"""Kivy renderer for PSX's portable primitive subset."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from kivy.base import runTouchApp
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button as KivyButton
from kivy.uix.checkbox import CheckBox as KivyCheckBox
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import NodeKind, VNode, validate_text_props, validate_button_props, validate_checkbox_props
from psx.renderers.text import apply_kivy_text, updated_text_props, size_kivy_text
from psx.renderers.button import apply_kivy_button, updated_button_props
from psx.renderers.checkbox import apply_kivy_checkbox, updated_checkbox_props
from psx.renderers.adapters import AdapterSubscription, DelegatingAdapter, RendererAdapterRegistry, adapter_key, handle_adapter_key



@dataclass(slots=True)
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


class KivyRenderer:
    """Map portable PSX layout nodes to Kivy's native widget/layout APIs."""

    def __init__(self) -> None:
        self._root: Widget | None = None
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in ("Column", "Row", "Fragment", "Text", "Button", "Input", "Checkbox", "Native"):
            self.adapters.register(component, self._default_adapter)

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def create(self, node: VNode, parent: object | None) -> KivyHandle:
        adapter = self.adapters.get(adapter_key(node)) or self._default_adapter
        return adapter.create(self, node, parent)  # type: ignore[return-value]

    def _adapter_create(self, node: VNode, parent: object | None) -> KivyHandle:
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _handle(parent).widget if parent is not None else None
            handle = self._native(node, native_parent)
        elif node.kind is NodeKind.FRAGMENT or node.type in {"Column", "Row"}:
            widget = BoxLayout(orientation="horizontal" if node.type == "Row" else "vertical")
            _apply_layout(widget, node.props)
            handle = KivyHandle(node.type, widget, dict(node.props))
        elif node.kind is NodeKind.HOST and node.type == "Text":
            widget = Label(markup=False)
            apply_kivy_text(widget, node.props)
            widget.bind(size=size_kivy_text)
            size_kivy_text(widget, widget.size)
            handle = KivyHandle(node.type, widget, dict(node.props))
        elif node.kind is NodeKind.HOST and node.type == "Button":
            widget = KivyButton()
            apply_kivy_button(widget, node.props)
            handle = KivyHandle(node.type, widget, dict(node.props))
        elif node.kind is NodeKind.HOST and node.type == "Checkbox":
            widget = KivyCheckBox()
            apply_kivy_checkbox(widget, node.props)
            handle = KivyHandle(node.type, widget, dict(node.props))
        else:
            raise RendererCapabilityError(f"Kivy does not support host primitive {node.type!r}.")
        if parent is None:
            self._root = handle.widget
        return handle

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.update(self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _handle(handle)
        if target.native is not None:
            if (changed or removed) and target.native.update is None:
                raise RendererCapabilityError(
                    f"Native widget {target.native.name!r} received prop changes but has no update adapter."
                )
            if target.native.update is not None:
                target.native.update(target.widget, changed, removed)
            return
        if target.node_type == "Text":
            props = updated_text_props(target.props, changed, removed)
            apply_kivy_text(target.widget, props)
            target.props = props
            return
        if target.node_type == "Button":
            props = updated_button_props(target.props, changed, removed)
            apply_kivy_button(_button(target), props)
            target.props = props
            return
        if target.node_type == "Checkbox":
            props = updated_checkbox_props(target.props, changed, removed)
            apply_kivy_checkbox(target.widget, props)
            target.props = props
            return
        unsupported = set(removed) | (set(changed) - {"label", "enabled", "spacing", "padding"})
        if unsupported:
            raise RendererCapabilityError(f"Unsupported Kivy props: {', '.join(sorted(unsupported))}")
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        if "label" in changed:
            _button(target).text = str(changed["label"])
        if "enabled" in changed:
            _button(target).disabled = not bool(changed["enabled"])
        if {"spacing", "padding"} & (set(changed) | set(removed)):
            _apply_layout(_layout(target), target.props)

    def insert(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self._place_children(container)

    def move(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self._place_children(container)

    def remove(self, parent: object, child: object) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        _layout(container).remove_widget(item.widget)
        if item.native is not None and item.native.ownership is NativeOwnership.BORROWED:
            if item.original_parent is not None:
                item.original_parent.add_widget(item.widget)

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
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
                raise TypeError("NativeWidget.bind_event must return a callable disposer.")
            return KivyNativeEventSubscription(disposer)
        if handle.node_type == "Checkbox" and event == "on_change":
            target = _checkbox(handle)
            def changed(_widget: KivyCheckBox, value: bool) -> object | None:
                if not getattr(target, "_psx_updating", False):
                    return slot.invoke(bool(value))
                return None
            target.bind(active=changed)
            return KivyEventSubscription(target, "active", changed)
        target = _button(handle)
        if event != "on_click":
            raise RendererCapabilityError(f"{event} is not supported by Kivy Button.")
        def callback(_widget: KivyButton) -> object | None: return slot.invoke()
        target.bind(on_release=callback)
        return KivyEventSubscription(target, "on_release", callback)

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

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        widget = target.widget
        if target.node_type == "Text":
            widget.unbind(size=size_kivy_text)
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            if target.original_parent is not None and widget.parent is not target.original_parent:
                target.original_parent.add_widget(widget)
            return
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        Clock.schedule_once(lambda _delta: callback(), 0)

    def run(self) -> int:
        if self._root is None:
            raise RuntimeError("KivyRenderer.run() requires a mounted PSX root.")
        runTouchApp(self._root)
        return 0

    def _place_children(self, parent: KivyHandle) -> None:
        layout = _layout(parent)
        for widget in tuple(layout.children):
            layout.remove_widget(widget)
        # Kivy stores ``children`` in reverse visual order; reverse insertion
        # keeps PSX's declarative sibling order intact.
        for child in reversed(parent.children):
            layout.add_widget(child.widget)

    @staticmethod
    def _native(node: VNode, parent: Widget | None) -> KivyHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "kivy":
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'kivy'."
            )
        initial_props = {name: value for name, value in node.props.items() if not name.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = (
            declaration.factory(parent) if declaration.factory is not None and declaration.takes_parent
            else declaration.factory() if declaration.factory is not None else declaration.widget
        )
        if not isinstance(widget, Widget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a Kivy Widget, got {type(widget).__name__}."
            )
        original_parent = widget.parent if declaration.ownership is NativeOwnership.BORROWED else None
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if declaration.ownership is NativeOwnership.OWNED and widget.parent is not None:
                widget.parent.remove_widget(widget)
            raise
        return KivyHandle(declaration, widget, dict(initial_props), native=declaration, original_parent=original_parent)


def _handle(value: object) -> KivyHandle:
    if not isinstance(value, KivyHandle):
        raise TypeError("KivyRenderer received a foreign handle.")
    return value


def _layout(handle: KivyHandle) -> BoxLayout:
    if not isinstance(handle.widget, BoxLayout):
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in Kivy.")
    return handle.widget


def _button(handle: KivyHandle) -> KivyButton:
    if not isinstance(handle.widget, KivyButton):
        raise RendererCapabilityError("Button operation received a non-Button handle.")
    return handle.widget


def _checkbox(handle: KivyHandle) -> KivyCheckBox:
    if not isinstance(handle.widget, KivyCheckBox):
        raise RendererCapabilityError("Checkbox operation received a non-Checkbox handle.")
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
    if node.kind is NodeKind.HOST and node.type == "Text":
        validate_text_props(node.props)
        return
    if node.kind is NodeKind.HOST and node.type == "Button":
        validate_button_props(node.props)
        return
    if node.kind is NodeKind.HOST and node.type == "Checkbox":
        validate_checkbox_props(node.props)
        return
    allowed = {"spacing", "padding"} if node.kind is NodeKind.FRAGMENT or node.type in {"Column", "Row"} else set()
    unsupported = set(node.props) - allowed
    if unsupported:
        raise RendererCapabilityError(f"Unsupported Kivy props for {node.type!r}: {', '.join(sorted(unsupported))}")
