"""PySide6 renderer for PSX's portable primitive subset.

The PySide6 binding is imported only when this adapter is loaded.  Importing
``psx`` itself remains safe in projects without a Qt binding.
"""

from psx.core.errors import RendererCapabilityError
from psx.renderers.button import apply_qt_button, updated_button_props
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import NodeKind, VNode, validate_text_props, validate_button_props, validate_checkbox_props, validate_input_props
from psx.renderers.text import apply_qt_text, updated_text_props
from psx.renderers.input import apply_qt_input, updated_input_props
from psx.renderers.checkbox import apply_qt_checkbox, updated_checkbox_props
from psx.renderers.adapters import AdapterSubscription, DelegatingAdapter, RendererAdapterRegistry, adapter_key, handle_adapter_key


@dataclass(slots=True)
class QtHandle:
    """Logical host representation; a layout container is represented by one QWidget."""

    node_type: object
    widget: QWidget
    layout: QHBoxLayout | QVBoxLayout | None = None
    native: NativeWidget | None = None
    props: dict[str, object] = field(default_factory=dict)
    original_parent: QWidget | None = None


@dataclass(slots=True)
class QtEventSubscription:
    signal: object
    callback: Callable[..., object]


@dataclass(slots=True)
class NativeEventSubscription:
    dispose: Callable[[], None]


