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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


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
    widget.setText(str(props["label"]))
    widget.setEnabled(bool(props["enabled"]))
    widget._psx_radio_value = props["value"]

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

    def __init__(self, binding: str, argv: list[str] | None = None) -> None:
        self._binding = binding.lower()
        self._binding_package = binding
        core = importlib.import_module(f"{binding}.QtCore")
        self._widgets = widgets = importlib.import_module(
            f"{binding}.QtWidgets")

        self._widget = widgets.QWidget
        self._vbox = widgets.QVBoxLayout
        self._hbox = widgets.QHBoxLayout
        # resolved lazily from the registry
        self._primitive_classes: dict[str, type] = {}

        application = widgets.QApplication
        self.application = application.instance() or application(
            argv if argv is not None else sys.argv)
        self._dispatcher = _make_dispatcher(core)

        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in (*_LAYOUTS, "Fragment", *_PRIMITIVES, "Native"):
            self.adapters.register(component, self._default_adapter)

        # Register built-in adapters for common components. 

        from .column import make_qt_column_adapter
        from .row import make_qt_row_adapter
        from .divider import make_qt_divider_adapter
        from .image import QtImageAdapter
        from .switch import QtSwitchAdapter
        from .link import QtLinkAdapter
        from .badge import QtBadgeAdapter
        from .spinbox import QtSpinBoxAdapter
        from .box import make_qt_box_adapter
        from .radiogroup import make_qt_radiogroup_adapter
        self.adapters.register("Divider", make_qt_divider_adapter(self))
        self.adapters.register("Column", make_qt_column_adapter(self))
        self.adapters.register("Row", make_qt_row_adapter(self))
        self.adapters.register("Image", QtImageAdapter())
        self.adapters.register("Switch", QtSwitchAdapter())
        self.adapters.register("Link", QtLinkAdapter())
        self.adapters.register("Badge", QtBadgeAdapter())
        self.adapters.register("SpinBox", QtSpinBoxAdapter())
        self.adapters.register("Box", make_qt_box_adapter(self))
        self.adapters.register("RadioGroup", make_qt_radiogroup_adapter(self))

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

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
        # type: ignore[return-value]
        return self._adapter_for(adapter_key(node)).create(self, node, parent)

    def _adapter_create(self, node: VNode, parent: object | None) -> QtHandle:
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
        return QtHandle(node.type, widget, props=dict(node.props))

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        self._adapter_for(handle_adapter_key(handle)).update(
            self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _handle(handle)
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
        _layout(_handle(parent)).insertWidget(index, _handle(child).widget)

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
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
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PyQt6", argv)


class PyQt5Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PyQt5", argv)


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
