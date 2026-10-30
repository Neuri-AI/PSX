"""Kivy renderer for PSX's portable primitive subset.

Adding a new host tag
---------------------
Call :func:`register_primitive` once (module import time is fine); every
``KivyRenderer`` picks it up, including renderers created before the call::

    register_primitive(
        "Slider",
        factory=Slider,                          # called with no arguments
        validate=validate_slider_props,
        apply=apply_kivy_slider,                 # apply(widget, props)
        updated_props=updated_slider_props,
        events={"on_change": ("value", emit_value)},   # Kivy event/property name
        on_create=None,                          # optional hook after first apply
        on_destroy=None,                         # optional hook before teardown
    )

Container tags are registered with :func:`register_layout`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import get_ident

from psx.core.props import FLEX_ITEM_PROPS
from psx.sfle.native_component_capabilities import native_leaf_needs_measurement
from psx.sfle.external_native_geometry_ports import external_port_for
from psx.sfle.model import LayoutConstraints, LayoutResult

from kivy.base import runTouchApp
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KivyButton
from kivy.uix.checkbox import CheckBox as KivyCheckBox
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.slider import Slider as KivySlider
from kivy.uix.spinner import Spinner

from psx.core.errors import RendererCapabilityError
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget, _clear_native_snapshot
from psx.core.vnode import (NodeKind, VNode)
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.text import apply_kivy_text, updated_text_props, size_kivy_text
from psx.renderers.components.button import apply_kivy_button, updated_button_props
from psx.renderers.components.checkbox import apply_kivy_checkbox, updated_checkbox_props
from psx.renderers.components.input import apply_kivy_input, updated_input_props
from psx.renderers.components.textarea import apply_kivy_textarea, updated_textarea_props
from psx.renderers.components.slider import apply_kivy_slider, updated_slider_props
from psx.renderers.components.spacer import apply_kivy_spacer, updated_spacer_props
from psx.renderers.components.select import apply_kivy_select, updated_select_props
from psx.core.contracts import (
    validate_textarea_props,
    validate_input_props,
    validate_button_props,
    validate_checkbox_props,
    validate_text_props,
    validate_slider_props,
    validate_spacer_props,
    validate_select_props,
)
from psx.renderers.kivy.divider import KivyDividerAdapter


# Kivy 2.3's triangulated Line treats "width" as half the painted
# thickness. Scale the CSS width into drawable pixels, then halve only for
# the Kivy graphics instruction; layout/border-box geometry is unchanged.
# Always force the triangulated method, including width=1, because GL_LINE
# switches to a one-device-pixel path at exactly that value.
_KIVY_LINE_RASTER_FACTOR = 0.5

_LAYOUT_PROPS = frozenset({"spacing", "padding"})

# (Kivy event/property name passed to widget.bind, factory building the Python callback)
EventDef = tuple[str, Callable[[Widget, EventSlot],
                               Callable[..., object | None]]]

# Factories for creating event callbacks for Kivy widgets


class KivyLabeledCheckBox(KivyCheckBox):
    """Keep the checkbox's clickable area inclusive of optional label text."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._psx_label = Label(
            text="", halign="left", valign="middle",
            size_hint=(None, None),
        )
        self.add_widget(self._psx_label)
        self.bind(pos=self._layout_caption, size=self._layout_caption)
        self._layout_caption()

    def _layout_caption(self, *args):
        label = self._psx_label
        gap = 32
        label.pos = (self.x + gap, self.y)
        label.size = (max(0.0, self.width - gap), self.height)
        label.text_size = label.size


def _kivy_input_factory():
    return TextInput(multiline=False)


def _kivy_textarea_factory():
    # A portable TextArea must reflow when SFLE changes its content width.
    # Kivy's provider defaults are not consistent across platforms.
    return TextInput(multiline=True, do_wrap=True)


def _kivy_slider_factory():
    # Kivy 2.3's default style binds the slider track width to this property
    # during construction.  Its zero default is rejected by the Windows GL
    # provider before PSX's normal property application can run.
    return KivySlider(value_track_width=1.0)


@dataclass(slots=True, eq=False)
class KivyHandle:
    node_type: object
    widget: Widget
    props: dict[str, object]
    children: list["KivyHandle"] = field(default_factory=list)
    native: NativeWidget | None = None
    original_parent: Widget | None = None
    original_size_hint: object = None
    original_pos_hint: dict[str, object] | None = None


@dataclass(slots=True)
class KivyEventSubscription:
    widget: Widget
    event: str
    callback: Callable[..., object | None]


@dataclass(slots=True)
class KivyNativeEventSubscription:
    dispose: Callable[[], None]


# -- event callback factories (reusable when registering new primitives) ---

def emit_call(widget: Widget, slot: EventSlot) -> Callable[..., object | None]:
    """Ignore the event arguments and invoke the slot with none."""
    return lambda *_: slot.invoke()


def emit_value(widget: Widget, slot: EventSlot) -> Callable[..., object | None]:
    """Forward the property's new value as-is (callback receives ``(widget, value)``)."""
    return lambda _widget, value: slot.invoke(value)


def emit_active(widget: Widget, slot: EventSlot) -> Callable[..., object | None]:
    """Forward ``active`` as ``bool``, skipping changes PSX itself is applying."""
    def changed(_widget: Widget, value: bool) -> object | None:
        if not getattr(widget, "_psx_updating", False):
            return slot.invoke(bool(value))
        return None
    return changed


def emit_kivy_input(widget, slot):
    def _on_text(instance, value):
        if getattr(instance, "_psx_updating", False):
            return
        slot.invoke(value)
    return _on_text


def emit_kivy_input_click(widget, slot):
    def clicked(instance, touch):
        if not instance.disabled and instance.collide_point(*touch.pos):
            slot.invoke()
        return False
    return clicked


def emit_kivy_submit(widget, slot):
    return lambda instance: slot.invoke()


def emit_kivy_textarea(widget, slot):
    def _on_text(instance, value):
        if getattr(instance, "_psx_updating", False):
            return
        slot.invoke(value)
    return _on_text


def emit_kivy_select(widget, slot):
    def changed(_widget, label):
        if getattr(widget, "_psx_updating", False):
            return
        for item_label, value in widget._psx_items:
            if item_label == label:
                slot.invoke(value)
                return
    return changed


def emit_kivy_slider(widget, slot):
    def _on_value(instance, value):
        if getattr(instance, "_psx_updating", False):
            return
        slot.invoke(float(value))
    return _on_value


# -- registries -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    """Everything the renderer needs to know about one leaf host primitive."""

    factory: Callable[[], Widget]
    validate: Callable[[Mapping[str, object]], None]
    apply: Callable[[Widget, Mapping[str, object]], None]
    updated_props: Callable[
        [Mapping[str, object], Mapping[str, object],
            frozenset[str]], dict[str, object]
    ]
    events: Mapping[str, EventDef] = field(default_factory=dict)
    on_create: Callable[[Widget], None] | None = None
    on_destroy: Callable[[Widget], None] | None = None


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    horizontal: bool
    props: frozenset[str] = _LAYOUT_PROPS


_PRIMITIVES: dict[str, PrimitiveSpec] = {}
_LAYOUTS: dict[str, LayoutSpec] = {}
_FRAGMENT_LAYOUT = LayoutSpec(horizontal=False)
_STRUCTURAL = frozenset({"Fragment", "Native"})


def register_primitive(
    name: str,
    *,
    factory: Callable[[], Widget],
    validate: Callable[[Mapping[str, object]], None],
    apply: Callable[[Widget, Mapping[str, object]], None],
    updated_props: Callable[..., dict[str, object]],
    events: Mapping[str, EventDef] | None = None,
    on_create: Callable[[Widget], None] | None = None,
    on_destroy: Callable[[Widget], None] | None = None,
    replace: bool = False,
) -> PrimitiveSpec:
    """Register a leaf host tag."""
    if name in _STRUCTURAL or name in _LAYOUTS or (name in _PRIMITIVES and not replace):
        raise ValueError(f"Primitive {name!r} is already registered.")
    spec = PrimitiveSpec(factory, validate, apply, updated_props, dict(
        events or {}), on_create, on_destroy)
    _PRIMITIVES[name] = spec
    return spec


