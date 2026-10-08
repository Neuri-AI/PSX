"""Stable callback slots used by renderer event bindings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class EventSlot:
    """A native connection invokes this stable object, not a render-time lambda."""

    __slots__ = ("_callback", "_active")

    def __init__(self, callback: Callable[..., object] | None) -> None:
        self._callback = callback
        self._active = True

    def update(self, callback: Callable[..., object] | None) -> None:
        self._callback = callback

    def dispose(self) -> None:
        self._active = False
        self._callback = None

    def invoke(self, *args: object, **kwargs: object) -> object | None:
        if self._active and self._callback is not None:
            return self._callback(*args, **kwargs)
        return None
