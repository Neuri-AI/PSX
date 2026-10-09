"""Tkinter renderer for PSX's small portable primitive subset.

Tkinter is imported only by this adapter.  Layout nodes are represented by
``ttk.Frame`` instances and PSX exclusively manages their ``pack`` children.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
import tkinter as tk
from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import NodeKind, VNode, validate_button_props, validate_checkbox_props, validate_text_props
from psx.renderers.text import apply_tk_text, updated_text_props
from psx.renderers.button import apply_tk_button, updated_button_props
from psx.renderers.checkbox import apply_tk_checkbox, updated_checkbox_props
from psx.renderers.adapters import AdapterSubscription, DelegatingAdapter, RendererAdapterRegistry, adapter_key, handle_adapter_key


@dataclass(slots=True)
class TkHandle:
    node_type: object
    widget: tk.Misc
    props: dict[str, object]
    children: list["TkHandle"] = field(default_factory=list)
    native: NativeWidget | None = None


@dataclass(slots=True)
class TkEventSubscription:
    widget: tk.Misc
    event: str
    callback: Callable[[], object | None]


@dataclass(slots=True)
class TkNativeEventSubscription:
    dispose: Callable[[], None]


class TkinterRenderer:
    """Map PSX primitives to ttk widgets and use Tk's existing event loop."""

    def __init__(self, root: tk.Tk | None = None, *, poll_interval_ms: int = 10) -> None:
        self.root = root if root is not None else tk.Tk()
        self._owns_root = root is None
        self._pending: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._poll_interval_ms = poll_interval_ms
        self._closed = False
        self._after_id: str | None = None
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in ("Column", "Row", "Fragment", "Text", "Button", "Input", "Checkbox", "Native"):
            self.adapters.register(component, self._default_adapter)
        self._schedule_drain()

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def create(self, node: VNode, parent: object | None) -> TkHandle:
        adapter = self.adapters.get(adapter_key(node)) or self._default_adapter
        return adapter.create(self, node, parent)  # type: ignore[return-value]

    def _adapter_create(self, node: VNode, parent: object | None) -> TkHandle:
        _validate_props(node)
        master = _as_handle(parent).widget if parent is not None else self.root
        if node.kind is NodeKind.NATIVE:
            return self._native(node, master)
        if node.kind is NodeKind.FRAGMENT or node.type in {"Column", "Row"}:
            padding = int(node.props.get("padding", 0))
            return TkHandle(node.type, ttk.Frame(master, padding=padding), dict(node.props))
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(f"Tkinter cannot create node kind {node.kind.value!r}.")
        if node.type == "Text":
            widget = ttk.Label(master)
            apply_tk_text(widget, node.props)
            return TkHandle(node.type, widget, dict(node.props))
        if node.type == "Button":
            widget = ttk.Button(master)
            apply_tk_button(widget, node.props)
            return TkHandle(node.type, widget, dict(node.props))
        if node.type == "Checkbox":
            variable = tk.BooleanVar(master=master)
            widget = ttk.Checkbutton(master, variable=variable)
            widget._psx_variable = variable
            apply_tk_checkbox(widget, node.props, variable)
            return TkHandle(node.type, widget, dict(node.props))
        raise RendererCapabilityError(f"Tkinter does not support host primitive {node.type!r}.")

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.update(self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _as_handle(handle)
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
            apply_tk_text(target.widget, props)
            target.props = props
            return
        if target.node_type == "Button":
            props = updated_button_props(target.props, changed, removed)
            apply_tk_button(_as_button(target), props)
            target.props = props
            return
        if target.node_type == "Checkbox":
            props = updated_checkbox_props(target.props, changed, removed)
            apply_tk_checkbox(_as_checkbox(target), props, _as_checkbox(target)._psx_variable)
            target.props = props
            return
        layout = target.node_type in {"Column", "Row", "Fragment"}
        allowed = {"spacing", "padding"} if layout else {"label", "enabled"}
        unsupported = (set(changed) | set(removed)) - allowed
        if unsupported:
            raise RendererCapabilityError(
                f"Unsupported Tkinter props for {target.node_type!r}: {', '.join(sorted(unsupported))}"
            )
        if "label" in changed:
            _as_button(target).configure(text=str(changed["label"]))
        if "enabled" in changed:
            _as_button(target).state(("!disabled",) if changed["enabled"] else ("disabled",))
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        if "padding" in changed or "padding" in removed:
            _as_frame(target).configure(padding=int(target.props.get("padding", 0)))
        if "spacing" in changed or "padding" in changed or {"spacing", "padding"} & set(removed):
            self._repack(target)

    def insert(self, parent: object, child: object, index: int) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self._repack(container)

    def move(self, parent: object, child: object, index: int) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self._repack(container)

    def remove(self, parent: object, child: object) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        if item in container.children:
            container.children.remove(item)
        item.widget.pack_forget()

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        handle = _as_handle(handle)
        if handle.native is not None:
            if handle.native.bind_event is None:
                raise RendererCapabilityError(
                    f"Native widget {handle.native.name!r} has no event adapter for {event!r}."
                )
            disposer = handle.native.bind_event(handle.widget, event, slot)
            if not callable(disposer):
                raise TypeError("NativeWidget.bind_event must return a callable disposer.")
            return TkNativeEventSubscription(disposer)
        if handle.node_type == "Checkbox" and event == "on_change":
            target = _as_checkbox(handle)
            def changed() -> object | None:
                return slot.invoke(bool(target._psx_variable.get()))
            target.configure(command=changed)
            return TkEventSubscription(target, event, changed)
        target = _as_button(handle)
        if event != "on_click":
            raise RendererCapabilityError(f"{event} is not supported by Button in Tkinter.")

        def callback() -> object | None:
            return slot.invoke()

        target.configure(command=callback)
        return TkEventSubscription(target, event, callback)

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, TkNativeEventSubscription):
            try:
                subscription.dispose()
            except tk.TclError:
                pass
            return
        target = _as_subscription(subscription)
        if target.event == "on_click":
            target.widget.configure(command="")

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _as_handle(handle)
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            return
        if target.widget.winfo_exists():
            target.widget.destroy()

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        """Queue work safely; Tk's ``after`` polling drains it on the UI thread."""
        self._pending.put(callback)

    def flush(self) -> None:
        """Drain queued work now; intended for deterministic tests on the Tk thread."""
        self._drain_pending()

    def run(self) -> int:
        self.root.mainloop()
        return 0

    def close(self) -> None:
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._owns_root and self.root.winfo_exists():
            self.root.destroy()

    def _drain_scheduled(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        self._after_id = None
        self._drain_pending()
        self._schedule_drain()

    def _schedule_drain(self) -> None:
        if self._closed:
            return
        try:
            self._after_id = self.root.after(self._poll_interval_ms, self._drain_scheduled)
        except tk.TclError:
            # The borrowed Qyro host may already be in teardown.
            self._closed = True

    def _drain_pending(self) -> None:
        while True:
            try:
                self._pending.get_nowait()()
            except Empty:
                return

    def _repack(self, parent: TkHandle) -> None:
        frame = _as_frame(parent)
        horizontal = parent.node_type == "Row"
        spacing = int(parent.props.get("spacing", 0))
        for child in parent.children:
            child.widget.pack_forget()
            child.widget.pack(
                in_=frame,
                side=tk.LEFT if horizontal else tk.TOP,
                fill=tk.X if not horizontal else tk.NONE,
                expand=not horizontal,
                padx=spacing if horizontal else 0,
                pady=0 if horizontal else spacing,
            )

    @staticmethod
    def _native(node: VNode, master: tk.Misc) -> TkHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "tkinter":
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'tkinter'."
            )
        initial_props = {name: value for name, value in node.props.items() if not name.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = (
            declaration.factory(master) if declaration.factory is not None and declaration.takes_parent
            else declaration.factory() if declaration.factory is not None else declaration.widget
        )
        if not isinstance(widget, tk.Misc):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a tkinter widget, got {type(widget).__name__}."
            )
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if declaration.ownership is NativeOwnership.OWNED and widget.winfo_exists():
                widget.destroy()
            raise
        return TkHandle(declaration, widget, dict(initial_props), native=declaration)