def register_layout(
    name: str, *, horizontal: bool, props: frozenset[str] = _LAYOUT_PROPS, replace: bool = False
) -> None:
    """Register a container tag backed by a ``BoxLayout``."""
    if name in _STRUCTURAL or name in _PRIMITIVES or (name in _LAYOUTS and not replace):
        raise ValueError(f"Layout {name!r} is already registered.")
    _LAYOUTS[name] = LayoutSpec(horizontal, props)


# -- built-in tags ----------------------------------------------------------

def _text_created(widget: Widget) -> None:
    widget.bind(size=size_kivy_text)
    size_kivy_text(widget, widget.size)


def _text_destroyed(widget: Widget) -> None:
    widget.unbind(size=size_kivy_text)


register_primitive(
    "Text", factory=lambda: Label(markup=False),
    validate=validate_text_props, apply=apply_kivy_text, updated_props=updated_text_props,
    on_create=_text_created, on_destroy=_text_destroyed,
)
register_primitive(
    "Button", factory=KivyButton,
    validate=validate_button_props, apply=apply_kivy_button, updated_props=updated_button_props,
    events={"on_click": ("on_release", emit_call)},
)
register_primitive(
    "Checkbox", factory=KivyLabeledCheckBox,
    validate=validate_checkbox_props, apply=apply_kivy_checkbox, updated_props=updated_checkbox_props,
    events={"on_change": ("active", emit_active)},
)

register_primitive(
    "Input",
    factory=_kivy_input_factory,
    validate=validate_input_props,
    apply=apply_kivy_input,
    updated_props=updated_input_props,
    events={
        "on_change": ("text", emit_kivy_input),
        "on_submit": ("on_text_validate", emit_kivy_submit),
        "on_click": ("on_touch_down", emit_kivy_input_click),
    },
)
register_primitive(
    "TextArea",
    factory=_kivy_textarea_factory,
    validate=validate_textarea_props,
    apply=apply_kivy_textarea,
    updated_props=updated_textarea_props,
    events={"on_change": ("text", emit_kivy_textarea)},
)

register_primitive(
    "Slider",
    factory=_kivy_slider_factory,
    validate=validate_slider_props,
    apply=apply_kivy_slider,
    updated_props=updated_slider_props,
    events={"on_change": ("value", emit_kivy_slider)},
)
register_primitive(
    "Select", factory=Spinner,
    validate=validate_select_props,
    apply=apply_kivy_select,
    updated_props=updated_select_props,
    events={"on_change": ("text", emit_kivy_select)},
)
register_primitive(
    "Spacer", factory=Widget,
    validate=validate_spacer_props, apply=apply_kivy_spacer,
    updated_props=updated_spacer_props,
)
# -- renderer ---------------------------------------------------------------


