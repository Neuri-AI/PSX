"""PyQt5/PyQt6 renderers for PSX's portable primitive subset.

Adding a new host tag
---------------------
Call :func:`register_primitive` once (module import time is fine); every
``QtRenderer`` picks it up, including renderers created before the call::

    register_primitive(
        "Slider",
        qt_class="QSlider",
        validate=validate_slider_props,
        apply=apply_qt_slider,
        updated_props=updated_slider_props,
        events={"on_change": ("valueChanged", emit_value)},
    )

Layout containers are registered with :func:`register_layout`.
"""

from __future__ import annotations

import importlib
import sys
from threading import get_ident
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from psx.sfle.model import LayoutConstraints, LayoutResult
from psx.core.props import FLEX_ITEM_PROPS
from psx.sfle.native_component_capabilities import native_leaf_needs_measurement
from psx.sfle.external_native_geometry_ports import external_port_for


from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import (
    NodeKind,
    VNode,

)
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.button import apply_qt_button, updated_button_props
from psx.renderers.components.checkbox import apply_qt_checkbox, updated_checkbox_props
from psx.renderers.components.text import apply_qt_text, updated_text_props
from psx.renderers.components.textarea import apply_qt_textarea, updated_textarea_props
from psx.renderers.components.input import apply_qt_input, updated_input_props
from psx.renderers.components.slider import apply_qt_slider, updated_slider_props
from psx.renderers.components.spacer import apply_qt_spacer, updated_spacer_props
from psx.renderers.components.progressbar import apply_qt_progressbar, updated_progressbar_props
from psx.renderers.components.radio import radio_props, updated_radio_props
from psx.renderers.components.select import apply_qt_select, updated_select_props
from psx.core.contracts import (
    validate_textarea_props,
    validate_input_props,
    validate_button_props,
    validate_checkbox_props,
    validate_text_props,
    validate_slider_props,
    validate_spacer_props,
    validate_progressbar_props,
    validate_radio_props,
    validate_select_props,
)

_LAYOUT_PROPS = frozenset({"spacing", "padding"})
_CONTAINER_UPDATABLE = frozenset({"label", "enabled", "spacing", "padding"})

# (signal attribute name on the widget, factory building the Python callback)
EventFactory = Callable[[object, EventSlot], Callable[..., object]]
EventDef = tuple[str, EventFactory]

# Appliers
def apply_qt_radio(widget, props):
    parent = widget.parentWidget()
    radios = getattr(parent, "_psx_radios", None)
    previous = getattr(widget, "_psx_radio_value", None)
    value = props["value"]
    if radios is not None and previous != value:
        if value in radios and radios[value] is not widget:
            raise RendererCapabilityError(
                f"RadioGroup has duplicate Radio value {value!r}."
            )
        if radios.get(previous) is widget:
            del radios[previous]
        radios[value] = widget
    widget.setText(str(props["label"]))
    widget.setEnabled(bool(props["enabled"]))
    widget._psx_radio_value = value
    if radios is not None and previous != value:
        from psx.renderers.qt.radiogroup import QtRadioGroupAdapter
        QtRadioGroupAdapter._sync_checked(parent, parent._psx_selected_value)

@dataclass(slots=True)
class QtHandle:
    node_type: object
    widget: object
    layout: object | None = None
    native: NativeWidget | None = None
    props: dict[str, object] = field(default_factory=dict)
    original_parent: object | None = None


@dataclass(slots=True)
class QtEventSubscription:
    signal: object
    callback: Callable[..., object]


@dataclass(slots=True)
class NativeEventSubscription:
    dispose: Callable[[], None]


# -- event callback factories (reusable when registering new primitives) ---

def emit_call(widget: object, slot: EventSlot) -> Callable[..., object]:
    """Ignore the signal arguments and invoke the slot with none."""
    return lambda *_: slot.invoke()


def emit_value(widget: object, slot: EventSlot) -> Callable[..., object]:
    """Forward the signal's single value as-is."""
    return lambda value: slot.invoke(value)


def emit_bool(widget: object, slot: EventSlot) -> Callable[..., object]:
    """Forward the signal's single value coerced to ``bool``."""
    return lambda value: slot.invoke(bool(value))


def emit_plain_text(widget: object, slot: EventSlot) -> Callable[..., object]:
    """Ignore the signal arguments and forward ``widget.toPlainText()``."""
    return lambda *_: slot.invoke(widget.toPlainText())


def emit_input_value(widget, slot):
    return lambda text: slot.invoke(text)


def emit_textarea_value(widget, slot):
    return lambda: slot.invoke(widget.toPlainText())

def emit_qt_select(widget, slot):
    def changed(index):
        if index > 0:
            slot.invoke(widget.itemData(index))
    return changed


