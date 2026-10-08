"""Renderer-specific escape hatches for existing native controls.

The core deliberately knows nothing about a GUI toolkit.  A ``NativeWidget``
describes the ownership contract and lets a renderer opt in explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
import importlib
from typing import TypeAlias

from .events import EventSlot


class NativeOwnership(str, Enum):
    """Who disposes the native widget when its PSX node is unmounted."""

    OWNED = "owned"
    BORROWED = "borrowed"


NativeUpdate: TypeAlias = Callable[[object, Mapping[str, object], frozenset[str]], None]
NativeBindEvent: TypeAlias = Callable[[object, str, EventSlot], Callable[[], None]]
_SIGNAL_PREFIX = "on_native_signal:"


@dataclass(frozen=True, slots=True)
class NativeWidget:
    """A renderer-bound native widget declaration.

    Exactly one of ``factory`` (PSX-owned) or ``widget`` (borrowed) is
    required.  ``update`` receives the native widget, changed props and
    removed prop names.  A declaration is intentionally renderer-specific:
    passing it to another renderer produces a capability error instead of a
    best-effort conversion.
    """

    renderer: str
    factory: Callable[..., object] | None = None
    takes_parent: bool = False
    widget: object | None = None
    update: NativeUpdate | None = None
    bind_event: NativeBindEvent | None = None
    ownership: NativeOwnership = NativeOwnership.OWNED
    name: str = "NativeWidget"

    def __post_init__(self) -> None:
        if isinstance(self.ownership, str):
            try:
                object.__setattr__(self, "ownership", NativeOwnership(self.ownership))
            except ValueError as error:
                raise ValueError("NativeWidget.ownership must be 'owned' or 'borrowed'.") from error
        if not self.renderer:
            raise ValueError("NativeWidget.renderer must identify a renderer.")
        if (self.factory is None) == (self.widget is None):
            raise ValueError("NativeWidget requires exactly one of factory or widget.")
        if self.factory is not None and not callable(self.factory):
            raise TypeError("NativeWidget.factory must be callable.")
        if not isinstance(self.takes_parent, bool):
            raise TypeError("NativeWidget.takes_parent must be a bool.")
        if self.takes_parent and self.factory is None:
            raise ValueError("NativeWidget.takes_parent requires a factory.")
        if self.widget is not None and self.ownership is not NativeOwnership.BORROWED:
            raise ValueError("A supplied native widget must use ownership='borrowed'.")
        if self.factory is not None and self.ownership is not NativeOwnership.OWNED:
            raise ValueError("A native widget factory must use ownership='owned'.")
        if self.update is not None and not callable(self.update):
            raise TypeError("NativeWidget.update must be callable or None.")
        if self.bind_event is not None and not callable(self.bind_event):
            raise TypeError("NativeWidget.bind_event must be callable or None.")


def Native(
    widget: object,
    *,
    props: Mapping[str, object] | None = None,
    signals: Mapping[str, Callable[..., object] | None] | None = None,
    renderer: str | None = None,
    key: str | int | None = None,
    ref: object | None = None,
    **attributes: object,
):
    """Mount a native control while retaining PSX reconciliation semantics.

    ``widget`` is normally a native widget class (owned by PSX) or an existing
    widget instance (borrowed).  Backend selection is inferred from the class
    or instance; custom controls may pass ``renderer=`` explicitly.
    """
    from .vnode import native_widget

    selected = renderer or _infer_renderer(widget)
    if selected is None:
        raise TypeError(
            "Cannot infer a renderer for Native(); pass renderer='pyside6', "
            "renderer='pyqt6', renderer='pyqt5', renderer='tkinter', or renderer='kivy'."
        )
    selected = selected.lower()
    if selected not in {"pyside6", "pyqt6", "pyqt5", "tkinter", "kivy"}:
        raise ValueError(f"Unsupported Native renderer {selected!r}.")
    if isinstance(widget, type) or callable(widget):
        declaration = NativeWidget(
            renderer=selected,
            factory=widget,  # type: ignore[arg-type]
            takes_parent=selected == "tkinter",
            update=_update_for(selected),
            bind_event=_bind_for(selected),
            name=getattr(widget, "__name__", type(widget).__name__),
        )
    else:
        declaration = NativeWidget(
            renderer=selected,
            widget=widget,
            ownership=NativeOwnership.BORROWED,
            update=_update_for(selected),
            bind_event=_bind_for(selected),
            name=type(widget).__name__,
        )
    values = dict(props or {})
    overlap = set(values) & set(attributes)
    if overlap:
        raise TypeError(f"Native props were passed twice: {', '.join(sorted(overlap))}")
    values.update(attributes)
    for signal, callback in (signals or {}).items():
        if not isinstance(signal, str) or not signal:
            raise TypeError("Native signal names must be non-empty strings.")
        if callback is not None and not callable(callback):
            raise TypeError(f"Native signal {signal!r} must be callable or None.")
        values[f"{_SIGNAL_PREFIX}{signal}"] = callback
    return native_widget(declaration, key=key, ref=ref, **values)


def _infer_renderer(value: object) -> str | None:
    candidate = value if isinstance(value, type) else type(value)
    for cls in getattr(candidate, "__mro__", (candidate,)):
        module = getattr(cls, "__module__", "")
        if module.startswith("PySide6."):
            return "pyside6"
        if module.startswith("PyQt6."):
            return "pyqt6"
        if module.startswith("PyQt5."):
            return "pyqt5"
        if module.startswith("tkinter"):
            return "tkinter"
        if module.startswith("kivy."):
            return "kivy"
    return None


def _update_for(renderer: str) -> NativeUpdate:
    return _qt_update if renderer.startswith("py") else (_tk_update if renderer == "tkinter" else _kivy_update)


def _bind_for(renderer: str) -> NativeBindEvent:
    return _qt_bind if renderer.startswith("py") else (_tk_bind if renderer == "tkinter" else _kivy_bind)


def _removed(removed: frozenset[str]) -> None:
    if removed:
        raise ValueError(
            "Native props cannot be removed without a specialized adapter: " + ", ".join(sorted(removed))
        )


def _qt_update(widget: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    _removed(removed)
    for name, value in changed.items():
        setter = getattr(widget, f"set{name[:1].upper()}{name[1:]}", None)
        if name == "url" and callable(setter) and type(value).__name__ != "QUrl":
            root = type(widget).__module__.split(".", 1)[0]
            value = importlib.import_module(f"{root}.QtCore").QUrl(str(value))
        if callable(setter):
            setter(value)
        elif hasattr(widget, "setProperty") and widget.setProperty(name, value):  # type: ignore[attr-defined]
            continue
        elif hasattr(widget, name):
            setattr(widget, name, value)
        else:
            raise AttributeError(f"{type(widget).__name__} has no native property {name!r}.")


def _qt_bind(widget: object, event: str, slot: EventSlot) -> Callable[[], None]:
    signal_name = _native_signal_name(event)
    signal = getattr(widget, signal_name, None)
    if signal is None or not hasattr(signal, "connect"):
        raise AttributeError(f"{type(widget).__name__} has no Qt signal {signal_name!r}.")

    def callback(*args: object) -> object:
        return slot.invoke(*args)

    signal.connect(callback)

    def dispose() -> None:
        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            pass

    return dispose


def _tk_update(widget: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    _removed(removed)
    if changed:
        try:
            widget.configure(**changed)  # type: ignore[attr-defined]
        except Exception as error:
            raise AttributeError(f"Cannot configure native Tk widget {type(widget).__name__}.") from error


def _tk_bind(widget: object, event: str, slot: EventSlot) -> Callable[[], None]:
    signal_name = _native_signal_name(event)

    def callback(native_event: object) -> object:
        return slot.invoke(native_event)

    identifier = widget.bind(signal_name, callback, add="+")  # type: ignore[attr-defined]

    def dispose() -> None:
        widget.unbind(signal_name, identifier)  # type: ignore[attr-defined]

    return dispose


def _kivy_update(widget: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    _removed(removed)
    for name, value in changed.items():
        if not hasattr(widget, name):
            raise AttributeError(f"{type(widget).__name__} has no Kivy property {name!r}.")
        setattr(widget, name, value)


def _kivy_bind(widget: object, event: str, slot: EventSlot) -> Callable[[], None]:
    signal_name = _native_signal_name(event)

    def callback(*args: object) -> object:
        return slot.invoke(*args)

    widget.bind(**{signal_name: callback})  # type: ignore[attr-defined]

    def dispose() -> None:
        widget.unbind(**{signal_name: callback})  # type: ignore[attr-defined]

    return dispose


def _native_signal_name(event: str) -> str:
    if not event.startswith(_SIGNAL_PREFIX):
        raise ValueError(f"Native event {event!r} was not declared through signals={{...}}.")
    return event[len(_SIGNAL_PREFIX) :]