class _UiDispatcher(QObject):
    """A QObject-affine bridge that queues work from any Python thread to Qt's UI loop."""

    requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.requested.connect(
            self._invoke, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _invoke(self, callback: Callable[[], None]) -> None:
        callback()


class PySide6Renderer:
    """Maps the portable primitive contract to real PySide6 widgets and layouts."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self.application = QApplication.instance() or QApplication(
            argv if argv is not None else sys.argv)
        self._dispatcher = _UiDispatcher()
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
            native_parent = _as_handle(
                parent).widget if parent is not None else None
            return self._native(node, native_parent)
        if node.kind is NodeKind.FRAGMENT:
            return self._container(node, vertical=True)
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(
                f"PySide6 cannot create node kind {node.kind.value!r}.")
        if node.type == "Column":
            return self._container(node, vertical=True)
        if node.type == "Row":
            return self._container(node, vertical=False)
        if node.type == "Text":
            widget = QLabel()
            apply_qt_text(widget, node.props, "PySide6")
            return QtHandle(node.type, widget, props=dict(node.props))
        if node.type == "Button":
            validate_button_props(node.props)
            button = QPushButton()
            apply_qt_button(button, node.props, "PySide6")
            return QtHandle(node.type, button, props=dict(node.props))
        if node.type == "Input":
            widget = QLineEdit()
            apply_qt_input(widget, node.props, "PySide6")
            return QtHandle(node.type, widget, props=dict(node.props))
        if node.type == "Checkbox":
            widget = QCheckBox()
            apply_qt_checkbox(widget, node.props)
            return QtHandle(node.type, widget, props=dict(node.props))
        raise RendererCapabilityError(
            f"PySide6 does not support host primitive {node.type!r}.")

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
            apply_qt_text(target.widget, props, "PySide6")
            target.props = props
            return
        if target.node_type == "Button":
            props = updated_button_props(target.props, changed, removed)
            apply_qt_button(target.widget, props, "PySide6")
            target.props = props
            return
        if target.node_type == "Input":
            props = updated_input_props(target.props, changed, removed)
            apply_qt_input(target.widget, props, "PySide6")
            target.props = props
            return
        if target.node_type == "Checkbox":
            props = updated_checkbox_props(target.props, changed, removed)
            apply_qt_checkbox(target.widget, props)
            target.props = props
            return
        unsupported = set(removed) | (
            set(changed) - {"label", "enabled", "spacing", "padding"})
        if unsupported:
            raise RendererCapabilityError(
                f"Unsupported PySide6 props for {target.node_type!r}: {', '.join(sorted(unsupported))}"
            )
        if "spacing" in changed or "spacing" in removed:
            if target.layout is None:
                raise RendererCapabilityError(
                    "spacing is only supported by Row and Column.")
            target.layout.setSpacing(int(changed["spacing"]))
        if "padding" in changed:
            if target.layout is None:
                raise RendererCapabilityError(
                    "padding is only supported by Row and Column.")
            padding = int(changed["padding"])
            target.layout.setContentsMargins(
                padding, padding, padding, padding)
        if "label" in changed:
            if not isinstance(target.widget, QPushButton):
                raise RendererCapabilityError(
                    "label is only supported by Button.")
            target.widget.setText(str(changed["label"]))
        if "enabled" in changed:
            target.widget.setEnabled(bool(changed["enabled"]))

    def insert(self, parent: object, child: object, index: int) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        layout = _layout_for(container)
        layout.insertWidget(index, item.widget)

    def move(self, parent: object, child: object, index: int) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        layout = _layout_for(container)
        layout.removeWidget(item.widget)
        layout.insertWidget(index, item.widget)

    def remove(self, parent: object, child: object) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        _layout_for(container).removeWidget(item.widget)
        if item.native is not None and item.native.ownership is NativeOwnership.BORROWED:
            item.widget.setParent(item.original_parent)
        else:
            item.widget.setParent(None)

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        target = _as_handle(handle)
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
        if isinstance(target.widget, QLineEdit):
            if event == "on_change":
                def callback(value: str) -> object | None:
                    return slot.invoke(value)
                target.widget.textChanged.connect(callback)
                return QtEventSubscription(target.widget.textChanged, callback)
            if event == "on_submit":
                def callback() -> object | None:
                    return slot.invoke()
                target.widget.returnPressed.connect(callback)
                return QtEventSubscription(target.widget.returnPressed, callback)
        if isinstance(target.widget, QCheckBox) and event == "on_change":
            def callback(value: bool) -> object | None:
                return slot.invoke(bool(value))
            target.widget.toggled.connect(callback)
            return QtEventSubscription(target.widget.toggled, callback)
            raise RendererCapabilityError(f"{event} is not supported by Input in PySide6.")
        if event != "on_click" or not isinstance(target.widget, QPushButton):
            raise RendererCapabilityError(
                f"{event} is not supported by {target.node_type!r} in PySide6.")

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
        target = _as_subscription(subscription)
        try:
            # type: ignore[union-attr]
            target.signal.disconnect(target.callback)
        except (RuntimeError, TypeError):
            # Native deletion can disconnect a Qt signal before PSX disposes it.
            pass

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _as_handle(handle)
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            target.widget.setParent(target.original_parent)
            return
        target.widget.setParent(None)
        target.widget.deleteLater()

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        self._dispatcher.requested.emit(callback)

    def run(self) -> int:
        return self.application.exec()

    @staticmethod
    def _container(node: VNode, *, vertical: bool) -> QtHandle:
        widget = QWidget()
        layout = QVBoxLayout(widget) if vertical else QHBoxLayout(widget)
        padding = int(node.props.get("padding", 0))
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(int(node.props.get("spacing", 0)))
        return QtHandle(node.type, widget, layout)

    @staticmethod
    def _native(node: VNode, parent: QWidget | None) -> QtHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "pyside6":
            renderer = declaration.renderer if isinstance(
                declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'pyside6'."
            )
        initial_props = {name: value for name,
                         value in node.props.items() if not name.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        widget = (
            declaration.factory(parent) if declaration.factory is not None and declaration.takes_parent
            else declaration.factory() if declaration.factory is not None else declaration.widget
        )
        if not isinstance(widget, QWidget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a PySide6 QWidget, got {type(widget).__name__}."
            )
        original_parent = widget.parentWidget(
        ) if declaration.ownership is NativeOwnership.BORROWED else None
        if declaration.update is not None:
            try:
                declaration.update(widget, initial_props, frozenset())
            except Exception:
                if declaration.ownership is NativeOwnership.OWNED:
                    widget.setParent(None)
                    widget.deleteLater()
                raise
        return QtHandle(declaration, widget, native=declaration, original_parent=original_parent)


def _as_handle(value: object) -> QtHandle:
    if not isinstance(value, QtHandle):
        raise TypeError("PySide6Renderer received a foreign handle.")
    return value


def _as_subscription(value: object) -> QtEventSubscription:
    if not isinstance(value, QtEventSubscription):
        raise TypeError(
            "PySide6Renderer received a foreign event subscription.")
    return value


def _layout_for(handle: QtHandle) -> QHBoxLayout | QVBoxLayout:
    if handle.layout is None:
        raise RendererCapabilityError(
            f"{handle.node_type!r} cannot contain PSX children in PySide6.")
    return handle.layout


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
    if node.kind is NodeKind.HOST and node.type == "Input":
        validate_input_props(node.props)
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
            f"Unsupported PySide6 props for {node.type!r}: {', '.join(sorted(unsupported))}"
        )
