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
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
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


_LAYOUT_PROPS = frozenset({"spacing", "padding"})

# (Kivy event/property name passed to widget.bind, factory building the Python callback)
EventDef = tuple[str, Callable[[Widget, EventSlot],
                               Callable[..., object | None]]]

# Factories for creating event callbacks for Kivy widgets


def _kivy_input_factory():
    return TextInput(multiline=False)


def _kivy_textarea_factory():
    return TextInput(multiline=True)


@dataclass(slots=True, eq=False)
class KivyHandle:
    node_type: object
    widget: Widget
    props: dict[str, object]
    children: list["KivyHandle"] = field(default_factory=list)
    native: NativeWidget | None = None
    original_parent: Widget | None = None


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
    "Checkbox", factory=KivyCheckBox,
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
    factory=KivySlider,
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

    def __init__(self) -> None:
        self._root: Widget | None = None
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        # "Input" stays reserved (unsupported in Kivy) so custom adapters still need replace=True.
        for component in dict.fromkeys((*_LAYOUTS, *_PRIMITIVES, "Fragment", "Input", "Native")):
            self.adapters.register(component, self._default_adapter)
        from .column import KivyColumnAdapter
        from .row import KivyRowAdapter
        from .divider import KivyDividerAdapter
        from .image import KivyImageAdapter
        from .switch import KivySwitchAdapter
        from .link import KivyLinkAdapter
        from .spinbox import KivySpinBoxAdapter
        from .box import KivyBoxAdapter
        from .progressbar import KivyProgressBarAdapter
        from .radio import KivyRadioAdapter, KivyRadioGroupAdapter

        self.adapters.register("Divider", KivyDividerAdapter())
        self.adapters.register("Column", KivyColumnAdapter())
        self.adapters.register("Row", KivyRowAdapter())
        self.adapters.register("Image", KivyImageAdapter())
        self.adapters.register("Switch", KivySwitchAdapter())
        self.adapters.register("Link", KivyLinkAdapter())
        self.adapters.register("SpinBox", KivySpinBoxAdapter())
        self.adapters.register("Box", KivyBoxAdapter())
        self.adapters.register("ProgressBar", KivyProgressBarAdapter())
        self.adapters.register("Radio", KivyRadioAdapter())
        self.adapters.register("RadioGroup", KivyRadioGroupAdapter())

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def _adapter_for(self, key: object):
        return self.adapters.get(key) or self._default_adapter

    # -- create -----------------------------------------------------------

    def create(self, node: VNode, parent: object | None) -> KivyHandle:
        # type: ignore[return-value]
        return self._adapter_for(adapter_key(node)).create(self, node, parent)

    def _adapter_create(self, node: VNode, parent: object | None) -> KivyHandle:
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _handle(
                parent).widget if parent is not None else None
            handle = self._native(node, native_parent)
        else:
            handle = self._create_local(node)
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

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        self._adapter_for(handle_adapter_key(handle)).update(
            self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _handle(handle)
        if target.native is not None:
            _update_native(target, changed, removed)
            return
        spec = _spec_for(target)
        if spec is not None:
            props = spec.updated_props(target.props, changed, removed)
            spec.apply(target.widget, props)
            target.props = props
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
            layout.add_widget(desired[position], index=position + offset)

    def destroy(self, handle: object) -> None:
        self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        widget = target.widget
        spec = _spec_for(target)
        if spec is not None and spec.on_destroy is not None:
            spec.on_destroy(widget)
        if _is_borrowed(target):
            if target.original_parent is not None and widget.parent is not target.original_parent:
                target.original_parent.add_widget(widget)
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

    def run(self) -> int:
        if self._root is None:
            raise RuntimeError(
                "KivyRenderer.run() requires a mounted PSX root.")
        runTouchApp(self._root)
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
        return KivyHandle(declaration, widget, dict(initial_props), native=declaration, original_parent=original_parent)


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
