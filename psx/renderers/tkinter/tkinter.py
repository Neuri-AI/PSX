"""Tkinter renderer for PSX's small portable primitive subset.

Tkinter is imported only by this adapter.  Layout nodes are represented by
``ttk.Frame`` instances and PSX exclusively manages their ``pack`` children.

Adding a new host tag
---------------------
Call :func:`register_primitive` once (module import time is fine); every
``TkinterRenderer`` picks it up, including renderers created before the call::

    register_primitive(
        "Slider",
        factory=ttk.Scale,                      # called as factory(master)
        validate=validate_slider_props,
        apply=apply_tk_slider,                  # apply(widget, props)
        updated_props=updated_slider_props,
        events={"on_change": ("command", emit_call)},
    )

Container tags are registered with :func:`register_layout`.
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
from psx.core.vnode import NodeKind, VNode
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.text import apply_tk_text, updated_text_props
from psx.renderers.components.button import apply_tk_button, updated_button_props
from psx.renderers.components.checkbox import apply_tk_checkbox, updated_checkbox_props
from psx.renderers.components.input import apply_tk_input, updated_input_props
from psx.renderers.components.textarea import apply_tk_textarea, updated_textarea_props
from psx.renderers.components.slider import apply_tk_slider, updated_slider_props
from psx.renderers.components.spacer import apply_tk_spacer, updated_spacer_props
from psx.renderers.components.progressbar import apply_tk_progressbar, updated_progressbar_props
from psx.renderers.components.radio import updated_radio_props

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
)

_LAYOUT_PROPS = frozenset({"spacing", "padding"})
_LAYOUT_UPDATABLE = frozenset({"spacing", "padding"})

# (widget option that holds the callback, factory building the Python callback)
EventDef = tuple[str, Callable[[tk.Misc, EventSlot], Callable[[], object | None]]]

# Makers
def _make_radio(master):
    return ttk.Radiobutton(master)

# Appliers
def apply_tk_radio(widget, props):
    widget.configure(text=str(props["label"]))
    widget.state(("!disabled",) if props["enabled"] else ("disabled",))
    widget._psx_radio_value = props["value"]

# factories for creating event callbacks for Tkinter widgets
def _tk_input_factory(master):
    var = tk.StringVar()
    entry = ttk.Entry(master, textvariable=var)
    entry.var = var
    return entry

def _tk_textarea_factory(master):
    return tk.Text(master, wrap="word")

@dataclass(slots=True, eq=False)
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
    option: str = "command"


@dataclass(slots=True)
class TkNativeEventSubscription:
    dispose: Callable[[], None]


# -- event callback factories (reusable when registering new primitives) ---

def emit_call(widget: tk.Misc, slot: EventSlot) -> Callable[[], object | None]:
    """Invoke the slot with no arguments."""
    return lambda: slot.invoke()


def emit_checked(widget: tk.Misc, slot: EventSlot) -> Callable[[], object | None]:
    """Invoke the slot with the checkbox's current boolean state."""
    return lambda: slot.invoke(bool(widget._psx_variable.get()))

def emit_tk_input(widget, slot):
    def _trace(*_):
        if getattr(widget, "_psx_updating", False):
            return
        slot.invoke(widget.var.get())
    widget.var.trace_add("write", _trace)
    return _trace   # el trace no se puede “desconectar” fácilmente; se ignora si el slot ya no existe

def emit_tk_submit(widget, slot):
    return lambda event: slot.invoke()

def emit_tk_textarea(widget, slot):
    def _on_modified(event):
        if getattr(widget, "_psx_updating", False):
            return
        if widget.edit_modified():
            widget.edit_modified(False)
            slot.invoke(widget.get("1.0", "end-1c"))
    return _on_modified

def emit_tk_slider(widget, slot):
    def _on_command(value_str):
        if getattr(widget, "_psx_updating", False):
            return
        slot.invoke(float(value_str))
    return _on_command


# -- registries -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    """Everything the renderer needs to know about one leaf host primitive."""

    factory: Callable[[tk.Misc], tk.Misc]
    validate: Callable[[Mapping[str, object]], None]
    apply: Callable[[tk.Misc, Mapping[str, object]], None]
    updated_props: Callable[
        [Mapping[str, object], Mapping[str, object], frozenset[str]], dict[str, object]
    ]
    events: Mapping[str, EventDef] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    horizontal: bool
    props: frozenset[str] = _LAYOUT_PROPS