def _as_handle(value: object) -> TkHandle:
    if not isinstance(value, TkHandle):
        raise TypeError("TkinterRenderer received a foreign handle.")
    return value


def _as_frame(handle: TkHandle) -> ttk.Frame:
    if not isinstance(handle.widget, ttk.Frame):
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in Tkinter.")
    return handle.widget


def _as_button(handle: TkHandle) -> ttk.Button:
    if not isinstance(handle.widget, ttk.Button):
        raise RendererCapabilityError("Button operation received a non-Button handle.")
    return handle.widget


def _as_checkbox(handle: TkHandle) -> ttk.Checkbutton:
    if not isinstance(handle.widget, ttk.Checkbutton):
        raise RendererCapabilityError("Checkbox operation received a non-Checkbox handle.")
    return handle.widget


def _as_subscription(value: object) -> TkEventSubscription:
    if not isinstance(value, TkEventSubscription):
        raise TypeError("TkinterRenderer received a foreign event subscription.")
    return value


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
    if node.kind is NodeKind.FRAGMENT:
        allowed = {"spacing"}
    elif node.type in {"Column", "Row"}:
        allowed = {"spacing", "padding"}
    else:
        return
    unsupported = set(node.props) - allowed
    if unsupported:
        raise RendererCapabilityError(
            f"Unsupported Tkinter props for {node.type!r}: {', '.join(sorted(unsupported))}"
        )