class KivyRenderer:
    """Map portable PSX layout nodes to Kivy's native widget/layout APIs."""

    def __init__(
        self,
        *,
        sfle_constraints: LayoutConstraints | None = None,
        engine: object | None = None,
    ) -> None:
        if sfle_constraints is not None and not isinstance(sfle_constraints, LayoutConstraints):
            raise TypeError("Kivy SFLE viewport must be LayoutConstraints.")
        if sfle_constraints is None and engine is not None:
            raise ValueError("Kivy SFLE engine requires explicit viewport constraints.")
        if sfle_constraints is not None and (
            not sfle_constraints.width.definite or not sfle_constraints.height.definite
        ):
            raise RendererCapabilityError("Kivy SFLE viewport must have definite axes.")
        from psx.sfle.backend import load_layout_engine
        self._sfle_constraints = sfle_constraints
        self._sfle_engine = (engine if engine is not None else load_layout_engine()) if sfle_constraints else None
        self._sfle_backend = "kivy"
        self._psx_css_pixel_scale = self._read_css_pixel_scale()
        self._sfle_generation = 0
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations
        self._sfle_measurement_invalidations = MeasurementInvalidations()
        from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
        self._sfle_native_intrinsic_cache = NativeIntrinsicCache()
        self._sfle_prior_solver_input = None
        self._sfle_prior_solver_result = None
        self._sfle_prior_solver_engine = None
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
        self._sfle_resize_pending = None
        self._sfle_resize_event = None
        self._sfle_window_resize_event = None
        self._sfle_resize_epoch = 0
        self._sfle_resize_error: Exception | None = None
        self._sfle_textarea_event = None
        self._sfle_textarea_epoch = 0
        self._sfle_textarea_error: Exception | None = None
        self.sfle_result: LayoutResult | None = None
        self._sfle_physical_commit_error: float | None = None
        self._root: Widget | None = None
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        # "Input" stays reserved (unsupported in Kivy) so custom adapters still need replace=True.
        for component in dict.fromkeys((*_LAYOUTS, *_PRIMITIVES, "Fragment", "Flex", "Input", "Native")):
            self.adapters.register(component, self._default_adapter)
        from .divider import KivyDividerAdapter
        from .image import KivyImageAdapter
        from .switch import KivySwitchAdapter
        from .link import KivyLinkAdapter
        from .badge import KivyBadgeAdapter
        from .spinbox import KivySpinBoxAdapter
        from .scroll import KivyScrollAdapter
        from .box import KivyBoxAdapter
        from .progressbar import KivyProgressBarAdapter
        from .radio import KivyRadioAdapter, KivyRadioGroupAdapter

        self.adapters.register("Divider", KivyDividerAdapter())
        self.adapters.register("Image", KivyImageAdapter())
        self.adapters.register("Switch", KivySwitchAdapter())
        self.adapters.register("Link", KivyLinkAdapter())
        self.adapters.register("Badge", KivyBadgeAdapter())
        self.adapters.register("SpinBox", KivySpinBoxAdapter())
        self.adapters.register("Scroll", KivyScrollAdapter())
        self.adapters.register("Box", KivyBoxAdapter())
        self.adapters.register("ProgressBar", KivyProgressBarAdapter())
        self.adapters.register("Radio", KivyRadioAdapter())
        self.adapters.register("RadioGroup", KivyRadioGroupAdapter())
        if sfle_constraints is not None:
            from .flex import KivySFLEFlexAdapter
            self.adapters.register("Flex", KivySFLEFlexAdapter(), replace=True)

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
        Clock.schedule_once(
            lambda _dt: self._sfle_poll_image_resources(epoch), 0.6)

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
        if self._sfle_constraints is None:
            raise RendererCapabilityError("Kivy SFLE has not been enabled for this renderer.")
        if not isinstance(constraints, LayoutConstraints):
            raise TypeError("Kivy SFLE viewport needs LayoutConstraints.")
        if not constraints.width.definite or not constraints.height.definite:
            raise RendererCapabilityError("Kivy SFLE viewport axes must be definite.")
        self._sfle_constraints = constraints
        self._sfle_generation += 1
        if self._root is not None:
            desired = (constraints.width.value, constraints.height.value)
            if tuple(self._root.size) != desired:
                self._root.size = desired

    def _sfle_on_root_size(self, widget: Widget, size: object) -> None:
        if widget is not self._sfle_watched_widget:
            return
        width, height = size
        constraints = self._sfle_constraints
        if (width <= 0 or height <= 0 or constraints is None
                or self._sfle_mounted_root is None):
            return
        if (constraints.width.value, constraints.height.value) == (width, height):
            return
        self._sfle_resize_pending = (width, height)
        if self._sfle_resize_event is None:
            epoch = self._sfle_resize_epoch
            self._sfle_resize_event = Clock.schedule_once(
                lambda _dt: self._sfle_flush_viewport_resize(epoch), 0,
            )

    def _sfle_on_window_resize(self, window, width: float, height: float) -> None:
        """Coalesce SDL/Cocoa resize events without mutating native geometry.

        The callback arguments and Window.size can describe different resize
        epochs on macOS Retina displays. Do not mix them, or dispatch root
        size changes while SDL is still delivering on_resize.
        """
        root = self._sfle_watched_widget
        if root is None or root.parent is not window:
            return
        if self._sfle_window_resize_event is not None:
            return
        epoch = self._sfle_resize_epoch
        self._sfle_window_resize_event = Clock.schedule_once(
            lambda _dt: self._sfle_flush_window_resize(window, epoch), 0,
        )

    def _sfle_flush_window_resize(self, window, epoch: int) -> None:
        self._sfle_window_resize_event = None
        root = self._sfle_watched_widget
        if (epoch != self._sfle_resize_epoch or root is None
                or root.parent is not window):
            return
        # Window.size is Kivy's current drawable-space geometry. The
        # on_resize payload may still be in Cocoa point coordinates.
        drawable = getattr(window, "size", None)
        if (drawable is None or len(drawable) != 2
                or any(not isinstance(value, (int, float)) or value <= 0
                       for value in drawable)):
            return
        new_size = tuple(drawable)
        if tuple(root.size) != new_size:
            root.size = new_size

        # Window resize already runs in a Clock callback, outside Cocoa's
        # native on_resize dispatch. A root-size notification schedules a
        # *second* Clock callback; that leaves the old Cinnamon layout
        # visible for an extra frame, particularly apparent on the Y axis
        # when ScrollView is also updating its vertical bounds. Reuse this
        # same UI tick for the committed viewport and cancel the redundant
        # root-size observer callback. Preserve the observer path for
        # synthetic/standalone root resizes that have no Window event.
        mounted = getattr(self, "_sfle_mounted_root", None)
        constraints = getattr(self, "_sfle_constraints", None)
        if (mounted is None or mounted.disposed or constraints is None
                or (constraints.width.value, constraints.height.value) == new_size):
            return
        if self._sfle_resize_event is not None:
            self._sfle_resize_event.cancel()
            self._sfle_resize_event = None
        self._sfle_resize_pending = new_size
        self._sfle_flush_viewport_resize(epoch)

    def _sfle_flush_viewport_resize(self, epoch: int) -> None:
        self._sfle_resize_event = None
        if epoch != self._sfle_resize_epoch or self._sfle_mounted_root is None:
            return
        size = self._sfle_resize_pending
        self._sfle_resize_pending = None
        if size is None:
            return
        root = self._sfle_mounted_root
        if root.disposed:
            return
        # Drop an obsolete size notification if another native event has
        # already resized the mounted root before this Clock callback.
        size = tuple(root.native_handle().widget.size)
        from psx.sfle.model import AvailableSize
        try:
            self.set_sfle_constraints(LayoutConstraints(
                AvailableSize(size[0], True), AvailableSize(size[1], True),
            ))
            self.commit_layout(root)
            self._sfle_resize_error = None
        except Exception as exc:
            self._sfle_resize_error = exc
            import logging
            logging.getLogger(__name__).exception("Kivy SFLE viewport resize failed")

    def _sfle_on_textarea_changed(self, widget: Widget, _text: str) -> None:
        if (self._sfle_constraints is None or self._sfle_mounted_root is None
                or self._sfle_in_commit or getattr(widget, "_psx_updating", False)
                or self._sfle_textarea_event is not None):
            return
        epoch = self._sfle_textarea_epoch
        self._sfle_textarea_event = Clock.schedule_once(
            lambda _dt: self._sfle_flush_textarea_changed(epoch), 0,
        )

    def _sfle_flush_textarea_changed(self, epoch: int) -> None:
        self._sfle_textarea_event = None
        if epoch != self._sfle_textarea_epoch or self._sfle_mounted_root is None:
            return
        root = self._sfle_mounted_root
        if root.disposed:
            return
        try:
            self._sfle_measurement_invalidations.request("content")
            self.commit_layout(root)
            self._sfle_textarea_error = None
        except Exception as exc:
            self._sfle_textarea_error = exc
            import logging
            logging.getLogger(__name__).exception("Kivy TextArea SFLE remeasurement failed")

    @staticmethod
    def _read_css_pixel_scale() -> float:
        from kivy.core.window import Window
        from psx.sfle.kivy_display_scale import KivyDisplayScale
        # Before Cocoa/SDL2 creates its window, there is no backing-store
        # ratio to sample. Defer to the first mounted native layout pass.
        if Window is None:
            return 1.0
        observed = KivyDisplayScale.from_window(Window)
        chosen = observed.css_scale
        if abs(observed.x - observed.y) > 0.02:
            from kivy.logger import Logger
            Logger.warning(
                "PSX Retina: Window.size/system_size differ by axis: "
                f"{observed.snapshot()}; CSS scale={chosen:g}. "
                "Preserving startup; capture this report on the device."
            )
        return chosen

    def commit_layout(self, root: object) -> None:
        if self._sfle_constraints is None:
            return
        current_scale = self._read_css_pixel_scale()
        if current_scale != self._psx_css_pixel_scale:
            self._psx_css_pixel_scale = current_scale
            self._sfle_generation += 1
            # Retain widget identity while refreshing native glyph metrics
            # and the canvas after moving between Retina and standard screens.
            pending = [root]
            while pending:
                mounted = pending.pop()
                if mounted.handle is not None:
                    self._scale_component_font(mounted.handle)
                    computed = getattr(mounted.node, "css_computed", None)
                    if computed is not None:
                        self.apply_css(mounted.handle, computed)
                pending.extend(mounted.children)
            self._sfle_measurement_invalidations.request("font")
        from psx.sfle.native_grid_bridge import is_mounted_native_grid_root, commit_native_grid
        from psx.sfle.grid_native_commit import GridCommitBackend
        from psx.sfle.kivy_layout_bridge import commit_kivy_sfle
        # Native style/texture signals can arrive while measuring. Retry a
        # bounded number of times using the latest semantic epoch; never
        # publish a transaction rejected for stale measurements.
        from psx.sfle.errors import SFLEError
        for attempt in range(3):
            try:
                if is_mounted_native_grid_root(root):
                    commit_native_grid(self, root, backend=GridCommitBackend.KIVY)
                else:
                    commit_kivy_sfle(self, root)
                break
            except SFLEError as error:
                if ("Stale semantic invalidation" not in str(error)
                        or attempt == 2):
                    raise
        self._sfle_measurement_invalidations.acknowledge(
            self._sfle_measurement_invalidations.epoch)

        self._sfle_textarea_epoch += 1
        if self._sfle_textarea_event is not None:
            self._sfle_textarea_event.cancel()
            self._sfle_textarea_event = None
        widget = root.native_handle().widget
        if widget is not self._sfle_watched_widget:
            if self._sfle_watched_widget is not None:
                self._sfle_watched_widget.unbind(size=self._sfle_on_root_size)
            self._sfle_resize_epoch += 1
            self._sfle_resize_pending = None
            if self._sfle_resize_event is not None:
                self._sfle_resize_event.cancel()
                self._sfle_resize_event = None
            if self._sfle_window_resize_event is not None:
                self._sfle_window_resize_event.cancel()
                self._sfle_window_resize_event = None
            widget.bind(size=self._sfle_on_root_size)
            self._sfle_watched_widget = widget
        from kivy.core.window import Window
        if not getattr(self, "_sfle_window_bound", False):
            Window.bind(on_resize=self._sfle_on_window_resize)
            self._sfle_window_bound = True
        self._sfle_mounted_root = root
        self._sfle_schedule_image_poll()

    def invalidate_layout(self) -> None:
        self._sfle_invalidation_lifetime += 1
        self._sfle_invalidation_scheduled = False
        self._sfle_measurement_invalidations.cancel()
        self._sfle_native_intrinsic_cache.clear()
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
        self._sfle_image_resource_watch.clear()
        self._sfle_resource_poll_scheduled = False
        self._sfle_mounted_root = None
        cursor_manager = getattr(self, "_psx_css_cursor_manager", None)
        if cursor_manager is not None:
            cursor_manager.close()
            self._psx_css_cursor_manager = None
        if self._sfle_constraints is not None:
            self._sfle_generation += 1
            self._sfle_resize_epoch += 1
            self._sfle_textarea_epoch += 1
            if self._sfle_textarea_event is not None:
                self._sfle_textarea_event.cancel()
                self._sfle_textarea_event = None
            self._sfle_textarea_error = None
            self._sfle_mounted_root = None
            self._sfle_resize_pending = None
            if self._sfle_resize_event is not None:
                self._sfle_resize_event.cancel()
                self._sfle_resize_event = None
            if self._sfle_window_resize_event is not None:
                self._sfle_window_resize_event.cancel()
                self._sfle_window_resize_event = None
            if self._sfle_watched_widget is not None:
                self._sfle_watched_widget.unbind(size=self._sfle_on_root_size)
                self._sfle_watched_widget = None
            if getattr(self, "_sfle_window_bound", False):
                from kivy.core.window import Window
                Window.unbind(on_resize=self._sfle_on_window_resize)
                self._sfle_window_bound = False
            self.sfle_result = None
            self._sfle_physical_commit_error = None

    def _adapter_for(self, key: object):
        return self.adapters.get(key) or self._default_adapter

    # -- create -----------------------------------------------------------

    def create(self, node: VNode, parent: object | None) -> KivyHandle:
        if self._sfle_constraints is not None:
            # Only certified widget types join the native SFLE tree until
            # the complete G2 registry/backend matrix is implemented.
            if node.kind not in (NodeKind.HOST, NodeKind.NATIVE):
                raise RendererCapabilityError("Native SFLE requires a host or Native layout participant.")
            # An unregistered custom host or a Native declaration without a
            # strict SFLE port must fail *before* its factory mutates the GUI.
            port = external_port_for(node, self)
            if port is None and node.type not in ("Flex", "Grid", "GridItem") and node.type not in FORMATTING_TAGS:
                native_leaf_needs_measurement(node, backend="kivy")
            if node.type not in ("Flex", "Grid", "GridItem"):
                node = VNode(node.kind, node.type, node.key,
                             {key: val for key, val in node.props.items()
                              if key not in FLEX_ITEM_PROPS}, node.children)
        # All adapter kinds, including custom ProgressBar adapters, must
        # advertise the same intrinsic port before native measurement.
        handle = self._adapter_for(adapter_key(node)).create(self, node, parent)
        self._scale_component_font(handle)
        if self._sfle_constraints is not None and node.type in (
            "Input", "Checkbox", "ProgressBar",
        ):
            handle.widget._psx_sfle_intrinsic_kind = node.type
        return handle

    def _scale_component_font(self, handle: object) -> None:
        target = _handle(handle)
        if target.node_type == "Badge":
            widget = target.widget
            if widget._psx_badge_pixel_scale != self._psx_css_pixel_scale:
                from psx.renderers.kivy.badge import KivyBadgeAdapter
                widget._psx_badge_pixel_scale = self._psx_css_pixel_scale
                KivyBadgeAdapter._apply(widget, target.props)
            return
        if (target.node_type in ("Text", "Button", "Input", "TextArea", "Select", "Link")
                and "font_size" in target.props and hasattr(target.widget, "font_size")):
            scaled = target.props["font_size"] * self._psx_css_pixel_scale
            target.widget.font_size = scaled
            baseline = getattr(target.widget, "_psx_css_default_typography", None)
            if baseline is not None and "font_size" in baseline:
                baseline["font_size"] = scaled

    def _adapter_create(self, node: VNode, parent: object | None) -> KivyHandle:
        if node.kind is NodeKind.HOST and node.type in FORMATTING_TAGS:
            if self._sfle_constraints is None or node.props.get("display") not in ("block", "inline"):
                raise RendererCapabilityError(
                    "Kivy div requires an enabled Cinnamon Block viewport.")
            if node.type == "label":
                from kivy.uix.textinput import TextInput

                class NativeLabelHost(Widget):
                    def focus_nested_input(self):
                        for descendant in self.walk():
                            if isinstance(descendant, TextInput) and not descendant.disabled:
                                descendant.focus = True
                                return True
                        return False

                    def on_touch_down(self, touch):
                        if self.collide_point(*touch.pos):
                            self.focus_nested_input()
                        return super().on_touch_down(touch)

                native_widget = NativeLabelHost(size_hint=(None, None))
            else:
                native_widget = Widget(size_hint=(None, None))
            handle = KivyHandle(node.type, native_widget, dict(node.props))
            if parent is None:
                viewport = self._sfle_constraints
                if (viewport.width.value is None or viewport.height.value is None
                        or not viewport.width.definite or not viewport.height.definite):
                    raise RendererCapabilityError(
                        "Kivy Block root requires definite viewport dimensions.")
                handle.widget.size = (viewport.width.value, viewport.height.value)
                # The native root is the viewport, while its CSS flow box
                # may have intrinsic content height. Kivy child coordinates
                # must be projected against the physical viewport height.
                handle.widget._psx_sfle_semantic_viewport = True
                self._root = handle.widget
            return handle
        if node.kind is NodeKind.HOST and node.type in ("Grid", "GridItem"):
            if self._sfle_constraints is None:
                raise RendererCapabilityError(
                    f"Native SFLE {self._sfle_backend} SFLE geometry not certified for {node.type!r}.")
            if node.type == "GridItem" and (parent is None or _handle(parent).node_type != "Grid"):
                raise RendererCapabilityError("GridItem must be a direct child of a mounted Grid.")
            if node.type == "Grid" and parent is not None and _handle(parent).node_type not in ("GridItem", "Flex", "div", "main", "section", "article", "header", "footer"):
                raise RendererCapabilityError("Grid must be inside a supported Cinnamon layout container.")
            handle = KivyHandle(node.type, Widget(size_hint=(None, None)), dict(node.props))
            if parent is None:
                self._root = handle.widget
            return handle
        if node.kind is NodeKind.HOST and node.type == "Flex":
            raise RendererCapabilityError(
                "Flex requires the Native SFLE SFLE geometry adapter for Kivy; "
                "native fallback layout is forbidden.")
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _handle(
                parent).widget if parent is not None else None
            handle = self._native(node, native_parent)
        else:
            handle = self._create_local(node)
        if self._sfle_constraints is not None:
            if handle.node_type in ("Input", "Checkbox", "ProgressBar"):
                handle.widget._psx_sfle_intrinsic_kind = handle.node_type
            # Widget itself must not accept an external Kivy layout's size hints.
            handle.widget.size_hint = (None, None)
            handle.widget.pos_hint = {}
            if handle.node_type == "TextArea":
                handle.widget.bind(text=self._sfle_on_textarea_changed)
        if parent is None:
            self._root = handle.widget
        return handle

    @staticmethod
    def _create_local(node: VNode) -> KivyHandle:
        layout = _layout_of(node)
        if layout is not None:
            widget = BoxLayout(
                orientation="horizontal" if layout.horizontal else "vertical")
            _apply_layout(widget, node.props)
            return KivyHandle(node.type, widget, dict(node.props))
        spec = _PRIMITIVES.get(
            node.type) if node.kind is NodeKind.HOST else None
        if spec is None:
            raise RendererCapabilityError(
                f"Kivy does not support host primitive {node.type!r}.")
        widget = spec.factory()
        spec.apply(widget, node.props)
        if spec.on_create is not None:
            spec.on_create(widget)
        return KivyHandle(node.type, widget, dict(node.props))

    def apply_css(self, handle: object, computed: object) -> None:
        """Paint native semantic backgrounds with one owned canvas instruction."""
        from psx.css.native_paint import background_rgba
        from kivy.graphics import Color, InstructionGroup, Rectangle

        target = _handle(handle)
        pixel_scale = getattr(self, "_psx_css_pixel_scale", 1.0)

        # CSS cursor is paint-only. Kivy's widgets have no individual OS
        # cursor, so the renderer owns one Window mouse_pos listener rather
        # than creating a global binding for every styled native widget.
        cursor_value = (
            computed.properties.get("cursor") if computed is not None
            and "cursor" in computed.specified else None
        )
        cursor_manager = getattr(self, "_psx_css_cursor_manager", None)
        from psx.css.cursor import KIVY_CURSOR_SHAPES
        if cursor_value in KIVY_CURSOR_SHAPES and cursor_manager is None:
            from kivy.core.window import Window
            from .css_cursor import KivyCssCursorManager
            cursor_manager = KivyCssCursorManager(Window)
            self._psx_css_cursor_manager = cursor_manager
        if cursor_manager is not None and (
            cursor_value in KIVY_CURSOR_SHAPES
            or target.widget in cursor_manager.styles
        ):
            cursor_manager.set_style(target.widget, cursor_value)

        # Apply one owned stroke to both HTML-like boxes and PascalCase
        # controls, before the typography branches return.
        if target.node_type in ("Text", "Button", "Input", "TextArea", "Checkbox", "Radio", "Select", "Link", "Badge"):
            from psx.css.native_paint import native_border_paint, native_border_radius, inset_rounded_border_box
            from kivy.graphics import Line
            stroke = native_border_paint(computed, alpha=True)
            radius = native_border_radius(computed) * pixel_scale
            widget = target.widget
            existing_border = getattr(widget, "_psx_css_control_stroke", None)
            if stroke is None:
                if existing_border is not None:
                    group, redraw, _, _ = existing_border
                    widget.unbind(pos=redraw, size=redraw)
                    widget.canvas.after.remove(group)
                    del widget._psx_css_control_stroke
                    del widget._psx_css_stroke_radius
            elif existing_border is None:
                width, rgba = stroke
                group = InstructionGroup()
                paint = Color(*rgba)
                line = Line(
                    width=width * pixel_scale * _KIVY_LINE_RASTER_FACTOR,
                    force_custom_drawing_method=True,
                )
                line.rounded_rectangle = inset_rounded_border_box(
                    widget.x, widget.y, widget.width, widget.height,
                    radius, width * pixel_scale,
                )
                group.add(paint)
                group.add(line)
                def redraw(instance, _):
                    r = widget._psx_css_stroke_radius
                    line.rounded_rectangle = inset_rounded_border_box(
                        instance.x, instance.y, instance.width,
                        instance.height, r, line.width / _KIVY_LINE_RASTER_FACTOR,
                    )
                widget._psx_css_stroke_radius = radius
                widget.canvas.after.add(group)
                widget.bind(pos=redraw, size=redraw)
                widget._psx_css_control_stroke = (group, redraw, paint, line)
            else:
                _, _, paint, line = existing_border
                line.width, paint.rgba = stroke[0] * pixel_scale * _KIVY_LINE_RASTER_FACTOR, stroke[1]
                widget._psx_css_stroke_radius = radius
                line.rounded_rectangle = inset_rounded_border_box(
                    widget.x, widget.y, widget.width, widget.height,
                    radius, stroke[0] * pixel_scale,
                )
        if target.node_type in (
            "Text", "Button", "Input", "TextArea", "Checkbox", "Radio",
            "Select", "Link", "Badge",
        ):
            # Qt applies authored CSS edges individually to controls.
            # A single rounded_rectangle would invent strokes on untouched
            # edges, so retain one native Line for every specified CSS side.
            from kivy.graphics import Line
            from psx.css.native_paint import (
                native_border_radius, native_side_border_paint,
                rounded_side_stroke_points,
            )
            widget = target.widget
            radius = native_border_radius(computed) * pixel_scale
            # A uniform CSS border is already painted by the full rounded
            # stroke above. Painting its four sides again doubles the width.
            sides = () if native_border_paint(computed, alpha=True) is not None else tuple(
                (side, thickness * pixel_scale, color)
                for side, thickness, color in native_side_border_paint(computed)
            )
            existing = getattr(widget, "_psx_css_control_side_strokes", None)
            if existing is not None and existing[2] != sides:
                group, redraw, _old_sides, _lines = existing
                widget.unbind(pos=redraw, size=redraw)
                widget.canvas.after.remove(group)
                del widget._psx_css_control_side_strokes
                existing = None
            widget._psx_css_control_side_radius = radius
            if sides and existing is None:
                group = InstructionGroup()
                lines = []
                for side, thickness, color in sides:
                    group.add(Color(*color))
                    line = Line(
                        width=thickness * _KIVY_LINE_RASTER_FACTOR,
                        force_custom_drawing_method=True,
                    )
                    group.add(line)
                    lines.append((side, thickness, line))

                def redraw(instance, _value):
                    x, y = instance.pos
                    width, height = instance.size
                    for side, thickness, line in lines:
                        points = rounded_side_stroke_points(
                            side, width, height,
                            instance._psx_css_control_side_radius, thickness,
                        )
                        line.points = tuple(
                            value + (x if index % 2 == 0 else y)
                            for index, value in enumerate(points)
                        )

                widget.canvas.after.add(group)
                widget.bind(pos=redraw, size=redraw)
                widget._psx_css_control_side_strokes = (
                    group, redraw, sides, lines,
                )
            if sides:
                widget._psx_css_control_side_strokes[1](widget, None)
        if target.node_type in ("Checkbox", "Radio"):
            # Keep native indicators and their input state intact. Authored
            # background paint is confined to the control host behind the
            # checkbox/radio content rather than replacing its native skin.
            from kivy.graphics import RoundedRectangle
            widget = target.widget
            rgba = background_rgba(computed)
            painted = getattr(widget, "_psx_css_check_background", None)
            if rgba is None:
                if painted is not None:
                    group, redraw, _, _ = painted
                    widget.unbind(pos=redraw, size=redraw)
                    widget.canvas.before.remove(group)
                    del widget._psx_css_check_background
            elif painted is None:
                group = InstructionGroup()
                color = Color(*rgba)
                radius = native_border_radius(computed) * pixel_scale
                rectangle = RoundedRectangle(
                    pos=widget.pos, size=widget.size, radius=[radius] * 4,
                )
                group.add(color)
                group.add(rectangle)

                def redraw(instance, _):
                    rectangle.pos = instance.pos
                    rectangle.size = instance.size

                widget.canvas.before.add(group)
                widget.bind(pos=redraw, size=redraw)
                widget._psx_css_check_background = (
                    group, redraw, color, rectangle,
                )
            else:
                _, _, color, rectangle = painted
                color.rgba = rgba
                rectangle.radius = [
                    native_border_radius(computed) * pixel_scale
                ] * 4
        if target.node_type == "Text":
            from psx.css.native_paint import native_text_typography
            from psx.renderers.components.text import apply_kivy_text
            if not hasattr(target.widget, "_psx_css_default_font_name"):
                target.widget._psx_css_default_font_name = target.widget.font_name
            apply_kivy_text(target.widget, target.props)
            self._scale_component_font(target)
            styles = native_text_typography(computed, alpha=True, line_height=True)
            target.widget.font_name = target.widget._psx_css_default_font_name
            if "font-family" in styles:
                target.widget.font_name = styles["font-family"]
            if "font-size" in styles:
                target.widget.font_size = styles["font-size"] * pixel_scale
            if "font-weight" in styles:
                target.widget.bold = styles["font-weight"] >= 600
            if "text-align" in styles:
                target.widget.halign = styles["text-align"]
            if "color" in styles:
                target.widget.color = styles["color"]
                if hasattr(target.widget, "disabled_color"):
                    target.widget.disabled_color = styles["color"]
            target.widget.line_height = (
                styles["line-height"] * pixel_scale / target.widget.font_size
                if "line-height" in styles else target.widget.property("line_height").defaultvalue
            )
            if self._sfle_constraints is not None:
                keys = ("font-family", "font-size", "font-weight", "line-height")
                revision = (target.props.get("value"),
                            tuple((key, styles.get(key)) for key in keys))
                if getattr(target.widget, "_psx_css_font_revision", None) != revision:
                    target.widget._psx_css_font_revision = revision
                    self.request_sfle_invalidation(
                        "font", widget_id=id(target.widget)
                    )
            return
        if target.node_type == "Badge":
            from psx.css.native_paint import native_text_typography
            styles = native_text_typography(computed, alpha=True)
            widget = target.widget
            if not hasattr(widget, "_psx_css_original_foreground"):
                widget._psx_css_original_foreground = tuple(widget.color)
            widget.color = styles.get("color", widget._psx_css_original_foreground)
            return
        if target.node_type == "Radio":
            from psx.css.native_paint import native_text_typography
            styles = native_text_typography(computed, alpha=True)
            widget = target.widget
            label = getattr(widget, "_psx_label", None)
            if label is None:
                raise ValueError("Kivy Radio foreground requires a native text label.")
            if not hasattr(label, "_psx_css_original_foreground"):
                label._psx_css_original_foreground = tuple(label.color)
            label.color = styles.get("color", label._psx_css_original_foreground)
            return
        if target.node_type in ("Input", "TextArea"):
            # TextInput owns a normal and a focused background texture. Both
            # must be suppressed while an authored CSS color is active, or the
            # native focused skin can paint over the CSS surface.
            from kivy.graphics import RoundedRectangle
            widget = target.widget
            rgba = background_rgba(computed)
            painted = getattr(widget, "_psx_css_input_background", None)
            if rgba is None:
                if painted is not None:
                    group, redraw, _, _, normal, active, tint = painted
                    widget.unbind(pos=redraw, size=redraw)
                    widget.canvas.before.remove(group)
                    widget.background_normal = normal
                    widget.background_active = active
                    widget.background_color = tint
                    del widget._psx_css_input_background
            elif painted is None:
                group = InstructionGroup()
                color = Color(*rgba)
                radius = native_border_radius(computed) * pixel_scale
                shape = RoundedRectangle(
                    pos=widget.pos, size=widget.size, radius=[radius] * 4,
                )
                group.add(color)
                group.add(shape)
                original = (
                    widget.background_normal, widget.background_active,
                    tuple(widget.background_color),
                )
                widget.background_normal = ""
                widget.background_active = ""
                widget.background_color = (0, 0, 0, 0)
                def redraw(instance, _):
                    shape.pos = instance.pos
                    shape.size = instance.size
                widget.canvas.before.add(group)
                widget.bind(pos=redraw, size=redraw)
                widget._psx_css_input_background = (
                    group, redraw, color, shape, *original,
                )
            else:
                _, _, color, shape, _, _, _ = painted
                color.rgba = rgba
                shape.radius = [native_border_radius(computed) * pixel_scale] * 4
        if target.node_type in ("Button", "Select", "Link"):
            # Kivy Button/Spinner skins otherwise obscure authored CSS backgrounds.
            from psx.css.native_paint import native_border_radius
            from kivy.graphics import RoundedRectangle
            widget = target.widget
            rgba = background_rgba(computed)
            # HTML/CSS buttons default to a transparent background when
            # no background is authored. Kivy's bundled normal texture is a
            # solid gray skin; leaving it in place creates phantom backgrounds
            # on unselected navigation buttons.
            if rgba is None and computed is not None:
                rgba = (0.0, 0.0, 0.0, 0.0)
            painted = getattr(widget, "_psx_css_button_background", None)
            if rgba is None:
                if painted is not None:
                    group, redraw, _, _, original_normal, original_down, original_color = painted
                    widget.unbind(pos=redraw, size=redraw)
                    widget.canvas.before.remove(group)
                    widget.background_normal = original_normal
                    widget.background_down = original_down
                    widget.background_color = original_color
                    del widget._psx_css_button_background
            elif painted is None:
                group = InstructionGroup()
                color = Color(*rgba)
                radius = native_border_radius(computed) * pixel_scale
                shape = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius] * 4)
                group.add(color)
                group.add(shape)
                def redraw(instance, _):
                    shape.pos = instance.pos
                    shape.size = instance.size
                original = (widget.background_normal, widget.background_down,
                            tuple(widget.background_color))
                widget.background_normal = ""
                widget.background_down = ""
                widget.background_color = (0, 0, 0, 0)
                widget.canvas.before.add(group)
                widget.bind(pos=redraw, size=redraw)
                widget._psx_css_button_background = (group, redraw, color, shape, *original)
            else:
                _, _, color, shape, _, _, _ = painted
                color.rgba = rgba
                shape.radius = [native_border_radius(computed) * pixel_scale] * 4
        if target.node_type in ("Button", "Input", "TextArea", "Select", "Link"):
            from psx.css.native_paint import native_text_typography
            styles = native_text_typography(computed, alpha=True,
                                            line_height=target.node_type == "Button")
            widget = target.widget
            if not hasattr(widget, "_psx_css_default_typography"):
                widget._psx_css_default_typography = {
                    key: getattr(widget, key) for key in
                    ("font_name", "font_size", "bold", "halign", "line_height", "color", "foreground_color", "disabled_color", "disabled_foreground_color")
                    if hasattr(widget, key)
                }
            # The portable Button font size is a live component prop. A CSS
            # projection must not restore the value cached at the first mount
            # after keyed reconciliation has updated that prop.
            if target.node_type == "Button":
                widget._psx_css_default_typography["font_size"] = target.props.get(
                    "font_size", widget._psx_css_default_typography["font_size"] / pixel_scale
                ) * pixel_scale
            for key, value in widget._psx_css_default_typography.items():
                setattr(widget, key, value)
            if "font-family" in styles and hasattr(widget, "font_name"):
                widget.font_name = styles["font-family"]
            if "font-size" in styles:
                widget.font_size = styles["font-size"] * pixel_scale
            if "font-weight" in styles:
                if not hasattr(widget, "bold"):
                    raise ValueError(f"Kivy {target.node_type} does not expose native font-weight.")
                widget.bold = styles["font-weight"] >= 600
            if target.node_type == "Button" and computed is not None and (
                "padding" in computed.specified or any(
                    f"padding-{side}" in computed.specified
                    for side in ("top", "right", "bottom", "left")
                )
            ):
                from psx.sfle.lengths import LengthKind
                if not hasattr(widget, "_psx_css_original_padding"):
                    widget._psx_css_original_padding = tuple(widget.padding)
                values = []
                for side in ("left", "top", "right", "bottom"):
                    length = computed.properties[f"padding-{side}"]
                    if length.kind is not LengthKind.PX:
                        raise ValueError("Kivy native Button padding requires pixel lengths.")
                    values.append(float(length.value) * pixel_scale)
                widget.padding = values
            elif target.node_type == "Button" and hasattr(widget, "_psx_css_original_padding"):
                widget.padding = widget._psx_css_original_padding
            if "text-align" in styles:
                if not hasattr(widget, "halign"):
                    raise ValueError(f"Kivy {target.node_type} does not support text-align.")
                widget.halign = styles["text-align"]
                if target.node_type in ("Button", "Select", "Link"):
                    # Kivy Label.halign has no visible effect when text_size
                    # follows the glyph texture instead of the native box.
                    # Bind only while CSS owns alignment; Cinnamon continues
                    # to own the outer rectangle.
                    if not hasattr(widget, "_psx_css_text_align_resize"):
                        widget._psx_css_original_text_size = tuple(widget.text_size)

                        def align_resize(instance, _value):
                            padding = instance.padding
                            horizontal = float(padding[0]) + float(padding[2])
                            instance.text_size = (
                                max(0.0, float(instance.width) - horizontal), None
                            )

                        widget._psx_css_text_align_resize = align_resize
                        widget.bind(size=align_resize)
                    widget._psx_css_text_align_resize(widget, None)
            elif target.node_type in ("Button", "Select", "Link"):
                resize = getattr(widget, "_psx_css_text_align_resize", None)
                if resize is not None:
                    widget.unbind(size=resize)
                    widget.text_size = widget._psx_css_original_text_size
                    del widget._psx_css_text_align_resize
                    del widget._psx_css_original_text_size
            if "line-height" in styles:
                if not hasattr(widget, "line_height"):
                    raise ValueError(f"Kivy {target.node_type} does not support line-height.")
                widget.line_height = styles["line-height"] * pixel_scale / widget.font_size
            if "color" in styles:
                if target.node_type in ("Input", "TextArea") and hasattr(widget, "foreground_color"):
                    widget.foreground_color = styles["color"]
                    if hasattr(widget, "disabled_foreground_color"):
                        widget.disabled_foreground_color = styles["color"]
                elif hasattr(widget, "color"):
                    widget.color = styles["color"]
                    if hasattr(widget, "disabled_color"):
                        widget.disabled_color = styles["color"]
                else:
                    raise ValueError(f"Kivy {target.node_type} has no foreground paint property.")
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
        widget = target.widget
        rgba = background_rgba(computed)
        from psx.css.native_paint import (
            border_rgba, native_border_radius, native_side_border_paint, inset_rounded_border_box,
            rounded_side_stroke_points,
        )
        radius = native_border_radius(computed) * pixel_scale
        from psx.sfle.lengths import Length, LengthKind
        from kivy.graphics import Line
        # Uniform borders own one closed stroke. Per-side instructions are
        # reserved for asymmetric edges; otherwise Retina draws each twice.
        side_styles = (() if border_rgba(computed) is not None else
                       tuple((side, thickness * pixel_scale, color)
                             for side, thickness, color in native_side_border_paint(computed)))
        old_side = getattr(widget, "_psx_css_side_strokes", None)
        if old_side is not None and old_side[2] != side_styles:
            group, redraw, _styles, _lines = old_side
            widget.unbind(pos=redraw, size=redraw)
            widget.canvas.after.remove(group)
            del widget._psx_css_side_strokes
            old_side = None
        widget._psx_css_side_radius = radius
        if side_styles and old_side is None:
            group = InstructionGroup()
            lines = []
            for side, thickness, color in side_styles:
                group.add(Color(*color))
                line = Line(
                    width=thickness * _KIVY_LINE_RASTER_FACTOR,
                    force_custom_drawing_method=True,
                )
                group.add(line)
                lines.append((side, thickness, line))

            def redraw_side(instance, _value):
                x, y = instance.pos
                w, h = instance.size
                for side, thickness, line in lines:
                    points = rounded_side_stroke_points(
                        side, w, h, widget._psx_css_side_radius, thickness,
                    )
                    line.points = tuple(
                        coordinate + (x if index % 2 == 0 else y)
                        for index, coordinate in enumerate(points)
                    )

            widget.canvas.after.add(group)
            widget.bind(pos=redraw_side, size=redraw_side)
            widget._psx_css_side_strokes = (group, redraw_side, side_styles, lines)
        if side_styles:
            widget._psx_css_side_strokes[1](widget, None)

        border = border_rgba(computed)
        thickness = computed.properties["border-width"] if computed is not None else None
        if border is not None:
            if not isinstance(thickness, Length) or thickness.kind != LengthKind.PX:
                raise ValueError("Kivy CSS border paint requires a pixel width.")
        stroke_width = float(thickness.value) * pixel_scale if border is not None else 0.0
        old_stroke = getattr(widget, "_psx_css_stroke", None)
        if border is None or stroke_width <= 0:
            if old_stroke is not None:
                stroke_group, stroke_redraw, _, _ = old_stroke
                widget.unbind(pos=stroke_redraw, size=stroke_redraw)
                widget.canvas.after.remove(stroke_group)
                del widget._psx_css_stroke
        elif old_stroke is None:
            stroke_group = InstructionGroup()
            stroke_color = Color(*border)
            stroke_line = Line(
                rounded_rectangle=inset_rounded_border_box(
                    widget.x, widget.y, widget.width, widget.height,
                    radius, stroke_width,
                ),
                width=stroke_width * _KIVY_LINE_RASTER_FACTOR,
                force_custom_drawing_method=True,
            )
            stroke_group.add(stroke_color)
            stroke_group.add(stroke_line)
            def stroke_redraw(instance, _value):
                stroke_line.rounded_rectangle = inset_rounded_border_box(
                    instance.x, instance.y, instance.width, instance.height,
                    widget._psx_css_semantic_radius,
                    stroke_line.width / _KIVY_LINE_RASTER_FACTOR,
                )
            widget._psx_css_semantic_radius = radius
            widget.canvas.after.add(stroke_group)
            widget.bind(pos=stroke_redraw, size=stroke_redraw)
            widget._psx_css_stroke = (stroke_group, stroke_redraw, stroke_color, stroke_line)
        else:
            _, _, stroke_color, stroke_line = old_stroke
            stroke_color.rgba = border
            stroke_line.width = stroke_width * _KIVY_LINE_RASTER_FACTOR
            widget._psx_css_semantic_radius = radius
            stroke_line.rounded_rectangle = inset_rounded_border_box(
                widget.x, widget.y, widget.width, widget.height,
                radius, stroke_width,
            )
        existing = getattr(widget, "_psx_css_paint", None)
        if rgba is None:
            if existing is not None:
                group, redraw, _color = existing
                widget.unbind(pos=redraw, size=redraw)
                widget.canvas.before.remove(group)
                del widget._psx_css_paint
                del widget._psx_css_paint_rect
            return
        if existing is None:
            group = InstructionGroup()
            color = Color(*rgba)
            from kivy.graphics import RoundedRectangle
            rectangle = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius] * 4)
            group.add(color)
            group.add(rectangle)
            def redraw(instance, _value):
                rectangle.pos = instance.pos
                rectangle.size = instance.size
            widget.canvas.before.add(group)
            widget.bind(pos=redraw, size=redraw)
            widget._psx_css_paint = (group, redraw, color)
            widget._psx_css_paint_rect = rectangle
        else:
            _group, _redraw, color = existing
            color.rgba = rgba
            widget._psx_css_paint_rect.radius = [radius] * 4

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        if self._sfle_constraints is not None and _handle(handle).node_type != "Flex":
            changed = {key: val for key, val in changed.items() if key not in FLEX_ITEM_PROPS}
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
        spec = _spec_for(target)
        if spec is not None:
            props = spec.updated_props(target.props, changed, removed)
            spec.apply(target.widget, props)
            target.props = props
            self._scale_component_font(target)
            # Component props are the baseline for CSS, not a snapshot of the
            # first mount. Refresh only fields explicitly controlled by the
            # component; leave CSS-owned fields for the projection/reset path.
            baseline = getattr(target.widget, "_psx_css_default_typography", None)
            if baseline is not None and "font_size" in baseline and "font_size" in changed:
                baseline["font_size"] = target.widget.font_size
            return
        if removed or not changed.keys() <= _LAYOUT_PROPS:
            unsupported = set(removed) | (set(changed) - _LAYOUT_PROPS)
            raise RendererCapabilityError(
                f"Unsupported Kivy props: {', '.join(sorted(unsupported))}")
        target.props.update(changed)
        if changed:
            _apply_layout(_layout(target), target.props)

    # -- tree operations --------------------------------------------------

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        if _handle(parent).node_type in ("Grid", "GridItem") or _handle(parent).node_type in FORMATTING_TAGS:
            container, item = _handle(parent), _handle(child)
            if item in container.children:
                container.children.remove(item)
            container.children.insert(index, item)
            if item.widget.parent is not container.widget:
                if item.widget.parent is not None:
                    item.widget.parent.remove_widget(item.widget)
                container.widget.add_widget(item.widget)
            return
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self._sync_children(container)

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        if _handle(parent).node_type in ("Grid", "GridItem") or _handle(parent).node_type in FORMATTING_TAGS:
            container, item = _handle(parent), _handle(child)
            container.children.remove(item)
            container.children.insert(index, item)
            return
        container, item = _handle(parent), _handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self._sync_children(container)

    def remove(self, parent: object, child: object) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        if container.node_type in ("Grid", "GridItem"):
            if item.widget.parent is container.widget:
                container.widget.remove_widget(item.widget)
            return
        _layout(container).remove_widget(item.widget)
        if _is_borrowed(item) and item.original_parent is not None:
            item.original_parent.add_widget(item.widget)

    def _sync_children(self, parent: KivyHandle) -> None:
        """Make the layout's ``children`` equal PSX's sibling order, touching only what differs.

        Widgets are compared by identity from the front of the list; the first
        mismatch marks the only range that has to be removed and re-added.
        Appending a child touches one widget instead of rebuilding the layout.
        """
        layout = _layout(parent)
        spacer = getattr(layout, "_psx_bottom_spacer", None)

        # Kivy stores ``Widget.children`` in reverse paint/layout order. PSX
        # keeps handles in declaration order, so reverse only while syncing to
        # the native container (``Text, Slider`` must remain visually so).
        desired = [child.widget for child in reversed(parent.children)]
        # The bottom spacer is managed by the Column adapter, not by this diff.
        current = [w for w in layout.children if w is not spacer]

        shared = 0
        limit = min(len(current), len(desired))
        while shared < limit and current[shared] is desired[shared]:
            shared += 1

        for widget in tuple(current[shared:]):
            layout.remove_widget(widget)

        # When the spacer sits at index 0, visible children start at index 1.
        offset = 1 if (spacer is not None and spacer.parent is layout) else 0
        for position in range(shared, len(desired)):
            widget = desired[position]
            # An existing borrowed Native widget is still attached to its
            # caller's parent when first mounted. Kivy refuses to add a widget
            # that already has a parent, so transfer only the borrowed handle;
            # its original parent is restored on remove/unmount.
            if widget.parent is not None and widget.parent is not layout:
                borrowed = next(
                    (item for item in parent.children
                     if item.widget is widget and _is_borrowed(item)), None)
                if borrowed is None:
                    raise RendererCapabilityError(
                        "Cannot move an owned Kivy widget from a foreign parent.")
                widget.parent.remove_widget(widget)
            layout.add_widget(widget, index=position + offset)

    def destroy(self, handle: object) -> None:
        # Kivy's global KV Builder maintains property bindings indexed by a
        # widget's uid.  Waiting for the native widget destructor to remove
        # them can retain KV binding graphs across frequent mount/unmount
        # cycles, particularly after SFLE geometry writes.  An owned widget
        # is permanently destroyed at this boundary; borrowed native widgets
        # are returned to their owner and MUST keep their KV rules.
        target = _handle(handle)
        if target.native is not None:
            _clear_native_snapshot(target.widget)
        self.apply_css(handle, None)
        try:
            self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)
        finally:
            # KV cleanup must still run if adapter destruction throws.
            # Reconciler aggregates native teardown exceptions separately.
            if not _is_borrowed(target):
                from kivy.lang import Builder
                Builder.unbind_widget(target.widget.uid)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        widget = target.widget
        if self._sfle_constraints is not None and target.node_type == "TextArea":
            widget.unbind(text=self._sfle_on_textarea_changed)
        spec = _spec_for(target)
        if spec is not None and spec.on_destroy is not None:
            spec.on_destroy(widget)
        if _is_borrowed(target):
            if widget.parent is not target.original_parent:
                # Kivy disallows adding a widget which still has a parent.
                # PSX owns only temporary placement, never the instance.
                if widget.parent is not None:
                    widget.parent.remove_widget(widget)
                if target.original_parent is not None:
                    target.original_parent.add_widget(widget)
            # SFLE temporarily disables size/position hints while mounted.
            # Borrowed callers retain ownership of their original hints.
            if target.original_size_hint is not None:
                widget.size_hint = target.original_size_hint
            if target.original_pos_hint is not None:
                widget.pos_hint = dict(target.original_pos_hint)
            return
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    # -- events -----------------------------------------------------------

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self._adapter_for(handle_adapter_key(handle))
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        handle = _handle(handle)
        if handle.native is not None:
            if handle.native.bind_event is None:
                raise RendererCapabilityError(
                    f"Native widget {handle.native.name!r} has no event adapter for {event!r}."
                )
            disposer = handle.native.bind_event(handle.widget, event, slot)
            if not callable(disposer):
                raise TypeError(
                    "NativeWidget.bind_event must return a callable disposer.")
            return KivyNativeEventSubscription(disposer)

        spec = _spec_for(handle)
        definition = spec.events.get(event) if spec is not None else None
        if definition is None:
            raise RendererCapabilityError(
                f"{event} is not supported by Kivy {handle.node_type}.")
        kivy_event, make_callback = definition
        # only the requested event's closure is built
        callback = make_callback(handle.widget, slot)
        handle.widget.bind(**{kivy_event: callback})
        return KivyEventSubscription(handle.widget, kivy_event, callback)

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, KivyNativeEventSubscription):
            subscription.dispose()
            return
        target = _subscription(subscription)
        target.widget.unbind(**{target.event: target.callback})

    # -- lifecycle --------------------------------------------------------

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        Clock.schedule_once(lambda _delta: callback(), 0)

    def restore_root(self, previous) -> None:
        """Restore renderer ownership when a candidate root fails to mount."""
        self._root = _handle(previous).widget

    def transition_root(self, previous, replacement) -> None:
        """Exchange Kivy's displayed root while keeping the event loop alive."""
        from kivy.core.window import Window
        old = _handle(previous).widget
        new = _handle(replacement).widget
        if old is new:
            return
        previous_parent = old.parent
        if previous_parent is not None:
            previous_parent.remove_widget(old)
            try:
                previous_parent.add_widget(new)
            except BaseException:
                previous_parent.add_widget(old)
                raise
        self._root = new

    def run(self) -> int:
        if self._root is None:
            raise RuntimeError(
                "KivyRenderer.run() requires a mounted PSX root.")
        # A root with Cinnamon-owned geometry has size_hint=None. Kivy will
        # not automatically expand it to the SDL2 window when runTouchApp
        # attaches it, so reconcile the viewport once the root is mounted.
        # The existing size observer schedules the corresponding layout.
        def sync_attached_viewport(_dt):
            from kivy.core.window import Window
            root = self._sfle_watched_widget
            if root is not None and root.parent is Window:
                width, height = Window.size
                if width > 0 and height > 0:
                    if tuple(root.size) != (width, height):
                        root.size = (width, height)

        Clock.schedule_once(sync_attached_viewport, 0)
        try:
            runTouchApp(self._root)
        finally:
            # runTouchApp stops Kivy's EventLoop itself. Release PSX's
            # window observers and pending layout/resize callbacks on both
            # normal close and interrupted native loops, so nothing retains
            # a detached root after the loop returns.
            self.invalidate_layout()
        return 0

    # -- factories --------------------------------------------------------

    @staticmethod
    def _native(node: VNode, parent: Widget | None) -> KivyHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "kivy":
            renderer = declaration.renderer if isinstance(
                declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'kivy'."
            )
        initial_props = {k: v for k, v in node.props.items()
                         if not k.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = _build_native_widget(declaration, parent)
        if not isinstance(widget, Widget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a Kivy Widget, got {type(widget).__name__}."
            )
        borrowed = declaration.ownership is NativeOwnership.BORROWED
        original_parent = widget.parent if borrowed else None
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if not borrowed and widget.parent is not None:
                widget.parent.remove_widget(widget)
            raise
        return KivyHandle(
            declaration, widget, dict(initial_props), native=declaration,
            original_parent=original_parent,
            original_size_hint=tuple(widget.size_hint) if borrowed else None,
            original_pos_hint=dict(widget.pos_hint) if borrowed else None,
        )


# -- module helpers ---------------------------------------------------------

def _layout_spec(node_type: object) -> LayoutSpec | None:
    return _LAYOUTS.get(node_type) if isinstance(node_type, str) else None


def _layout_of(node: VNode) -> LayoutSpec | None:
    return _FRAGMENT_LAYOUT if node.kind is NodeKind.FRAGMENT else _layout_spec(node.type)


def _spec_for(handle: KivyHandle) -> PrimitiveSpec | None:
    """Primitive spec of a non-native handle (native handles carry a NativeWidget as type)."""
    if handle.native is not None or not isinstance(handle.node_type, str):
        return None
    return _PRIMITIVES.get(handle.node_type)


def _is_borrowed(handle: KivyHandle) -> bool:
    return handle.native is not None and handle.native.ownership is NativeOwnership.BORROWED


def _update_native(target: KivyHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    update = target.native.update
    if (changed or removed) and update is None:
        raise RendererCapabilityError(
            f"Native widget {target.native.name!r} received prop changes but has no update adapter."
        )
    if update is not None:
        update(target.widget, changed, removed)


def _build_native_widget(declaration: NativeWidget, parent: Widget | None) -> object:
    if declaration.factory is None:
        return declaration.widget
    return declaration.factory(parent) if declaration.takes_parent else declaration.factory()


def _handle(value: object) -> KivyHandle:
    if not isinstance(value, KivyHandle):
        raise TypeError("KivyRenderer received a foreign handle.")
    return value


def _layout(handle: KivyHandle) -> BoxLayout:
    if not isinstance(handle.widget, BoxLayout):
        raise RendererCapabilityError(
            f"{handle.node_type!r} cannot contain PSX children in Kivy.")
    return handle.widget


def _subscription(value: object) -> KivyEventSubscription:
    if not isinstance(value, KivyEventSubscription):
        raise TypeError("KivyRenderer received a foreign event subscription.")
    return value


def _apply_layout(widget: BoxLayout, props: Mapping[str, object]) -> None:
    padding = int(props.get("padding", 0))
    widget.padding = (padding, padding, padding, padding)
    widget.spacing = int(props.get("spacing", 0))


def _validate_props(node: VNode) -> None:
    if node.kind is NodeKind.NATIVE:
        return
    if node.kind is NodeKind.HOST:
        spec = _PRIMITIVES.get(node.type)
        if spec is not None:
            spec.validate(node.props)
            return
    layout = _layout_of(node)
    allowed = layout.props if layout is not None else frozenset()
    if node.props.keys() <= allowed:
        return
    unsupported = set(node.props) - allowed
    raise RendererCapabilityError(
        f"Unsupported Kivy props for {node.type!r}: {', '.join(sorted(unsupported))}")