_PRIMITIVES: dict[str, PrimitiveSpec] = {}
_LAYOUTS: dict[str, LayoutSpec] = {}
_FRAGMENT_LAYOUT = LayoutSpec(horizontal=False, props=frozenset({"spacing"}))
_STRUCTURAL = frozenset({"Fragment", "Native"})


def register_primitive(
    name: str,
    *,
    factory: Callable[[tk.Misc], tk.Misc],
    validate: Callable[[Mapping[str, object]], None],
    apply: Callable[[tk.Misc, Mapping[str, object]], None],
    updated_props: Callable[..., dict[str, object]],
    events: Mapping[str, EventDef] | None = None,
    replace: bool = False,
) -> PrimitiveSpec:
    """Register a leaf host tag."""
    if name in _STRUCTURAL or name in _LAYOUTS or (name in _PRIMITIVES and not replace):
        raise ValueError(f"Primitive {name!r} is already registered.")
    spec = PrimitiveSpec(factory, validate, apply, updated_props, dict(events or {}))
    _PRIMITIVES[name] = spec
    return spec


def register_layout(
    name: str, *, horizontal: bool, props: frozenset[str] = _LAYOUT_PROPS, replace: bool = False
) -> None:
    """Register a container tag backed by a ``ttk.Frame`` managed with ``pack``."""
    if name in _STRUCTURAL or name in _PRIMITIVES or (name in _LAYOUTS and not replace):
        raise ValueError(f"Layout {name!r} is already registered.")
    _LAYOUTS[name] = LayoutSpec(horizontal, props)


# -- built-in tags ----------------------------------------------------------

def _make_checkbox(master: tk.Misc) -> ttk.Checkbutton:
    variable = tk.BooleanVar(master=master)
    widget = ttk.Checkbutton(master, variable=variable)
    widget._psx_variable = variable
    return widget


def _apply_checkbox(widget: tk.Misc, props: Mapping[str, object]) -> None:
    apply_tk_checkbox(widget, props, widget._psx_variable)


register_primitive(
    "Text", factory=ttk.Label,
    validate=validate_text_props, apply=apply_tk_text, updated_props=updated_text_props,
)
register_primitive(
    "Button", factory=ttk.Button,
    validate=validate_button_props, apply=apply_tk_button, updated_props=updated_button_props,
    events={"on_click": ("command", emit_call)},
)
register_primitive(
    "Checkbox", factory=_make_checkbox,
    validate=validate_checkbox_props, apply=_apply_checkbox, updated_props=updated_checkbox_props,
    events={"on_change": ("command", emit_checked)},
)

register_primitive(
    "Input",
    factory=_tk_input_factory,
    validate=validate_input_props,
    apply=apply_tk_input,
    updated_props=updated_input_props,
    events={
        "on_change": ("<<Modified>>", emit_tk_input),  # realmente se usa trace, ver nota
        "on_submit": ("<Return>", emit_tk_submit),
    },
)
register_primitive(
    "TextArea",
    factory=_tk_textarea_factory,
    validate=validate_textarea_props,
    apply=apply_tk_textarea,
    updated_props=updated_textarea_props,
    events={"on_change": ("<<Modified>>", emit_tk_textarea)},
)
register_primitive(
    "Slider",
    factory=ttk.Scale,
    validate=validate_slider_props,
    apply=apply_tk_slider,
    updated_props=updated_slider_props,
    events={"on_change": ("command", emit_tk_slider)},
)
register_primitive(
    "Spacer", factory=ttk.Frame,
    validate=validate_spacer_props, apply=apply_tk_spacer,
    updated_props=updated_spacer_props,
)
register_primitive(
    "ProgressBar", factory=lambda master: ttk.Progressbar(master),
    validate=validate_progressbar_props,
    apply=apply_tk_progressbar,
    updated_props=updated_progressbar_props,
)