def emit_slider_value(widget, slot):
    props = widget._psx_props
    factor = widget._psx_factor
    return lambda int_value: slot.invoke(
        props["min"] + int_value / factor
    )

# -- registries -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    """Everything the renderer needs to know about one leaf host primitive.

    ``qt_class`` is a name because the concrete class depends on the binding
    (PyQt5 vs PyQt6) and is resolved per renderer instance.
    """

    qt_class: str
    validate: Callable[[Mapping[str, object]], None]
    # (widget, props, binding)
    apply: Callable[[object, Mapping[str, object], str], None]
    updated_props: Callable[
        [Mapping[str, object], Mapping[str, object],
            frozenset[str]], dict[str, object]
    ]
    events: Mapping[str, EventDef] = field(default_factory=dict)


_PRIMITIVES: dict[str, PrimitiveSpec] = {}
_LAYOUTS: dict[str, bool] = {}  # tag name -> vertical?


def register_primitive(
    name: str,
    *,
    qt_class: str,
    validate: Callable[[Mapping[str, object]], None],
    apply: Callable[..., None],
    updated_props: Callable[..., dict[str, object]],
    events: Mapping[str, EventDef] | None = None,
    takes_binding: bool = True,
    replace: bool = False,
) -> PrimitiveSpec:
    """Register a leaf host tag.

    ``apply`` is called as ``apply(widget, props, binding)``; pass
    ``takes_binding=False`` if it only accepts ``(widget, props)``.
    """
    if name in _LAYOUTS or (name in _PRIMITIVES and not replace):
        raise ValueError(f"Primitive {name!r} is already registered.")
    if not takes_binding:
        without_binding = apply

        def apply(widget, props, _binding):  # noqa: F811
            without_binding(widget, props)

    spec = PrimitiveSpec(qt_class, validate, apply,
                         updated_props, dict(events or {}))
    _PRIMITIVES[name] = spec
    return spec


def register_layout(name: str, *, vertical: bool, replace: bool = False) -> None:
    """Register a container tag backed by a QVBoxLayout/QHBoxLayout."""
    if name in _PRIMITIVES or (name in _LAYOUTS and not replace):
        raise ValueError(f"Layout {name!r} is already registered.")
    _LAYOUTS[name] = vertical


# -- built-in tags ----------------------------------------------------------

register_primitive(
    "Text", qt_class="QLabel",
    validate=validate_text_props, apply=apply_qt_text, updated_props=updated_text_props,
)
register_primitive(
    "Button", qt_class="QPushButton",
    validate=validate_button_props, apply=apply_qt_button, updated_props=updated_button_props,
    events={"on_click": ("clicked", emit_call)},
)
register_primitive(
    "Checkbox", qt_class="QCheckBox",
    validate=validate_checkbox_props, apply=apply_qt_checkbox, updated_props=updated_checkbox_props,
    events={"on_change": ("toggled", emit_bool)},
    takes_binding=False,
)
register_primitive(
    "TextArea",
    qt_class="QPlainTextEdit",
    validate=validate_textarea_props,
    apply=apply_qt_textarea,
    updated_props=updated_textarea_props,
    events={"on_change": ("textChanged", emit_textarea_value)},
)
register_primitive(
    "Input",
    qt_class="QLineEdit",
    validate=validate_input_props,
    apply=apply_qt_input,
    updated_props=updated_input_props,
    events={
        "on_change": ("textChanged", emit_input_value),
        "on_submit": ("returnPressed", lambda w, s: (lambda: s.invoke())),
    },
)
register_primitive(
    "Slider",
    qt_class="QSlider",
    validate=validate_slider_props,
    apply=apply_qt_slider,
    updated_props=updated_slider_props,
    events={"on_change": ("valueChanged", emit_slider_value)},
)
register_primitive(
    "Spacer", qt_class="QWidget",
    validate=validate_spacer_props,
    apply=apply_qt_spacer,
    updated_props=updated_spacer_props,
    takes_binding=False,
)
register_primitive(
    "ProgressBar", qt_class="QProgressBar",
    validate=validate_progressbar_props,
    apply=apply_qt_progressbar,
    updated_props=updated_progressbar_props,
)

register_primitive(
    "Radio", qt_class="QRadioButton",
    validate=validate_radio_props,
    apply=apply_qt_radio,
    updated_props=updated_radio_props,
    takes_binding=False,
)
register_primitive(
    "Select", qt_class="QComboBox",
    validate=validate_select_props,
    apply=apply_qt_select,
    updated_props=updated_select_props,
    events={"on_change": ("currentIndexChanged", emit_qt_select)},
)

# -- renderer ---------------------------------------------------------------

def _make_resize_filter(core, on_resize, on_invalidation=None):
    """Observe root viewport and native style/DPI changes without owning layout."""
    qevents = getattr(core.QEvent, "Type", core.QEvent)
    event_type = getattr(qevents, "Resize")
    semantic_types = {
        value: reason
        for name, reason in (
            ("FontChange", "font"),
            ("ApplicationFontChange", "font"),
            ("PaletteChange", "theme"),
            ("ApplicationPaletteChange", "theme"),
            ("StyleChange", "theme"),
            ("ScreenChangeInternal", "dpi"),
            ("DevicePixelRatioChange", "dpi"),
        )
        if (value := getattr(qevents, name, None)) is not None
    }

    class ResizeFilter(core.QObject):
        def eventFilter(self, watched, event):
            if event.type() == event_type:
                size = event.size()
                on_resize(watched, size.width(), size.height())
            elif on_invalidation is not None:
                reason = semantic_types.get(event.type())
                if reason is not None:
                    on_invalidation(watched, reason)
            return False

    return ResizeFilter()


def _make_dispatcher(core):
    """Build a QObject bridge that queues work from any Python thread onto the Qt loop."""
    queued = getattr(getattr(core.Qt, "ConnectionType",
                     core.Qt), "QueuedConnection")
    signal = getattr(core, "pyqtSignal", None) or core.Signal
    slot = getattr(core, "pyqtSlot", None) or core.Slot

    class Dispatcher(core.QObject):
        requested = signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.requested.connect(self._invoke, queued)

        @slot(object)
        def _invoke(self, callback: Callable[[], None]) -> None:
            callback()

    return Dispatcher()


class QtRenderer:
    """Single Qt renderer shared by PyQt5/6 and PySide2/6 bindings."""

    def __init__(
        self,
        binding: str,
        argv: list[str] | None = None,
        *,
        sfle_constraints: LayoutConstraints | None = None,
        engine: object | None = None,
    ) -> None:
        if sfle_constraints is not None and not isinstance(sfle_constraints, LayoutConstraints):
            raise TypeError("Qt SFLE viewport requires LayoutConstraints.")
        if sfle_constraints is None and engine is not None:
            raise ValueError("Qt SFLE engine requires explicit viewport constraints.")
        from psx.sfle.backend import load_layout_engine
        self._sfle_constraints = sfle_constraints
        self._sfle_engine = (engine if engine is not None else load_layout_engine()) if sfle_constraints else None
        self._sfle_generation = 0
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations
        self._sfle_measurement_invalidations = MeasurementInvalidations()
        from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
        self._sfle_native_intrinsic_cache = NativeIntrinsicCache()
        from psx.sfle.native_resource_watch import ImageResourceWatch
        self._sfle_image_resource_watch = ImageResourceWatch()
        self._sfle_resource_poll_scheduled = False
        self._sfle_resource_error: Exception | None = None
        self._sfle_invalidation_scheduled = False
        self._sfle_invalidation_lifetime = 0
        self._sfle_mounted_root = None
        self._sfle_in_commit = False
        self._sfle_owner_thread = get_ident()
        self._sfle_mounted_root = None
        self._sfle_watched_widget = None
        self._sfle_resize_filter = None
        self._sfle_style_watched_widgets = {}
        self._sfle_resize_pending = None
        self._sfle_resize_baseline = None
        self._sfle_resize_scheduled = False
        self._sfle_resize_epoch = 0
        self._sfle_resize_error: Exception | None = None
        self._sfle_textarea_pending = False
        self._sfle_textarea_epoch = 0
        self._sfle_textarea_error: Exception | None = None
        self.sfle_result: LayoutResult | None = None
        self._sfle_physical_commit_error: float | None = None
        self._sfle_backend = "qt"
        self._binding = binding.lower()
        self._binding_package = binding
        core = importlib.import_module(f"{binding}.QtCore")
        self._qtcore = core
        self._widgets = widgets = importlib.import_module(
            f"{binding}.QtWidgets")

        self._widget = widgets.QWidget
        self._vbox = widgets.QVBoxLayout
        self._hbox = widgets.QHBoxLayout
        # resolved lazily from the registry
        self._primitive_classes: dict[str, type] = {}

        application = widgets.QApplication
        if binding == "PySide6" and application.instance() is None:
            try:
                from PySide6.QtWebView import QtWebView
            except ImportError:
                # QtWebView is optional unless an application renders WebView.
                pass
            else:
                QtWebView.initialize()
        self.application = application.instance() or application(
            argv if argv is not None else sys.argv)
        self._dispatcher = _make_dispatcher(core)

        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in (*_LAYOUTS, "Fragment", "Flex", *_PRIMITIVES, "Native"):
            self.adapters.register(component, self._default_adapter)

        # Register built-in adapters for common components. 

        from .divider import make_qt_divider_adapter
        from .image import QtImageAdapter
        from .switch import QtSwitchAdapter
        from .link import QtLinkAdapter
        from .badge import QtBadgeAdapter
        from .spinbox import QtSpinBoxAdapter
        from .scroll import QtScrollAdapter
        from .box import make_qt_box_adapter
        from .radiogroup import make_qt_radiogroup_adapter
        self.adapters.register("Divider", make_qt_divider_adapter(self))
        self.adapters.register("Image", QtImageAdapter())
        self.adapters.register("Switch", QtSwitchAdapter())
        self.adapters.register("Link", QtLinkAdapter())
        self.adapters.register("Badge", QtBadgeAdapter())
        self.adapters.register("SpinBox", QtSpinBoxAdapter())
        self.adapters.register("Scroll", QtScrollAdapter())
        self.adapters.register("Box", make_qt_box_adapter(self))
        self.adapters.register("RadioGroup", make_qt_radiogroup_adapter(self))
        if sfle_constraints is not None:
            from .flex import QtSFLEFlexAdapter
            self.adapters.register("Flex", QtSFLEFlexAdapter(), replace=True)

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def _sfle_poll_image_resources(self, lifetime: int) -> None:
        if lifetime != self._sfle_invalidation_lifetime:
            return
        self._sfle_resource_poll_scheduled = False
        root = self._sfle_mounted_root
        if root is None or root.disposed:
            return
        for instance in self._sfle_image_resource_watch.changed():
            if instance.disposed:
                continue
            widget = instance.handle.widget
            # Image adapters cache decoded content by source string; a
            # revision at that same path must bypass the old decoded image.
            widget._psx_source = None
            widget._psx_pixmap_cache = None
            widget._psx_image_cache = None
            source = instance.node.props["source"]
            try:
                self.update(instance.handle, {"source": source}, frozenset())
                reload_image = getattr(widget, "reload", None)
                if callable(reload_image):
                    reload_image()
                self._sfle_resource_error = None
                self.request_sfle_invalidation("resource", widget_id=id(widget))
                self._sfle_image_resource_watch.acknowledge(instance)
            except Exception as error:
                # Preserve the last committed geometry and keep watching;
                # recreating a missing/invalid file can recover in place.
                self._sfle_resource_error = error
        self._sfle_schedule_image_poll()

    def _sfle_schedule_image_poll(self) -> None:
        if self._sfle_resource_poll_scheduled:
            return
        root = self._sfle_mounted_root
        if (root is None or root.disposed
                or not self._sfle_image_resource_watch.sync(root)):
            return
        self._sfle_resource_poll_scheduled = True
        epoch = self._sfle_invalidation_lifetime
        self._qtcore.QTimer.singleShot(
            600, lambda: self._sfle_poll_image_resources(epoch))

    def request_sfle_invalidation(self, reason: str, *, widget_id: int | None = None) -> None:
        """Coalesce semantic measurement changes on the backend owner UI thread.

        The mounted instance is reused; the existing SFLE transaction remains
        the only writer. Teardown invalidates queued work by epoch.
        """
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations

        if self._sfle_constraints is None:
            raise RendererCapabilityError("SFLE measurement invalidation requires enabled SFLE.")
        state = self._sfle_measurement_invalidations
        state.request(reason, widget_id=widget_id)
        if self._sfle_invalidation_scheduled:
            return
        self._sfle_invalidation_scheduled = True
        scheduled_epoch = self._sfle_invalidation_lifetime

        def flush() -> None:
            if scheduled_epoch != self._sfle_invalidation_lifetime:
                return
            self._sfle_invalidation_scheduled = False
            root = self._sfle_mounted_root
            if root is None or root.disposed or not state.needs_commit():
                return
            epoch = state.epoch
            try:
                self.commit_layout(root)
            except Exception:
                # Preserve all invalidations for explicit retry. A failed
                # native transaction must never acknowledge its epoch.
                self._sfle_last_invalidation_error = True
                raise
            else:
                self._sfle_last_invalidation_error = False
                state.acknowledge(epoch)

        self.schedule_ui(flush)

    def set_sfle_constraints(self, constraints: LayoutConstraints) -> None:
        """Update host viewport constraints; caller may re-commit mounted tree."""
        if self._sfle_constraints is None:
            raise RendererCapabilityError("Qt SFLE was not enabled for this renderer.")
        if not isinstance(constraints, LayoutConstraints):
            raise TypeError("Qt SFLE constraints must be LayoutConstraints.")
        self._sfle_constraints = constraints
        self._sfle_generation += 1

    def _sfle_watch_child_style_events(self, root: object) -> None:
        """Track live child widgets for font, palette and DPR changes."""
        watched = {}
        def walk(instance: object) -> None:
            handle = getattr(instance, "handle", None)
            if handle is not None and getattr(handle, "widget", None) is not None:
                widget = handle.widget
                watched[id(widget)] = widget
            for child in instance.children:
                walk(child)
        walk(root)
        for identity, widget in tuple(self._sfle_style_watched_widgets.items()):
            if identity not in watched:
                try:
                    widget.removeEventFilter(self._sfle_resize_filter)
                except RuntimeError:
                    pass
        for identity, widget in watched.items():
            if identity not in self._sfle_style_watched_widgets:
                widget.installEventFilter(self._sfle_resize_filter)
        self._sfle_style_watched_widgets = watched

    def _sfle_on_native_semantic_change(self, watched, reason: str) -> None:
        if (id(watched) in self._sfle_style_watched_widgets
                and self._sfle_mounted_root is not None
                and self._sfle_constraints is not None):
            # Screen/DPR migration changes the entire logical-to-device
            # projection; root-level style changes likewise affect all
            # descendants. A leaf font/style change only dirties that
            # native widget's intrinsic result; SFLE still computes the
            # authoritative geometry for the complete tree.
            global_change = (reason == "dpi" or watched is self._sfle_watched_widget)
            self.request_sfle_invalidation(
                reason, widget_id=None if global_change else id(watched),
            )

    def _sfle_on_viewport_resize(self, watched, width: int, height: int) -> None:
        if watched is not self._sfle_watched_widget or width <= 0 or height <= 0:
            return
        constraints = self._sfle_constraints
        if constraints is None or self._sfle_mounted_root is None:
            return
        if self._sfle_resize_baseline == (width, height):
            return
        self._sfle_resize_baseline = (width, height)
        if (constraints.width.value, constraints.height.value) == (width, height):
            return
        self._sfle_resize_pending = (width, height)
        if self._sfle_resize_scheduled:
            return
        self._sfle_resize_scheduled = True
        epoch = self._sfle_resize_epoch
        # Frame-sized trailing-edge debounce: Qt may deliver consecutive
        # top-level window Resize events over multiple nested event turns.
        self._qtcore.QTimer.singleShot(16, lambda: self._sfle_flush_viewport_resize(epoch))

    def _sfle_flush_viewport_resize(self, epoch: int) -> None:
        self._sfle_resize_scheduled = False
        if epoch != self._sfle_resize_epoch or self._sfle_mounted_root is None:
            return
        size = self._sfle_resize_pending
        self._sfle_resize_pending = None
        if size is None:
            return
        root = self._sfle_mounted_root
        if root.disposed:
            return
        from psx.sfle.model import AvailableSize
        try:
            self.set_sfle_constraints(LayoutConstraints(
                AvailableSize(size[0], True), AvailableSize(size[1], True),
            ))
            self.commit_layout(root)
            self._sfle_resize_error = None
        except Exception as exc:
            # Exceptions must not cross Qt's C++ event callback boundary.
            self._sfle_resize_error = exc
            import logging
            logging.getLogger(__name__).exception("Qt SFLE viewport resize failed")

    def _sfle_on_textarea_content_changed(self) -> None:
        """Coalesce native edits into one SFLE intrinsic remeasurement.

        Signals are emitted on the Qt UI thread. Never perform a layout
        transaction inside the QPlainTextEdit signal/paint call stack.
        """
        if (self._sfle_constraints is None or self._sfle_mounted_root is None
                or self._sfle_in_commit or self._sfle_textarea_pending):
            return
        self._sfle_textarea_pending = True
        epoch = self._sfle_textarea_epoch
        self._qtcore.QTimer.singleShot(
            0, lambda: self._sfle_flush_textarea_content(epoch),
        )

    def _sfle_flush_textarea_content(self, epoch: int) -> None:
        if epoch != self._sfle_textarea_epoch:
            return
        self._sfle_textarea_pending = False
        root = self._sfle_mounted_root
        if root is None or root.disposed:
            return
        try:
            self._sfle_measurement_invalidations.request("content")
            self.commit_layout(root)
            self._sfle_textarea_error = None
        except Exception as exc:
            self._sfle_textarea_error = exc
            import logging
            logging.getLogger(__name__).exception(
                "Qt TextArea native SFLE remeasurement failed",
            )

    def commit_layout(self, root: object) -> None:
        if self._sfle_constraints is None:
            return
        from psx.sfle.native_grid_bridge import is_mounted_native_grid_root, commit_native_grid
        from psx.sfle.grid_native_commit import GridCommitBackend
        from psx.sfle.qt_layout_bridge import commit_qt_sfle
        # Native style/texture signals can arrive while measuring. Retry a
        # bounded number of times using the latest semantic epoch; never
        # publish a transaction rejected for stale measurements.
        from psx.sfle.errors import SFLEError
        for attempt in range(3):
            try:
                if is_mounted_native_grid_root(root):
                    commit_native_grid(self, root, backend=GridCommitBackend.QT)
                else:
                    commit_qt_sfle(self, root)
                break
            except SFLEError as error:
                if ("Stale semantic invalidation" not in str(error)
                        or attempt == 2):
                    raise
        self._sfle_measurement_invalidations.acknowledge(
            self._sfle_measurement_invalidations.epoch)

        # An explicit/reconciler commit supersedes a pending native edit.
        self._sfle_textarea_epoch += 1
        self._sfle_textarea_pending = False
        # Subscribe only after the mounted SFLE root is fully certified.
        # The observer watches the real root QWidget, not a nested Flex.
        widget = root.native_handle().widget
        if widget is not self._sfle_watched_widget:
            if self._sfle_watched_widget is not None:
                self._sfle_watched_widget.removeEventFilter(self._sfle_resize_filter)
            self._sfle_resize_epoch += 1
            self._sfle_resize_pending = None
            self._sfle_resize_scheduled = False
            self._sfle_resize_filter = _make_resize_filter(
                self._qtcore, self._sfle_on_viewport_resize,
                self._sfle_on_native_semantic_change,
            )
            widget.installEventFilter(self._sfle_resize_filter)
            self._sfle_watched_widget = widget
            self._sfle_resize_baseline = (widget.width(), widget.height())
        self._sfle_mounted_root = root
        self._sfle_watch_child_style_events(root)
        self._sfle_schedule_image_poll()

    def invalidate_layout(self) -> None:
        self._sfle_invalidation_lifetime += 1
        self._sfle_invalidation_scheduled = False
        self._sfle_measurement_invalidations.cancel()
        self._sfle_native_intrinsic_cache.clear()
        self._sfle_image_resource_watch.clear()
        self._sfle_resource_poll_scheduled = False
        self._sfle_mounted_root = None
        if self._sfle_constraints is not None:
            self._sfle_generation += 1
            self._sfle_resize_epoch += 1
            self._sfle_resize_pending = None
            self._sfle_resize_scheduled = False
            self._sfle_textarea_epoch += 1
            self._sfle_textarea_pending = False
            self._sfle_textarea_error = None
            self._sfle_mounted_root = None
            if self._sfle_watched_widget is not None:
                # Qt may already have destroyed a borrowed/owned widget.
                try:
                    self._sfle_watched_widget.removeEventFilter(self._sfle_resize_filter)
                except RuntimeError:
                    pass
            for widget in self._sfle_style_watched_widgets.values():
                try:
                    widget.removeEventFilter(self._sfle_resize_filter)
                except (RuntimeError, TypeError):
                    pass
            self._sfle_style_watched_widgets.clear()
            self._sfle_watched_widget = None
            self._sfle_resize_filter = None
            self._sfle_resize_baseline = None
            self.sfle_result = None
            self._sfle_physical_commit_error = None

    def _adapter_for(self, key: object):
        return self.adapters.get(key) or self._default_adapter

    def _widget_class(self, name: str) -> type:
        cls = self._primitive_classes.get(name)
        if cls is None:
            cls = self._primitive_classes[name] = getattr(
                self._widgets, _PRIMITIVES[name].qt_class)
        return cls

    # -- create -----------------------------------------------------------

    def create(self, node: VNode, parent: object | None) -> QtHandle:
        if self._sfle_constraints is not None:
            # G2 incremental native coverage: don't silently delegate an unported
            # layout or primitive to native Qt layout managers.
            if node.kind not in (NodeKind.HOST, NodeKind.NATIVE):
                raise RendererCapabilityError("Native SFLE requires a host or Native layout participant.")
            # An unregistered custom host or a Native declaration without a
            # strict SFLE port must fail *before* its factory mutates the GUI.
            port = external_port_for(node, self)
            if port is None and node.type not in ("Flex", "Grid", "GridItem"):
                native_leaf_needs_measurement(node, backend="qt")
            if node.type not in ("Flex", "Grid", "GridItem"):
                node = VNode(node.kind, node.type, node.key,
                             {k: v for k, v in node.props.items() if k not in FLEX_ITEM_PROPS},
                             node.children)
        # type: ignore[return-value]
        return self._adapter_for(adapter_key(node)).create(self, node, parent)

    def _adapter_create(self, node: VNode, parent: object | None) -> QtHandle:
        if node.kind is NodeKind.HOST and node.type in ("Grid", "GridItem"):
            if self._sfle_constraints is None:
                raise RendererCapabilityError(
                    f"Native SFLE {self._sfle_backend} SFLE geometry not certified for {node.type!r}.")
            if node.type == "GridItem" and (parent is None or _handle(parent).node_type != "Grid"):
                raise RendererCapabilityError("GridItem must be a direct child of a mounted Grid.")
            if node.type == "Grid" and parent is not None and _handle(parent).node_type not in ("GridItem", "Flex"):
                raise RendererCapabilityError("Nested Grid must be the direct content root of GridItem.")
            return QtHandle(node.type, self._widget(), props=dict(node.props))
        if node.kind is NodeKind.HOST and node.type == "Flex":
            raise RendererCapabilityError(
                "Flex requires the Native SFLE SFLE geometry adapter for Qt; "
                "native fallback layout is forbidden.")
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _handle(
                parent).widget if parent is not None else None
            return self._native(node, native_parent)
        vertical = True if node.kind is NodeKind.FRAGMENT else _LAYOUTS.get(
            node.type)
        if vertical is not None:
            return self._container(node, vertical=vertical)
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(
                f"PyQt cannot create node kind {node.kind.value!r}.")
        spec = _PRIMITIVES.get(node.type)
        if spec is None:
            raise RendererCapabilityError(
                f"PyQt does not support host primitive {node.type!r}.")
        widget = self._widget_class(node.type)()
        spec.apply(widget, node.props, self._binding_package)
        if self._sfle_constraints is not None and node.type == "Text":
            # QLabel's real heightForWidth is enabled by wordWrap.
            # SFLE (not QLabel) still owns size and position.
            widget.setWordWrap(True)
        if self._sfle_constraints is not None and node.type == "TextArea":
            # Native Qt continues to paint/edit text; SFLE owns the outer
            # rectangle. Native text edits invalidate width-sensitive height.
            widget.textChanged.connect(self._sfle_on_textarea_content_changed)
        return QtHandle(node.type, widget, props=dict(node.props))

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        if self._sfle_constraints is not None and _handle(handle).node_type != "Flex":
            changed = {key: value for key, value in changed.items() if key not in FLEX_ITEM_PROPS}
            removed = frozenset(key for key in removed if key not in FLEX_ITEM_PROPS)
            if not changed and not removed:
                return
        self._adapter_for(handle_adapter_key(handle)).update(
            self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _handle(handle)
        if target.node_type in ("Grid", "GridItem"):
            target.props.update(changed)
            for name in removed:
                target.props.pop(name, None)
            return
        if target.native is not None:
            _update_native(target, changed, removed)
            return
        spec = _PRIMITIVES.get(target.node_type)
        if spec is not None:
            props = spec.updated_props(target.props, changed, removed)
            spec.apply(target.widget, props, self._binding_package)
            target.props = props
            return
        _update_container(target, changed, removed)

    # -- tree operations --------------------------------------------------

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        if _handle(parent).node_type in ("Grid", "GridItem"):
            widget = _handle(child).widget
            widget.setParent(_handle(parent).widget)
            # A child mounted after its top-level Grid is already visible
            # (for example, a view selected through use_state) does not
            # inherit visibility merely by being reparented.
            widget.show()
            return
        _layout(_handle(parent)).insertWidget(index, _handle(child).widget)

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        if _handle(parent).node_type in ("Grid", "GridItem"):
            return
        layout = _layout(_handle(parent))
        widget = _handle(child).widget
        layout.removeWidget(widget)
        layout.insertWidget(index, widget)

    def remove(self, parent: object, child: object) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        item = _handle(child)
        if _handle(parent).node_type in ("Grid", "GridItem"):
            item.widget.setParent(None)
            return
        _layout(_handle(parent)).removeWidget(item.widget)
        _release(item)

    def destroy(self, handle: object) -> None:
        self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        if not _release(target):
            target.widget.deleteLater()

    # -- events -----------------------------------------------------------

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self._adapter_for(handle_adapter_key(handle))
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        target = _handle(handle)
        if target.native is not None:
            if target.native.bind_event is None:
                raise RendererCapabilityError(
                    f"Native widget {target.native.name!r} has no event adapter for {event!r}."
                )
            disposer = target.native.bind_event(target.widget, event, slot)
            if not callable(disposer):
                raise TypeError(
                    "NativeWidget.bind_event must return a callable disposer.")
            return NativeEventSubscription(disposer)

        spec = _PRIMITIVES.get(target.node_type)
        definition = spec.events.get(event) if spec is not None else None
        if definition is None:
            raise RendererCapabilityError(
                f"{event} is not supported by {target.node_type!r} in PyQt.")
        signal_name, make_callback = definition
        signal = getattr(target.widget, signal_name)
        # only the requested event's closure is built
        callback = make_callback(target.widget, slot)
        signal.connect(callback)
        return QtEventSubscription(signal, callback)

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, NativeEventSubscription):
            try:
                subscription.dispose()
            except (RuntimeError, TypeError):
                pass
            return
        item = _subscription(subscription)
        try:
            item.signal.disconnect(item.callback)
        except (RuntimeError, TypeError):
            # Native deletion can disconnect a Qt signal before PSX disposes it.
            pass

    # -- lifecycle --------------------------------------------------------

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        self._dispatcher.requested.emit(callback)

    def run(self) -> int:
        return self.application.exec()

    # -- factories --------------------------------------------------------

    def _container(self, node: VNode, *, vertical: bool) -> QtHandle:
        widget = self._widget()
        layout = self._vbox(widget) if vertical else self._hbox(widget)
        padding = int(node.props.get("padding", 0))
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(int(node.props.get("spacing", 0)))
        return QtHandle(node.type, widget, layout)

    def _native(self, node: VNode, parent: object | None) -> QtHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != self._binding:
            renderer = declaration.renderer if isinstance(
                declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not {self._binding!r}."
            )
        initial_props = {k: v for k, v in node.props.items()
                         if not k.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = _build_native_widget(declaration, parent)
        if not isinstance(widget, self._widget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a {self._binding} QWidget, "
                f"got {type(widget).__name__}."
            )
        borrowed = declaration.ownership is NativeOwnership.BORROWED
        original_parent = widget.parentWidget() if borrowed else None
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if not borrowed:
                widget.setParent(None)
                widget.deleteLater()
            raise
        return QtHandle(declaration, widget, native=declaration, original_parent=original_parent)


class PyQt6Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None, *, sfle_constraints: LayoutConstraints | None = None, engine: object | None = None) -> None:
        super().__init__("PyQt6", argv, sfle_constraints=sfle_constraints, engine=engine)


class PyQt5Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None, *, sfle_constraints: LayoutConstraints | None = None, engine: object | None = None) -> None:
        super().__init__("PyQt5", argv, sfle_constraints=sfle_constraints, engine=engine)


# -- module helpers ---------------------------------------------------------

def _update_native(target: QtHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    update = target.native.update
    if (changed or removed) and update is None:
        raise RendererCapabilityError(
            f"Native widget {target.native.name!r} received prop changes but has no update adapter."
        )
    if update is not None:
        update(target.widget, changed, removed)


def _update_container(target: QtHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    if removed or not changed.keys() <= _CONTAINER_UPDATABLE:
        unsupported = set(removed) | (set(changed) - _CONTAINER_UPDATABLE)
        raise RendererCapabilityError(
            f"Unsupported PyQt props: {', '.join(sorted(unsupported))}")
    if not changed.keys().isdisjoint(_LAYOUT_PROPS):
        layout = _layout(target)
        if "spacing" in changed:
            layout.setSpacing(int(changed["spacing"]))
        if "padding" in changed:
            padding = int(changed["padding"])
            layout.setContentsMargins(padding, padding, padding, padding)
    if "label" in changed:
        target.widget.setText(str(changed["label"]))
    if "enabled" in changed:
        target.widget.setEnabled(bool(changed["enabled"]))


def _build_native_widget(declaration: NativeWidget, parent: object | None) -> object:
    if declaration.factory is None:
        return declaration.widget
    return declaration.factory(parent) if declaration.takes_parent else declaration.factory()


def _release(handle: QtHandle) -> bool:
    """Detach the widget from its Qt parent. Returns True if it was borrowed (must not be deleted)."""
    if handle.native is not None and handle.native.ownership is NativeOwnership.BORROWED:
        handle.widget.setParent(handle.original_parent)
        return True
    handle.widget.setParent(None)
    return False


def _handle(value: object) -> QtHandle:
    if not isinstance(value, QtHandle):
        raise TypeError("PyQt renderer received a foreign handle.")
    return value


def _subscription(value: object) -> QtEventSubscription:
    if not isinstance(value, QtEventSubscription):
        raise TypeError("PyQt renderer received a foreign event subscription.")
    return value


def _layout(handle: QtHandle) -> object:
    if handle.layout is None:
        raise RendererCapabilityError(
            f"{handle.node_type!r} cannot contain PSX children in PyQt.")
    return handle.layout


def _validate_props(node: VNode) -> None:
    if node.kind is NodeKind.NATIVE:
        return
    if node.kind is NodeKind.HOST:
        spec = _PRIMITIVES.get(node.type)
        if spec is not None:
            spec.validate(node.props)
            return
    allowed = _LAYOUT_PROPS if node.kind is NodeKind.FRAGMENT or node.type in _LAYOUTS else frozenset()
    if node.props.keys() <= allowed:
        return
    unsupported = set(node.props) - allowed
    raise RendererCapabilityError(
        f"Unsupported PyQt props for {node.type!r}: {', '.join(sorted(unsupported))}"
    )
