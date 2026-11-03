"""Per-render stylesheet ownership, injected by an application context.

A ContextVar makes adjacent and nested app renders isolated without keeping
VNode references or changing the component constructor lifecycle.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from .sources import ResourceResolver


@dataclass(frozen=True, slots=True)
class CssResourceContext:
    stylesheets: tuple[str, ...]
    resolver: ResourceResolver | None = None
    root: Path = Path(".")


_current_css: ContextVar[CssResourceContext | None] = ContextVar("psx_css_context", default=None)


def current_css_context() -> CssResourceContext | None:
    return _current_css.get()


@contextmanager
def scoped_css_resources(
    stylesheets: tuple[str, ...] | list[str] = (),
    *,
    resolver: ResourceResolver | None = None,
    root: str | Path = ".",
) -> Iterator[None]:
    if not isinstance(stylesheets, (tuple, list)) or not all(isinstance(name, str) for name in stylesheets):
        raise TypeError("Application stylesheets must be a string sequence.")
    token = _current_css.set(CssResourceContext(tuple(stylesheets), resolver, Path(root)))
    try:
        yield
    finally:
        _current_css.reset(token)