register_primitive(
    "Radio", factory=_make_radio,
    validate=validate_radio_props,
    apply=apply_tk_radio,
    updated_props=updated_radio_props,
)
# -- renderer ---------------------------------------------------------------

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
        # "Input" stays reserved (unsupported in Tk) so custom adapters still need replace=True.
        for component in dict.fromkeys((*_LAYOUTS, *_PRIMITIVES, "Fragment", "Input", "Native")):
            self.adapters.register(component, self._default_adapter)
        from .column import TkColumnAdapter
        from .row import TkRowAdapter
        from .divider import TkDividerAdapter
        from .image import TkImageAdapter
        from .box import TkBoxAdapter
        from .radiogroup import TkRadioGroupAdapter
        from .select import TkSelectAdapter
        from .switch import TkSwitchAdapter
        from .link import TkLinkAdapter
        from .spinbox import TkSpinBoxAdapter
        from .scroll import TkScrollAdapter
        self.adapters.register("Column", TkColumnAdapter())
        self.adapters.register("Row", TkRowAdapter())
        self.adapters.register("Divider", TkDividerAdapter())
        self.adapters.register("Image", TkImageAdapter())
        self.adapters.register("Box", TkBoxAdapter())
        self.adapters.register("RadioGroup", TkRadioGroupAdapter())
        self.adapters.register("Select", TkSelectAdapter())
        self.adapters.register("Switch", TkSwitchAdapter())
        self.adapters.register("Link", TkLinkAdapter())
        self.adapters.register("SpinBox", TkSpinBoxAdapter())
        self.adapters.register("Scroll", TkScrollAdapter())
        self._schedule_drain()

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def _adapter_for(self, key: object):
        return self.adapters.get(key) or self._default_adapter

    # -- create -----------------------------------------------------------

    def create(self, node: VNode, parent: object | None) -> TkHandle:
        # Scroll owns an inner content frame. New Tk widgets must be constructed
        # with that frame as their real native master; pack(in_=...) alone
        # cannot reparent a widget into a descendant of its original master.
        native_parent = parent
        if parent is not None and getattr(parent, "node_type", None) == "Scroll":
            from types import SimpleNamespace
            native_parent = SimpleNamespace(widget=parent.widget._psx_content)
        handle = self._adapter_for(adapter_key(node)).create(self, node, native_parent)
        self._bind_scroll_wheel(handle.widget)
        return handle

    @staticmethod
    def _bind_scroll_wheel(widget: tk.Misc) -> None:
        # Each mounted widget registers only on itself; no global bind_all().
        def on_wheel(event):
            current = widget
            while current is not None:
                if hasattr(current, "_psx_canvas"):
                    consumed = current._wheel(event)
                    if consumed == "break":
                        return consumed
                current = getattr(current, "master", None)
            return None
        current = widget
        in_scroll = False
        while current is not None:
            if hasattr(current, "_psx_canvas"):
                in_scroll = True
                break
            current = getattr(current, "master", None)
        if not in_scroll:
            return
        widget.bind("<MouseWheel>", on_wheel, add="+")
        widget.bind("<Shift-MouseWheel>", on_wheel, add="+")
        widget.bind("<Button-4>", on_wheel, add="+")
        widget.bind("<Button-5>", on_wheel, add="+")

    def _adapter_create(self, node: VNode, parent: object | None) -> TkHandle:
        _validate_props(node)
        master = _as_handle(parent).widget if parent is not None else self.root
        if node.kind is NodeKind.NATIVE:
            return self._native(node, master)
        if _layout_of(node) is not None:
            padding = int(node.props.get("padding", 0))
            return TkHandle(node.type, ttk.Frame(master, padding=padding), dict(node.props))
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(f"Tkinter cannot create node kind {node.kind.value!r}.")
        spec = _PRIMITIVES.get(node.type)
        if spec is None:
            raise RendererCapabilityError(f"Tkinter does not support host primitive {node.type!r}.")
        widget = spec.factory(master)
        spec.apply(widget, node.props)
        return TkHandle(node.type, widget, dict(node.props))

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        self._adapter_for(handle_adapter_key(handle)).update(self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _as_handle(handle)
        if target.native is not None:
            _update_native(target, changed, removed)
            return
        spec = _PRIMITIVES.get(target.node_type)
        if spec is not None:
            props = spec.updated_props(target.props, changed, removed)
            spec.apply(target.widget, props)
            target.props = props
            return
        self._update_layout(target, changed, removed)

    def _update_layout(self, target: TkHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        if not (removed <= _LAYOUT_UPDATABLE and changed.keys() <= _LAYOUT_UPDATABLE):
            unsupported = (set(changed) | set(removed)) - _LAYOUT_UPDATABLE
            raise RendererCapabilityError(
                f"Unsupported Tkinter props for {target.node_type!r}: {', '.join(sorted(unsupported))}"
            )
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        if "padding" in changed or "padding" in removed:
            _as_frame(target).configure(padding=int(target.props.get("padding", 0)))
        if "spacing" in changed or "spacing" in removed:
            self._repack(target)

    # -- tree operations --------------------------------------------------

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        self._place(_as_handle(parent), _as_handle(child), index, require_existing=False)

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        self._place(_as_handle(parent), _as_handle(child), index, require_existing=True)

    def remove(self, parent: object, child: object) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        if item in container.children:
            container.children.remove(item)
        item.widget.pack_forget()

    def _place(self, container: TkHandle, item: TkHandle, index: int, *, require_existing: bool) -> None:
        """Put ``item`` at ``index`` and re-pack only the children that can have changed position."""
        children = container.children
        try:
            old = children.index(item)
        except ValueError:
            if require_existing:
                raise
            old = None
        else:
            del children[old]
        children.insert(index, item)
        new = children.index(item)
        self._repack(container, new if old is None else min(old, new))

    def _repack(self, parent: TkHandle, start: int = 0) -> None:
        frame = _as_frame(parent)
        options = _pack_options(parent)
        for child in parent.children[start:]:
            child.widget.pack_forget()
            child.widget.pack(in_=frame, **options)

    def destroy(self, handle: object) -> None:
        self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _as_handle(handle)
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            return
        if target.widget.winfo_exists():
            target.widget.destroy()

    # -- events -----------------------------------------------------------

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self._adapter_for(handle_adapter_key(handle))
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

        spec = _PRIMITIVES.get(handle.node_type)
        definition = spec.events.get(event) if spec is not None else None
        if definition is None:
            raise RendererCapabilityError(f"{event} is not supported by {handle.node_type} in Tkinter.")
        option, make_callback = definition
        callback = make_callback(handle.widget, slot)  # only the requested event's closure is built
        handle.widget.configure(**{option: callback})
        return TkEventSubscription(handle.widget, event, callback, option)

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
        target.widget.configure(**{target.option: ""})

    # -- scheduling / lifecycle ------------------------------------------

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

    # -- factories --------------------------------------------------------

    @staticmethod
    def _native(node: VNode, master: tk.Misc) -> TkHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "tkinter":
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'tkinter'."
            )
        initial_props = {k: v for k, v in node.props.items() if not k.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = _build_native_widget(declaration, master)
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


# -- module helpers ---------------------------------------------------------

def _layout_spec(node_type: object) -> LayoutSpec | None:
    return _LAYOUTS.get(node_type) if isinstance(node_type, str) else None


def _layout_of(node: VNode) -> LayoutSpec | None:
    return _FRAGMENT_LAYOUT if node.kind is NodeKind.FRAGMENT else _layout_spec(node.type)


def _pack_options(parent: TkHandle) -> dict[str, object]:
    spacing = int(parent.props.get("spacing", 0))
    layout = _layout_spec(parent.node_type)
    if layout is not None and layout.horizontal:
        return {"side": tk.LEFT, "fill": tk.NONE, "expand": False, "padx": spacing, "pady": 0}
    return {"side": tk.TOP, "fill": tk.X, "expand": True, "padx": 0, "pady": spacing}


def _update_native(target: TkHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    update = target.native.update
    if (changed or removed) and update is None:
        raise RendererCapabilityError(
            f"Native widget {target.native.name!r} received prop changes but has no update adapter."
        )
    if update is not None:
        update(target.widget, changed, removed)


def _build_native_widget(declaration: NativeWidget, master: tk.Misc) -> object:
    if declaration.factory is None:
        return declaration.widget
    return declaration.factory(master) if declaration.takes_parent else declaration.factory()


def _as_handle(value: object) -> TkHandle:
    if not isinstance(value, TkHandle):
        raise TypeError("TkinterRenderer received a foreign handle.")
    return value


def _as_frame(handle: TkHandle) -> ttk.Frame:
    if not isinstance(handle.widget, ttk.Frame):
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in Tkinter.")
    return handle.widget


def _as_subscription(value: object) -> TkEventSubscription:
    if not isinstance(value, TkEventSubscription):
        raise TypeError("TkinterRenderer received a foreign event subscription.")
    return value


def _validate_props(node: VNode) -> None:
    if node.kind is NodeKind.NATIVE:
        return
    if node.kind is NodeKind.HOST:
        spec = _PRIMITIVES.get(node.type)
        if spec is not None:
            spec.validate(node.props)
            return
    layout = _layout_of(node)
    if layout is None or node.props.keys() <= layout.props:
        return
    unsupported = set(node.props) - layout.props
    raise RendererCapabilityError(
        f"Unsupported Tkinter props for {node.type!r}: {', '.join(sorted(unsupported))}"
    )
