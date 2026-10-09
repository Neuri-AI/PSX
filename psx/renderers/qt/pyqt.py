"""PyQt5/PyQt6 renderers for PSX's portable primitive subset."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import NodeKind, VNode, validate_text_props, validate_button_props, validate_checkbox_props
from psx.renderers.button import apply_qt_button, updated_button_props
from psx.renderers.text import apply_qt_text, updated_text_props
from psx.renderers.checkbox import apply_qt_checkbox, updated_checkbox_props
from psx.renderers.adapters import AdapterSubscription, DelegatingAdapter, RendererAdapterRegistry, adapter_key, handle_adapter_key


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


class _PyQtRenderer:
    def __init__(self, binding: str, argv: list[str] | None = None) -> None:
        self._binding = binding.lower()
        self._binding_package = binding
        core = importlib.import_module(f"{binding}.QtCore")
        widgets = importlib.import_module(f"{binding}.QtWidgets")
        self._qt = core.Qt
        self._widget = widgets.QWidget
        self._label = widgets.QLabel
        self._button = widgets.QPushButton
        self._checkbox = widgets.QCheckBox
        self._vbox = widgets.QVBoxLayout
        self._hbox = widgets.QHBoxLayout
        application = widgets.QApplication
        self.application = application.instance() or application(argv if argv is not None else sys.argv)
        signal = getattr(core, "pyqtSignal")
        slot = getattr(core, "pyqtSlot")
        queued = getattr(getattr(self._qt, "ConnectionType", self._qt), "QueuedConnection")

        class Dispatcher(core.QObject):
            requested = signal(object)

            def __init__(self) -> None:
                super().__init__()
                self.requested.connect(self._invoke, queued)

            @slot(object)
            def _invoke(self, callback: Callable[[], None]) -> None:
                callback()

        self._dispatcher = Dispatcher()
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in ("Column", "Row", "Fragment", "Text", "Button", "Input", "Checkbox", "Native"):
            self.adapters.register(component, self._default_adapter)

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def create(self, node: VNode, parent: object | None) -> QtHandle:
        adapter = self.adapters.get(adapter_key(node)) or self._default_adapter
        return adapter.create(self, node, parent)  # type: ignore[return-value]

    def _adapter_create(self, node: VNode, parent: object | None) -> QtHandle:
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _handle(parent).widget if parent is not None else None
            return self._native(node, native_parent)
        if node.kind is NodeKind.FRAGMENT or node.type == "Column":
            return self._container(node, vertical=True)
        if node.type == "Row":
            return self._container(node, vertical=False)
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(f"PyQt cannot create node kind {node.kind.value!r}.")
        if node.type == "Text":
            widget = self._label()
            apply_qt_text(widget, node.props, self._binding_package)
            return QtHandle(node.type, widget, props=dict(node.props))
        if node.type == "Button":
            button = self._button()
            apply_qt_button(button, node.props, self._binding_package)
            return QtHandle(node.type, button, props=dict(node.props))
        if node.type == "Checkbox":
            widget = self._checkbox()
            apply_qt_checkbox(widget, node.props)
            return QtHandle(node.type, widget, props=dict(node.props))
        raise RendererCapabilityError(f"PyQt does not support host primitive {node.type!r}.")

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
            apply_qt_text(target.widget, props, self._binding_package)
            target.props = props
            return
        if target.node_type == "Button":
            props = updated_button_props(target.props, changed, removed)
            apply_qt_button(target.widget, props, self._binding_package)
            target.props = props
            return
        if target.node_type == "Checkbox":
            props = updated_checkbox_props(target.props, changed, removed)
            apply_qt_checkbox(target.widget, props)
            target.props = props
            return
        unsupported = set(removed) | (set(changed) - {"label", "enabled", "spacing", "padding"})
        if unsupported:
            raise RendererCapabilityError(f"Unsupported PyQt props: {', '.join(sorted(unsupported))}")
        if {"spacing", "padding"} & (set(changed) | set(removed)):
            layout = _layout(target)
            if "spacing" in changed or "spacing" in removed:
                layout.setSpacing(int(changed.get("spacing", 0)))
            if "padding" in changed or "padding" in removed:
                padding = int(changed.get("padding", 0))
                layout.setContentsMargins(padding, padding, padding, padding)
        if "label" in changed:
            target.widget.setText(str(changed["label"]))
        if "enabled" in changed:
            target.widget.setEnabled(bool(changed["enabled"]))

    def insert(self, parent: object, child: object, index: int) -> None:
        _layout(_handle(parent)).insertWidget(index, _handle(child).widget)

    def move(self, parent: object, child: object, index: int) -> None:
        layout = _layout(_handle(parent))
        widget = _handle(child).widget
        layout.removeWidget(widget)
        layout.insertWidget(index, widget)

    def remove(self, parent: object, child: object) -> None:
        handle = _handle(child)
        item = handle.widget
        _layout(_handle(parent)).removeWidget(item)
        item.setParent(handle.original_parent if handle.native is not None and handle.native.ownership is NativeOwnership.BORROWED else None)

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
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
                raise TypeError("NativeWidget.bind_event must return a callable disposer.")
            return NativeEventSubscription(disposer)
        if event != "on_click" or not isinstance(target.widget, self._button):
            if event == "on_change" and isinstance(target.widget, self._checkbox):
                def changed(value: bool) -> object | None:
                    return slot.invoke(bool(value))
                target.widget.toggled.connect(changed)
                return QtEventSubscription(target.widget.toggled, changed)
            raise RendererCapabilityError(f"{event} is not supported by {target.node_type!r} in PyQt.")
        def callback(_checked: bool = False) -> object | None:
            return slot.invoke()
        target.widget.clicked.connect(callback)
        return QtEventSubscription(target.widget.clicked, callback)

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
            pass

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        widget = target.widget
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            widget.setParent(target.original_parent)
            return
        widget.setParent(None)
        widget.deleteLater()

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        self._dispatcher.requested.emit(callback)

    def run(self) -> int:
        return self.application.exec()

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
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not {self._binding!r}."
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
        if not isinstance(widget, self._widget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a {self._binding} QWidget, got {type(widget).__name__}."
            )
        original_parent = widget.parentWidget() if declaration.ownership is NativeOwnership.BORROWED else None
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if declaration.ownership is NativeOwnership.OWNED:
                widget.setParent(None)
                widget.deleteLater()
            raise
        return QtHandle(declaration, widget, native=declaration, original_parent=original_parent)


class PyQt6Renderer(_PyQtRenderer):
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PyQt6", argv)


class PyQt5Renderer(_PyQtRenderer):
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PyQt5", argv)


def _handle(value: object) -> QtHandle:
    if not isinstance(value, QtHandle):
        raise TypeError("PyQt renderer received a foreign handle.")
    return value


def _layout(handle: QtHandle) -> object:
    if handle.layout is None:
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in PyQt.")
    return handle.layout


def _subscription(value: object) -> QtEventSubscription:
    if not isinstance(value, QtEventSubscription):
        raise TypeError("PyQt renderer received a foreign event subscription.")
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
    allowed = {"spacing", "padding"} if node.kind is NodeKind.FRAGMENT or node.type in {"Column", "Row"} else set()
    unsupported = set(node.props) - allowed
    if unsupported:
        raise RendererCapabilityError(f"Unsupported PyQt props for {node.type!r}: {', '.join(sorted(unsupported))}")
