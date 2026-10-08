"""PySide6 renderer for the M2 portable primitive subset.

This module is deliberately the only M2 module that imports PySide6.  Importing
``psx`` itself remains safe in projects without a Qt binding.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget
from psx.core.vnode import NodeKind, VNode


@dataclass(slots=True)
class QtHandle:
    """Logical host representation; a layout container is still one QWidget in M2."""

    node_type: object
    widget: QWidget
    layout: QHBoxLayout | QVBoxLayout | None = None
    native: NativeWidget | None = None
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
        self.requested.connect(self._invoke, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _invoke(self, callback: Callable[[], None]) -> None:
        callback()


class PySide6Renderer:
    """Maps the M1 primitive contract to real PySide6 widgets and layouts."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self.application = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
        self._dispatcher = _UiDispatcher()

    def create(self, node: VNode, parent: object | None) -> QtHandle:
        _validate_props(node)
        if node.kind is NodeKind.NATIVE:
            native_parent = _as_handle(parent).widget if parent is not None else None
            return self._native(node, native_parent)
        if node.kind is NodeKind.FRAGMENT:
            return self._container(node, vertical=True)
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(f"PySide6 cannot create node kind {node.kind.value!r}.")
        if node.type == "Column":
            return self._container(node, vertical=True)
        if node.type == "Row":
            return self._container(node, vertical=False)
        if node.type == "Text":
            return QtHandle(node.type, QLabel(str(node.props["value"])))
        if node.type == "Button":
            button = QPushButton(str(node.props["label"]))
            button.setEnabled(bool(node.props.get("enabled", True)))
            return QtHandle(node.type, button)
        raise RendererCapabilityError(f"PySide6 does not support host primitive {node.type!r}.")

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _as_handle(handle)
        if target.native is not None:
            if (changed or removed) and target.native.update is None:
                raise RendererCapabilityError(
                    f"Native widget {target.native.name!r} received prop changes but has no update adapter."
                )
            if target.native.update is not None:
                target.native.update(target.widget, changed, removed)
            return
        # Layout properties are optional.  In particular, a hot update may
        # change ``<Column padding={24}>`` to ``<Column>``.  Treating that
        # removal as unsupported made an optional prop impossible to remove
        # without restarting the application.
        unsupported = (set(removed) - {"spacing", "padding"}) | (
            set(changed) - {"value", "label", "enabled", "spacing", "padding"}
        )
        if unsupported:
            raise RendererCapabilityError(
                f"Unsupported PySide6 props for {target.node_type!r}: {', '.join(sorted(unsupported))}"
            )
        if "spacing" in changed or "spacing" in removed:
            if target.layout is None:
                raise RendererCapabilityError("spacing is only supported by Row and Column.")
            target.layout.setSpacing(int(changed.get("spacing", 0)))
        if "padding" in changed or "padding" in removed:
            if target.layout is None:
                raise RendererCapabilityError("padding is only supported by Row and Column.")
            padding = int(changed.get("padding", 0))
            target.layout.setContentsMargins(padding, padding, padding, padding)
        if "value" in changed:
            if not isinstance(target.widget, QLabel):
                raise RendererCapabilityError("value is only supported by Text.")
            target.widget.setText(str(changed["value"]))
        if "label" in changed:
            if not isinstance(target.widget, QPushButton):
                raise RendererCapabilityError("label is only supported by Button.")
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
        target = _as_handle(handle)
        if target.native is not None:
            if target.native.bind_event is None:
                raise RendererCapabilityError(
                    f"Native widget {target.native.name!r} has no event adapter for {event!r}."
                )
            disposer = target.native.bind_event(target.widget, event, slot)
            if not callable(disposer):
                raise TypeError("NativeWidget.bind_event must return a callable disposer.")
            return NativeEventSubscription(disposer)
        if event != "on_click" or not isinstance(target.widget, QPushButton):
            raise RendererCapabilityError(f"{event} is not supported by {target.node_type!r} in M2.")

        def callback(_checked: bool = False) -> object | None:
            return slot.invoke()

        target.widget.clicked.connect(callback)
        return QtEventSubscription(target.widget.clicked, callback)

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, NativeEventSubscription):
            try:
                subscription.dispose()
            except (RuntimeError, TypeError):
                pass
            return
        target = _as_subscription(subscription)
        try:
            target.signal.disconnect(target.callback)  # type: ignore[union-attr]
        except (RuntimeError, TypeError):
            # Native deletion can disconnect a Qt signal before PSX disposes it.
            pass

    def destroy(self, handle: object) -> None:
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
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'pyside6'."
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
        if not isinstance(widget, QWidget):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a PySide6 QWidget, got {type(widget).__name__}."
            )
        original_parent = widget.parentWidget() if declaration.ownership is NativeOwnership.BORROWED else None
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
        raise TypeError("PySide6Renderer received a foreign event subscription.")
    return value


def _layout_for(handle: QtHandle) -> QHBoxLayout | QVBoxLayout:
    if handle.layout is None:
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in M2.")
    return handle.layout


def _validate_props(node: VNode) -> None:
    if node.kind is NodeKind.NATIVE:
        return
    if node.kind is NodeKind.FRAGMENT:
        allowed = {"spacing"}
    elif node.type in {"Column", "Row"}:
        allowed = {"spacing", "padding"}
    elif node.type == "Text":
        allowed = {"value"}
    elif node.type == "Button":
        allowed = {"label", "enabled", "on_click"}
    else:
        return
    unsupported = set(node.props) - allowed
    if unsupported:
        raise RendererCapabilityError(
            f"Unsupported PySide6 props for {node.type!r}: {', '.join(sorted(unsupported))}"
        )
