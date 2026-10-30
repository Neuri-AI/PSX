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
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget, _clear_native_snapshot
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
        "on_click": ("__psx_mouse_press__", emit_call),
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

_QT_NATIVE_LABEL_TYPES = {}
_QT_CSS_TEXT_TYPES = {}
_QT_CSS_BUTTON_TYPES = {}
_RESIZE_FILTER_TYPES = {}


def _make_resize_filter(core, on_resize, on_invalidation=None):
    """Reuse one QObject subclass per binding; keep callbacks instance-local.

    Defining a new Python QObject subclass on every native render creates
    accumulating Shiboken wrapper metadata on PySide even after teardown.
    """
    filter_type = _RESIZE_FILTER_TYPES.get(core.QObject)
    if filter_type is None:
        qevents = getattr(core.QEvent, "Type", core.QEvent)
        event_type = getattr(qevents, "Resize")
        semantic_types = {
            value: reason
            for name, reason in (
                ("FontChange", "font"),
                ("ApplicationFontChange", "font"),
                ("PaletteChange", "palette"),
                ("ApplicationPaletteChange", "theme"),
                ("StyleChange", "style"),
                ("ScreenChangeInternal", "dpi"),
                ("DevicePixelRatioChange", "dpi"),
            )
            if (value := getattr(qevents, name, None)) is not None
        }

        class ResizeFilter(core.QObject):
            def __init__(self, resize_handler, invalidation_handler):
                super().__init__()
                self._resize_handler = resize_handler
                self._invalidation_handler = invalidation_handler

            def eventFilter(self, watched, event):
                if event.type() == event_type:
                    callback = self._resize_handler
                    if callback is not None:
                        size = event.size()
                        callback(watched, size.width(), size.height())
                elif self._invalidation_handler is not None:
                    reason = semantic_types.get(event.type())
                    if reason is not None:
                        self._invalidation_handler(watched, reason)
                return False

            def discard_callbacks(self):
                self._resize_handler = None
                self._invalidation_handler = None

        filter_type = ResizeFilter
        _RESIZE_FILTER_TYPES[core.QObject] = filter_type
    return filter_type(on_resize, on_invalidation)

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
        self._sfle_prior_solver_input = None
        self._sfle_prior_solver_result = None
        self._sfle_prior_solver_engine = None
        # Single successful detached paint/layout fingerprint, renderer-owned.
        self._sfle_committed_signatures = None
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
        # Changes originating from PSX's own CSS projection already passed
        # through typed style effects and the reconciler's geometry decision.
        # Do not classify their synchronous Qt StyleChange/FontChange echoes
        # as external theme changes (which would trigger a second layout).
        if (getattr(self, "_sfle_css_projection_depth", 0)
                or getattr(watched, "_psx_css_projection_active", False)):
            return
        if reason in ("style", "palette"):
            generation = getattr(watched, "_psx_css_qss_generation", 0)
            consumed = getattr(watched, "_psx_css_qss_consumed", 0)
            if (generation > consumed
                    and getattr(watched, "_psx_css_last_applied_stylesheet", None)
                    == watched.styleSheet()):
                # Qt may deliver StyleChange or PaletteChange *after* its
                # CSS setStyleSheet call returns. Consume only the pending
                # explicitly self-authored QSS generation; external palette
                # and system-theme events still invalidate normally.
                watched._psx_css_qss_consumed = generation
                return
            reason = "theme"
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
        # Coalesce bursts within the current event turn without imposing a
        # full-frame delay. A zero-timeout callback executes after Qt finishes
        # dispatching the current native resize; pending holds the latest size.
        # Keep the callback out of the Resize event's native call stack.
        self._qtcore.QTimer.singleShot(0, lambda: self._sfle_flush_viewport_resize(epoch))

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
        widget = getattr(widget, "_psx_sfle_viewport_shell", widget)
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
        # A full unmount/remount must drop cached VNode blueprints and old
        # native intrinsic identities; a later tree always starts fresh.
        for cache_name in (
            "_psx_grid_intrinsic_reuse", "_psx_grid_flow_blueprints",
            "_sfle_structural_snapshot_reuse",
        ):
            cache = getattr(self, cache_name, None)
            if cache is not None:
                cache.clear()
        self._sfle_prior_solver_input = None
        self._sfle_prior_solver_result = None
        self._sfle_prior_solver_engine = None
        self._sfle_committed_signatures = None
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
            event_filter = self._sfle_resize_filter
            self._sfle_resize_filter = None
            if event_filter is not None:
                event_filter.discard_callbacks()
                event_filter.deleteLater()
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
            if port is None and node.type not in ("Flex", "Grid", "GridItem") and node.type not in FORMATTING_TAGS:
                native_leaf_needs_measurement(node, backend="qt")
            if node.type not in ("Flex", "Grid", "GridItem"):
                node = VNode(node.kind, node.type, node.key,
                             {k: v for k, v in node.props.items() if k not in FLEX_ITEM_PROPS},
                             node.children)
        # type: ignore[return-value]
        return self._adapter_for(adapter_key(node)).create(self, node, parent)

    def _adapter_create(self, node: VNode, parent: object | None) -> QtHandle:
        if node.kind is NodeKind.HOST and node.type in FORMATTING_TAGS:
            if self._sfle_constraints is None or node.props.get("display") not in ("block", "inline"):
                raise RendererCapabilityError(
                    "Qt div requires an enabled Cinnamon Block viewport.")
            if node.type == "label":
                # An implicit HTML-like label focuses a nested editable input.
                # Only the toolkit performs focus; Cinnamon still owns geometry.
                qt_widgets = self._widgets
                base_widget = self._widget

                widget_type = _QT_NATIVE_LABEL_TYPES.get(base_widget)
                if widget_type is None:
                    class NativeLabelHost(base_widget):
                        def mousePressEvent(self, event):
                            for editor in self.findChildren(qt_widgets.QLineEdit):
                                if editor.isEnabled():
                                    editor.setFocus()
                                    break
                            super().mousePressEvent(event)
                    widget_type = NativeLabelHost
                    _QT_NATIVE_LABEL_TYPES[base_widget] = widget_type

                widget = widget_type()
            else:
                widget = self._widget()
            if parent is None and node.props.get("display") == "block":
                # A block root is a content-height box, not the native
                # top-level window. Keep the window as an independent viewport
                # so CSS backgrounds paint only the measured semantic box.
                viewport = self._widget()
                viewport.resize(round(self._sfle_constraints.width.value),
                                round(self._sfle_constraints.height.value))
                widget.setParent(viewport)
                widget._psx_sfle_viewport_shell = viewport
            return QtHandle(node.type, widget, props=dict(node.props))
        if node.kind is NodeKind.HOST and node.type in ("Grid", "GridItem"):
            if self._sfle_constraints is None:
                raise RendererCapabilityError(
                    f"Native SFLE {self._sfle_backend} SFLE geometry not certified for {node.type!r}.")
            if node.type == "GridItem" and (parent is None or _handle(parent).node_type != "Grid"):
                raise RendererCapabilityError("GridItem must be a direct child of a mounted Grid.")
            if node.type == "Grid" and parent is not None and _handle(parent).node_type not in ("GridItem", "Flex", "div", "main", "section", "article", "header", "footer"):
                raise RendererCapabilityError("Grid must be inside a supported Cinnamon layout container.")
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
        if node.type == "Text":
            label_class = self._widget_class("Text")
            gui = __import__(self._binding_package + ".QtGui", fromlist=["QTextDocument"])
            core = __import__(self._binding_package + ".QtCore", fromlist=["QSize"])

            widget_type = _QT_CSS_TEXT_TYPES.get(label_class)
            if widget_type is None:
                class CssMeasuredTextLabel(label_class):
                    """QLabel-compatible text host with native QTextDocument line spacing."""

                    def __init__(self):
                        super().__init__()
                        self._psx_css_line_height = None
                        self._psx_css_document = None
                        self._psx_css_intrinsic_hint = None

                    def _psx_sync_line_height(self, height):
                        # A style/text/font revision invalidates the intrinsic
                        # QTextDocument size, never an allocated viewport width.
                        self._psx_css_intrinsic_hint = None
                        self._psx_css_line_height = height
                        if height is None:
                            self._psx_css_document = None
                            self.updateGeometry()
                            self.update()
                            return
                        document = gui.QTextDocument(self)
                        document.setDocumentMargin(0)
                        document.setDefaultFont(self.font())
                        cursor = gui.QTextCursor(document)
                        cursor.insertText(self.text())
                        cursor.select(getattr(gui.QTextCursor, "SelectionType", gui.QTextCursor).Document)
                        block = gui.QTextBlockFormat()
                        kinds = getattr(gui.QTextBlockFormat, "LineHeightTypes", gui.QTextBlockFormat)
                        block.setLineHeight(float(height), getattr(kinds.FixedHeight, 'value', kinds.FixedHeight))
                        block.setAlignment(self.alignment())
                        cursor.setBlockFormat(block)
                        char = gui.QTextCharFormat()
                        char.setForeground(self.palette().color(self.foregroundRole()))
                        cursor.mergeCharFormat(char)
                        self._psx_css_document = document
                        self.updateGeometry()
                        self.update()

                    def sizeHint(self):
                        document = self._psx_css_document
                        if document is None:
                            return super().sizeHint()
                        # Qt requests intrinsic sizeHint() repeatedly while
                        # applying native geometry. The unbounded-document
                        # intrinsic size is independent of the allocated width;
                        # only heightForWidth() needs a fresh width-based solve.
                        # CSS projection reconstructs the document for
                        # text/font/line-height changes. QTextDocument's
                        # revision changes on text edits. Avoid the expensive
                        # QFont.key() construction on every native sizeHint.
                        revision = document.revision()
                        cached = self._psx_css_intrinsic_hint
                        if (cached is not None and cached[0] is document
                                and cached[1] == revision):
                            return core.QSize(cached[2])
                        document.setTextWidth(-1)
                        size = document.size()
                        hint = core.QSize(
                            max(1, round(size.width())),
                            max(1, round(size.height())),
                        )
                        self._psx_css_intrinsic_hint = (document, revision, hint)
                        return core.QSize(hint)

                    def heightForWidth(self, width):
                        if self._psx_css_document is None:
                            return super().heightForWidth(width)
                        self._psx_css_document.setTextWidth(max(1, width))
                        return max(1, round(self._psx_css_document.size().height()))

                    def paintEvent(self, event):
                        if self._psx_css_document is None:
                            return super().paintEvent(event)
                        self._psx_css_document.setTextWidth(max(1, self.width()))
                        painter = gui.QPainter(self)
                        self._psx_css_document.drawContents(painter)
                        painter.end()
                widget_type = CssMeasuredTextLabel
                _QT_CSS_TEXT_TYPES[label_class] = widget_type

            widget = widget_type()
        elif node.type == "Button":
            button_class = self._widget_class("Button")

            widget_type = _QT_CSS_BUTTON_TYPES.get(button_class)
            if widget_type is None:
                class CssMeasuredButton(button_class):
                    def __init__(self):
                        super().__init__()
                        self._psx_css_line_height = None

                    def sizeHint(self):
                        natural = super().sizeHint()
                        if self._psx_css_line_height is not None:
                            extra = max(0, round(
                                self._psx_css_line_height - self.fontMetrics().height()
                            ))
                            natural.setHeight(natural.height() + extra)
                        return natural
                widget_type = CssMeasuredButton
                _QT_CSS_BUTTON_TYPES[button_class] = widget_type

            widget = widget_type()
        else:
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

    def apply_css(self, handle: object, computed: object) -> None:
        """Project one CSS transaction without interpreting Qt's own events as external."""
        self._sfle_css_projection_depth = (
            getattr(self, "_sfle_css_projection_depth", 0) + 1
        )
        try:
            self._apply_css_projected(handle, computed)
        finally:
            self._sfle_css_projection_depth -= 1

    def _apply_css_projected(self, handle: object, computed: object) -> None:
        """Paint explicit CSS backgrounds on Cinnamon-owned semantic hosts."""
        from psx.css.native_paint import qt_semantic_stylesheet
        target = _handle(handle)
        from psx.css.cursor import QT_CURSOR_SHAPES
        native_widget = target.widget
        authored_cursor = (
            computed.properties["cursor"] if computed is not None
            and "cursor" in computed.specified else "auto"
        )
        if authored_cursor != "auto":
            shape_enum = self._qtcore.Qt
            shapes = getattr(shape_enum, "CursorShape", shape_enum)
            cursor_shape = getattr(shapes, QT_CURSOR_SHAPES[authored_cursor])
            if (not getattr(native_widget, "_psx_css_cursor_applied", False)
                    or native_widget.cursor().shape() != cursor_shape):
                native_widget.setCursor(cursor_shape)
            native_widget._psx_css_cursor_applied = True
        elif getattr(native_widget, "_psx_css_cursor_applied", False):
            native_widget.unsetCursor()
            native_widget._psx_css_cursor_applied = False
        if target.node_type == "Badge":
            from psx.css.native_paint import foreground_hex
            target.widget._psx_css_foreground = foreground_hex(computed)
            target.widget.update()
            return
        if target.node_type == "Text":
            from psx.css.native_paint import native_text_typography
            from psx.renderers.components.text import apply_qt_text
            styles = native_text_typography(computed, line_height=True)
            if self._sfle_constraints is not None:
                revision = (target.props.get("value"), tuple((name, styles.get(name)) for name in ("font-family", "font-size", "font-weight", "line-height")))
                if getattr(target.widget, "_psx_css_font_revision", None) != revision:
                    target.widget._psx_css_font_revision = revision
                    self.request_sfle_invalidation("font", widget_id=id(target.widget))
            apply_qt_text(target.widget, target.props, self._binding_package)
            if styles:
                font = target.widget.font()
                if "font-family" in styles:
                    font.setFamily(styles["font-family"])
                if "font-size" in styles:
                    font.setPixelSize(round(styles["font-size"]))
                if "font-weight" in styles:
                    font.setBold(styles["font-weight"] >= 600)
                target.widget.setFont(font)
                if "text-align" in styles:
                    enum = getattr(__import__(self._binding_package + ".QtCore", fromlist=["Qt"]).Qt, "AlignmentFlag", __import__(self._binding_package + ".QtCore", fromlist=["Qt"]).Qt)
                    if enum is not None:
                        target.widget.setAlignment(getattr(enum, {"left": "AlignLeft", "right": "AlignRight", "center": "AlignHCenter"}[styles["text-align"]]) | enum.AlignVCenter)
                if "color" in styles:
                    target.widget.setStyleSheet("color: " + styles["color"] + ";")
            target.widget._psx_sync_line_height(styles.get("line-height"))
            return
        if target.node_type in ("Button", "Checkbox", "Input", "TextArea", "Radio", "Select", "Link"):
            from psx.css.native_paint import native_text_typography
            styles = native_text_typography(computed, line_height=target.node_type == "Button")
            widget = target.widget
            if not hasattr(widget, "_psx_css_base_font"):
                widget._psx_css_base_font = widget.font()
                widget._psx_css_base_stylesheet = widget.styleSheet()
            else:
                # A native adapter or application may replace its own QSS
                # between CSS commits. Rebase only when the installed style
                # differs from the last CSS projection we actually owned.
                installed = widget.styleSheet()
                if installed != getattr(widget, "_psx_css_last_applied_stylesheet",
                                        widget._psx_css_base_stylesheet):
                    widget._psx_css_base_stylesheet = installed
            font = widget._psx_css_base_font
            font = type(font)(font)
            if "font-family" in styles:
                font.setFamily(styles["font-family"])
            if "font-size" in styles:
                font.setPixelSize(round(styles["font-size"]))
            if "font-weight" in styles:
                font.setBold(styles["font-weight"] >= 600)
            widget._psx_css_projection_active = True
            try:
                if widget.font() != font:
                    widget.setFont(font)
            finally:
                widget._psx_css_projection_active = False
            if target.node_type == "Button":
                leading = styles.get("line-height")
                if leading is not None and (
                    "\n" in widget.text() or leading < widget.fontMetrics().height()
                ):
                    raise ValueError("Qt Button line-height needs single-line text and sufficient leading.")
                widget._psx_css_line_height = leading
                widget.updateGeometry()
            if "text-align" in styles:
                if target.node_type not in ("Button", "Link", "Input", "TextArea"):
                    raise ValueError(f"Native Qt {target.node_type} does not support CSS text-align.")
                if target.node_type == "Input":
                    qt = self._qtcore.Qt
                    flags = getattr(qt, "AlignmentFlag", qt)
                    alignment = {"left": flags.AlignLeft, "center": flags.AlignHCenter,
                                 "right": flags.AlignRight}[styles["text-align"]]
                    widget.setAlignment(alignment)
            elif target.node_type == "Input":
                widget.setAlignment(getattr(getattr(self._qtcore.Qt, "AlignmentFlag", self._qtcore.Qt), "AlignLeft"))
            declarations = []
            if "font-family" in styles:
                declarations.append('font-family: "' + styles["font-family"] + '";')
            if "font-size" in styles:
                declarations.append(f'font-size: {styles["font-size"]:g}px;')
            if "font-weight" in styles:
                declarations.append(f'font-weight: {styles["font-weight"]};')
            if "color" in styles:
                declarations.append('color: ' + styles["color"] + ';')
            from psx.css.native_paint import background_hex
            background = background_hex(computed)
            if background is not None:
                declarations.append(f"background-color: {background};")
            if "text-align" in styles and target.node_type in ("Button", "Link", "TextArea"):
                declarations.append('text-align: ' + styles["text-align"] + ';')
            from psx.css.native_paint import native_border_paint
            from psx.css.native_paint import native_border_radius
            radius = native_border_radius(computed)
            border = native_border_paint(computed)
            if border is not None:
                thickness, color = border
                declarations.append(f"border: {thickness:g}px solid {color};")
            from psx.css.native_paint import native_side_border_styles
            declarations.extend(native_side_border_styles(computed))
            if radius:
                declarations.append(f"border-radius: {radius:g}px;")
            if target.node_type == "Button" and computed is not None:
                from psx.sfle.lengths import LengthKind
                # Qt owns the button's internal text insets. Reuse the
                # validated CSS box sides rather than merely resizing its box.
                if "padding" in computed.specified or any(
                    f"padding-{side}" in computed.specified
                    for side in ("top", "right", "bottom", "left")
                ):
                    values = []
                    for side in ("top", "right", "bottom", "left"):
                        length = computed.properties[f"padding-{side}"]
                        if length.kind is not LengthKind.PX:
                            raise ValueError("Qt Button padding requires pixel lengths.")
                        values.append(length.value)
                    declarations.append(
                        "padding: " + " ".join(f"{value:g}px" for value in values) + ";"
                    )
                if "border-width" in computed.specified and border is None:
                    declarations.append("border: none;")
            baseline = widget._psx_css_base_stylesheet
            authored = " ".join(declarations)
            if authored and baseline.rstrip().endswith("}"):
                # A Link (or an externally styled Qt control) may already
                # have a selector block. Bare declarations after that block
                # are invalid QSS, so append a widget-local selector rule.
                widget_class = widget.metaObject().className()
                projected = baseline.rstrip() + "\n" + widget_class + " { " + authored + " }"
            elif authored:
                projected = (baseline + " " + authored).strip()
            else:
                projected = baseline
            if widget.styleSheet() != projected:
                widget._psx_css_projection_active = True
                try:
                    widget._psx_css_qss_generation = (
                        getattr(widget, "_psx_css_qss_generation", 0) + 1
                    )
                    widget.setStyleSheet(projected)
                finally:
                    widget._psx_css_projection_active = False
            widget._psx_css_last_applied_stylesheet = projected
            if self._sfle_constraints is not None:
                keys = ("font-family", "font-size", "font-weight", "line-height")
                if any(key in styles for key in keys) or hasattr(widget, "_psx_css_font_revision"):
                    revision = tuple((key, styles.get(key)) for key in keys)
                    if getattr(widget, "_psx_css_font_revision", None) != revision:
                        widget._psx_css_font_revision = revision
                        self.request_sfle_invalidation("font", widget_id=id(widget))
            return
        if target.node_type not in FORMATTING_TAGS:
            return
        authored = qt_semantic_stylesheet(computed)
        # A bare QWidget stylesheet applies to matching descendant widgets.
        # Scope semantic-host paint to this native widget so its border and
        # background do not appear on nested <p>, <div> or controls.
        css_name = getattr(target.widget, "_psx_css_object_name", None)
        if css_name is None:
            css_name = f"psx_css_{id(target.widget):x}"
            target.widget._psx_css_object_name = css_name
            target.widget.setObjectName(css_name)
        projected = f"#{css_name} {{ {authored} }}" if authored else ""
        if target.widget.styleSheet() != projected:
            target.widget._psx_css_projection_active = True
            try:
                target.widget._psx_css_qss_generation = (
                    getattr(target.widget, "_psx_css_qss_generation", 0) + 1
                )
                target.widget.setStyleSheet(projected)
            finally:
                target.widget._psx_css_projection_active = False
            target.widget._psx_css_last_applied_stylesheet = projected

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
        if target.node_type in FORMATTING_TAGS:
            updated = dict(target.props)
            updated.update(changed)
            for name in removed:
                updated.pop(name, None)
            if updated.get("display") not in ("block", "inline"):
                raise RendererCapabilityError(
                    "div currently supports only the Cinnamon Block context.")
            target.props = updated
            return
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
        if _handle(parent).node_type in ("Grid", "GridItem") or _handle(parent).node_type in FORMATTING_TAGS:
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
        if _handle(parent).node_type in ("Grid", "GridItem") or _handle(parent).node_type in FORMATTING_TAGS:
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
        if _handle(parent).node_type in ("Grid", "GridItem") or _handle(parent).node_type in FORMATTING_TAGS:
            item.widget.setParent(None)
            return
        _layout(_handle(parent)).removeWidget(item.widget)
        _release(item)

    def destroy(self, handle: object) -> None:
        self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        if target.native is not None:
            _clear_native_snapshot(target.widget)
        viewport = getattr(target.widget, "_psx_sfle_viewport_shell", None)
        if not _release(target):
            target.widget.deleteLater()
        if viewport is not None:
            viewport.close()
            viewport.deleteLater()

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
        if target.node_type == "Input" and event == "on_click":
            qt_core = self._qtcore
            event_type = qt_core.QEvent.Type.MouseButtonPress if hasattr(qt_core.QEvent, "Type") else qt_core.QEvent.MouseButtonPress
            class ClickFilter(qt_core.QObject):
                def eventFilter(self, watched, native_event):
                    if native_event.type() == event_type and watched.isEnabled():
                        slot.invoke()
                    return False
            filter_object = ClickFilter(target.widget)
            target.widget.installEventFilter(filter_object)
            return NativeEventSubscription(lambda: target.widget.removeEventFilter(filter_object))
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

    def transition_root(self, previous, replacement) -> None:
        """Replace the root content without replacing the native Qt window."""
        old = _handle(previous).widget
        new = _handle(replacement).widget
        previous_window = getattr(old, "_psx_sfle_viewport_shell", None)
        replacement_window = getattr(new, "_psx_sfle_viewport_shell", None)
        if previous_window is not None:
            if replacement_window is not None and replacement_window is not previous_window:
                # This provisional shell was never presented to the user.
                new.setParent(previous_window)
                replacement_window.deleteLater()
            else:
                new.setParent(previous_window)
            new._psx_sfle_viewport_shell = previous_window
            # Unmounting the former root must not destroy the reused viewport.
            old._psx_sfle_viewport_shell = None
            new.show()
            return
        # Legacy roots without a shell cannot transfer native ownership safely.
        # Keep their established presentation behavior.
        previous_window = old
        replacement_window = replacement_window or new
        replacement_window.setGeometry(previous_window.geometry())
        replacement_window.show()
        replacement_window.raise_()

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
