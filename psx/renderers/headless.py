"""Deterministic in-memory renderer for core tests and examples."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import RLock

from psx.core.events import EventSlot
from psx.core.vnode import NodeKind, VNode
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.button import updated_button_props, validate_button_props
from psx.renderers.components.checkbox import updated_checkbox_props, validate_checkbox_props
from psx.renderers.components.input import updated_input_props, validate_input_props
from psx.renderers.components.slider import updated_slider_props, validate_slider_props
from psx.renderers.components.spacer import updated_spacer_props, validate_spacer_props
from psx.renderers.components.text import updated_text_props, validate_text_props
from psx.renderers.components.textarea import updated_textarea_props, validate_textarea_props
from psx.renderers.components.divider import updated_divider_props, validate_divider_props
from psx.renderers.components.image import updated_image_props, validate_image_props


# eq=False: handles compare by identity, so list.remove/in use the fast C
# identity path instead of a recursive field-by-field dataclass comparison.


@dataclass(slots=True, eq=False)
class HeadlessHandle:
    type: object
    props: dict[str, object]
    children: list["HeadlessHandle"] = field(default_factory=list)
    events: dict[str, EventSlot] = field(default_factory=dict)
    destroyed: bool = False


class HeadlessRenderer:
    """Records native-like operations without importing a UI toolkit."""

    def __init__(self) -> None:
        self.operations: list[tuple[object, ...]] = []
        self._pending: list[Callable[[], None]] = []
        self._lock = RLock()
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in (
            "Column", "Row", "Fragment",
            "Text", "Button", "Input", "TextArea", "Checkbox", "Slider",
            "Spacer", "Divider", "Image", "Native", "Box",
        ):
            self.adapters.register(component, self._default_adapter)

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def create(self, node: VNode, parent: object | None) -> HeadlessHandle:
        adapter = self.adapters.get(adapter_key(node)) or self._default_adapter
        return adapter.create(self, node, parent)  # type: ignore[return-value]

    def _adapter_create(self, node: VNode, parent: object | None) -> HeadlessHandle:
        if node.kind is NodeKind.HOST:
            if node.type == "Text":
                validate_text_props(node.props)
            elif node.type == "Button":
                validate_button_props(node.props)
            elif node.type == "Checkbox":
                validate_checkbox_props(node.props)
            elif node.type == "Input":
                validate_input_props(node.props)
            elif node.type == "TextArea":
                validate_textarea_props(node.props)
            elif node.type == "Slider":
                validate_slider_props(node.props)
            elif node.type == "Spacer":
                validate_spacer_props(node.props)
            elif node.type == "Divider":
                validate_divider_props(node.props)
            elif node.type == "Image":
                validate_image_props(node.props)
        handle = HeadlessHandle(node.type, dict(node.props))
        self.operations.append(("create", handle))
        return handle

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        adapter.update(self, handle, changed, removed)

    def _adapter_update(
        self,
        handle: object,
        changed: Mapping[str, object],
        removed: frozenset[str],
    ) -> None:
        target = _handle(handle)
        if target.type == "Text":
            updated_text_props(target.props, changed, removed)
        elif target.type == "Input":
            updated_input_props(target.props, changed, removed)
        elif target.type == "TextArea":
            updated_textarea_props(target.props, changed, removed)
        elif target.type == "Slider":
            updated_slider_props(target.props, changed, removed)
        elif target.type == "Button":
            updated_button_props(target.props, changed, removed)
        elif target.type == "Checkbox":
            updated_checkbox_props(target.props, changed, removed)
        elif target.type == "Spacer":
            updated_spacer_props(target.props, changed, removed)
        elif target.type == "Divider":
            updated_divider_props(target.props, changed, removed)
        elif target.type == "Image":
            updated_image_props(target.props, changed, removed)
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        self.operations.append(("update", target, dict(changed), removed))

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("insert", container, item, index))

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("move", container, item, index))

    def remove(self, parent: object, child: object) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        self.operations.append(("remove", container, item))

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        target = _handle(handle)
        target.events[event] = slot
        subscription = (target, event, slot)
        self.operations.append(("bind_event", target, event))
        return subscription

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        target, event, slot = subscription  # type: ignore[misc]
        if target.events.get(event) is slot:
            target.events.pop(event)
        self.operations.append(("unbind_event", target, event))

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        target.destroyed = True
        self.operations.append(("destroy", target))

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._pending.append(callback)

    def flush(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    return
                callback = self._pending.pop(0)
            callback()

    def run(self) -> int:
        self.flush()
        return 0


def _handle(value: object) -> HeadlessHandle:
    if not isinstance(value, HeadlessHandle):
        raise TypeError("HeadlessRenderer received a foreign handle.")
    return value
