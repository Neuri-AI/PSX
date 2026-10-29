"""Renderer-specific escape hatches for existing native controls.

The core deliberately knows nothing about a GUI toolkit.  A ``NativeWidget``
describes the ownership contract and lets a renderer opt in explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from weakref import WeakKeyDictionary
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
_NATIVE_LAYOUT_PROPS = frozenset({"layout_width", "layout_height"})


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
    sfle_port: object | None = None

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
        if self.sfle_port is not None:
            from psx.sfle.external_native_geometry_ports import SFLEExternalPort
            if not isinstance(self.sfle_port, SFLEExternalPort):
                raise TypeError("NativeWidget.sfle_port requires SFLEExternalPort.")


def Native(
    widget: object,
    *,
    props: Mapping[str, object] | None = None,
    kwargs: Mapping[str, object] | None = None,
    args: tuple[object, ...] | None = None,
    signals: Mapping[str, Callable[..., object] | None] | None = None,
    renderer: str | None = None,
    sfle_port: object | None = None,
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
            "renderer='pyqt6', renderer='pyqt5', renderer='pyside2', renderer='tkinter', or renderer='kivy'."
        )
    selected = selected.lower()
    if selected not in {"pyside6", "pyside2", "pyqt6", "pyqt5", "tkinter", "kivy"}:
        raise ValueError(f"Unsupported Native renderer {selected!r}.")
    if sfle_port is None:
        sfle_port = _default_sfle_port(selected)
    if kwargs is not None and not isinstance(kwargs, Mapping):
        raise TypeError("Native kwargs must be a mapping.")
    if args is not None and not isinstance(args, (tuple, list)):
        raise TypeError("Native args must be a tuple or list.")
    if (kwargs or args) and not (isinstance(widget, type) or callable(widget)):
        raise TypeError("Native constructor args/kwargs require a widget class or factory.")
    factory = _ConstructorFactory(widget, tuple(args or ()), dict(kwargs or {})) if (args or kwargs) else widget
    if isinstance(widget, type) or callable(widget):
        declaration = NativeWidget(
            renderer=selected,
            factory=factory,  # type: ignore[arg-type]
            takes_parent=selected == "tkinter",
            update=_update_for(selected),
            bind_event=_bind_for(selected),
            sfle_port=sfle_port,
            name=getattr(widget, "__name__", type(widget).__name__),
        )
    else:
        declaration = NativeWidget(
            renderer=selected,
            widget=widget,
            ownership=NativeOwnership.BORROWED,
            update=_update_for(selected),
            bind_event=_bind_for(selected),
            sfle_port=sfle_port,
            name=type(widget).__name__,
        )
    values = dict(attributes)
    if props is not None:
        if not isinstance(props, Mapping):
            raise TypeError("Native props must be a mapping.")
        values["props"] = dict(props)
    # Sizing belongs to Cinnamon, never to the native toolkit property setter.
    # Both explicit Native(width=...) and CSS sizing share the same layout input.
    for axis in ("width", "height"):
        if axis in values:
            layout_axis = f"layout_{axis}"
            if layout_axis in values:
                raise TypeError(f"Native received both {axis} and {layout_axis}.")
            values[layout_axis] = values.pop(axis)
    for signal, callback in (signals or {}).items():
        if not isinstance(signal, str) or not signal:
            raise TypeError("Native signal names must be non-empty strings.")
        if callback is not None and not callable(callback):
            raise TypeError(f"Native signal {signal!r} must be callable or None.")
        values[f"{_SIGNAL_PREFIX}{signal}"] = callback
    return native_widget(declaration, key=key, ref=ref, **values)


class _ConstructorFactory:
    """Callable with value-based equality so normal rerenders preserve native identity."""

    def __init__(self, target: object, args: tuple[object, ...], kwargs: dict[str, object]):
        self.target = target
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *parent: object) -> object:
        return self.target(*parent, *self.args, **self.kwargs)  # type: ignore[operator]

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, _ConstructorFactory) and self.target is other.target
                and _native_equal(self.args, other.args)
                and _native_equal(self.kwargs, other.kwargs))


_native_adapters: dict[type, Callable[[object, Mapping[str, object], frozenset[str]], None]] = {}
_reactive_snapshots: WeakKeyDictionary = WeakKeyDictionary()


def native_adapter(widget_type: type):
    """Register a reactive Native handler for an unmodified third-party widget."""
    if not isinstance(widget_type, type):
        raise TypeError("native_adapter requires a widget class.")

    def register(callback):
        if not callable(callback):
            raise TypeError("Native adapter must be callable.")
        _native_adapters[widget_type] = callback
        return callback

    return register


def _native_equal(left: object, right: object) -> bool:
    if left is right:
        return True
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return (left.keys() == right.keys()
                and all(_native_equal(left[key], right[key]) for key in left))
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return len(left) == len(right) and all(
            _native_equal(a, b) for a, b in zip(left, right)
        )
    if type(left).__module__.startswith("numpy") or type(right).__module__.startswith("numpy"):
        return False  # New arrays are dirty; avoid O(N) comparisons on the UI thread.
    try:
        result = left == right
        return result if isinstance(result, bool) else False
    except (TypeError, ValueError):
        return False


def _apply_reactive_props(widget: object, props: object) -> None:
    if not isinstance(props, Mapping):
        raise TypeError("Native props must be a mapping.")
    previous = _reactive_snapshots.get(widget, {})
    removed = previous.keys() - props.keys()
    if removed:
        raise ValueError(f"Native reactive props removed without reset policy: {sorted(removed)}")
    changed = frozenset(
        name for name, value in props.items()
        if name not in previous or not _native_equal(previous[name], value)
    )
    if not changed:
        return
    handler = getattr(widget, "update_props", None)
    if not callable(handler):
        handler = next((_native_adapters[cls] for cls in type(widget).__mro__
                        if cls in _native_adapters), None)
        if handler is not None:
            handler = lambda p, c, update=handler: update(widget, p, c)
    if handler is None:
        raise TypeError(
            f"{type(widget).__name__} received reactive props but has no "
            "update_props(props, changed) method or @native_adapter."
        )
    handler(props, changed)
    _reactive_snapshots[widget] = dict(props)


@lru_cache(maxsize=6)
def _default_sfle_port(renderer: str) -> object | None:
    """Return the built-in geometry bridge for ordinary toolkit widgets.

    ``Native`` is the ergonomic API: standard Qt, Tkinter and Kivy widgets
    expose the operations SFLE needs. Advanced ``NativeWidget`` adapters stay
    explicit because their geometry contract cannot be inferred.
    """
    from psx.sfle.external_native_geometry_ports import SFLEExternalPort
    from psx.sfle.model import IntrinsicSizes, Rect

    if renderer == "tkinter":
        def measure_tk(widget: object, _constraints: object) -> IntrinsicSizes:
            width = max(0, widget.winfo_reqwidth())  # type: ignore[attr-defined]
            height = max(0, widget.winfo_reqheight())  # type: ignore[attr-defined]
            return IntrinsicSizes(width, width, height, height, width, height)

        def apply_tk(widget: object, rect: Rect) -> None:
            widget.place(  # type: ignore[attr-defined]
                x=round(rect.x), y=round(rect.y),
                width=round(rect.width), height=round(rect.height),
            )

        def read_tk(widget: object) -> Rect:
            placement = widget.place_info()  # type: ignore[attr-defined]
            return Rect(*(float(placement[axis]) for axis in ("x", "y", "width", "height")))

        return SFLEExternalPort(measure_tk, apply_tk, read_tk)

    if renderer == "kivy":
        def measure_kivy(widget: object, _constraints: object) -> IntrinsicSizes:
            minimum = getattr(widget, "minimum_size", (0, 0))
            preferred = getattr(widget, "size", minimum)
            min_width, min_height = (max(0, float(value)) for value in minimum)
            preferred_width = max(min_width, float(preferred[0]))
            preferred_height = max(min_height, float(preferred[1]))
            return IntrinsicSizes(
                min_width, preferred_width, min_height, preferred_height,
                preferred_width, preferred_height,
            )

        def apply_kivy(widget: object, rect: Rect) -> None:
            widget.pos = (rect.x, rect.y)  # type: ignore[attr-defined]
            widget.size = (rect.width, rect.height)  # type: ignore[attr-defined]

        def read_kivy(widget: object) -> Rect:
            return Rect(widget.x, widget.y, widget.width, widget.height)  # type: ignore[attr-defined]

        return SFLEExternalPort(measure_kivy, apply_kivy, read_kivy)

    if not renderer.startswith("py"):
        return None

    def measure(widget: object, _constraints: object) -> IntrinsicSizes:
        hint = widget.sizeHint()  # type: ignore[attr-defined]
        minimum = widget.minimumSizeHint()  # type: ignore[attr-defined]
        min_width = max(0, minimum.width())
        min_height = max(0, minimum.height())
        preferred_width = max(min_width, hint.width())
        preferred_height = max(min_height, hint.height())
        return IntrinsicSizes(
            min_width,
            preferred_width,
            min_height,
            preferred_height,
            preferred_width,
            preferred_height,
        )

    def apply(widget: object, rect: Rect) -> None:
        widget.setGeometry(  # type: ignore[attr-defined]
            round(rect.x), round(rect.y), round(rect.width), round(rect.height)
        )

    def read(widget: object) -> Rect:
        frame = widget.geometry()  # type: ignore[attr-defined]
        return Rect(frame.x(), frame.y(), frame.width(), frame.height())

    return SFLEExternalPort(measure, apply, read)


def _infer_renderer(value: object) -> str | None:
    candidate = value if isinstance(value, type) else type(value)
    for cls in getattr(candidate, "__mro__", (candidate,)):
        module = getattr(cls, "__module__", "")
        if module.startswith("PySide6."):
            return "pyside6"
        if module.startswith("PySide2."):
            return "pyside2"
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
    unsupported = removed - _NATIVE_LAYOUT_PROPS
    if unsupported:
        raise ValueError(
            "Native props cannot be removed without a specialized adapter: " + ", ".join(sorted(unsupported))
        )


def _qt_update(widget: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    _removed(removed)
    if "props" in changed:
        _apply_reactive_props(widget, changed["props"])
    for name, value in changed.items():
        if name == "props" or name in _NATIVE_LAYOUT_PROPS:
            continue
        # Respect both native Qt setFooBar and Pythonic set_foo_bar.
        # Avoid calling arbitrary methods: only property setters are eligible.
        parts = name.split("_")
        camel = "".join(part[:1].upper() + part[1:] for part in parts)
        candidates = (f"set_{name}", f"set{camel}")
        setter_name = next((candidate for candidate in candidates if callable(getattr(widget, candidate, None))), None)
        if setter_name is not None:
            setter = getattr(widget, setter_name)
            # Qt's setUrl expects QUrl; custom set_url methods retain the
            # original Python value and can perform their own conversion.
            if setter_name == "setUrl" and name == "url" and type(value).__name__ != "QUrl":
                root = type(widget).__module__.split(".", 1)[0]
                value = importlib.import_module(f"{root}.QtCore").QUrl(str(value))
            setter(value)
        elif hasattr(widget, "setProperty") and widget.setProperty(name, value):  # type: ignore[attr-defined]
            continue
        elif hasattr(widget, name) and not callable(getattr(widget, name)):
            setattr(widget, name, value)
        else:
            raise AttributeError(f"{type(widget).__name__} has no writable native property {name!r}.")


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
    if "props" in changed:
        _apply_reactive_props(widget, changed["props"])
    changed = {k: v for k, v in changed.items() if k != "props" and k not in _NATIVE_LAYOUT_PROPS}
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
    if "props" in changed:
        _apply_reactive_props(widget, changed["props"])
    for name, value in changed.items():
        if name == "props" or name in _NATIVE_LAYOUT_PROPS:
            continue
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
