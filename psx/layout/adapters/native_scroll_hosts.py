"""Apply immutable SFLE Scroll geometry to native viewport hosts.

The caller owns the UI thread and must validate its layout generation before
calling a host port. Scroll offsets never mutate SFLE Rect values.
"""
from __future__ import annotations

from dataclasses import dataclass

from psx.layout.scroll.native_scroll_viewport import ScrollViewportBinding
from psx.layout.scroll.scroll_offsets import ScrollOffset, clamp_scroll_offset


@dataclass(frozen=True, slots=True)
class ScrollHostGeometry:
    offset: ScrollOffset
    viewport_size: tuple[float, float]
    content_size: tuple[float, float]


def binding_from_host(props: dict, viewport: object, content: object) -> ScrollViewportBinding:
    """Adapt SFLE boxes and validated Scroll props without layout recomputation."""
    from psx.layout.contracts.model import Rect

    axes = props["direction"]
    enabled = bool(props["enabled"])
    return ScrollViewportBinding(
        axes, enabled,
        Rect(viewport.x, viewport.y, viewport.width, viewport.height),
        Rect(content.x, content.y, content.width, content.height),
        enabled and axes in ("horizontal", "both"),
        enabled and axes in ("vertical", "both"),
    )


def host_geometry(binding: ScrollViewportBinding, offset: ScrollOffset) -> ScrollHostGeometry:
    """Resolve axes and overflow once, independently of native coordinates."""
    position = clamp_scroll_offset(binding, offset)
    return ScrollHostGeometry(
        position,
        (binding.viewport.width, binding.viewport.height),
        (binding.content.width, binding.content.height),
    )


def apply_qt_scroll(area: object, binding: ScrollViewportBinding,
                    offset: ScrollOffset) -> ScrollHostGeometry:
    from psx.renderers.qt.scroll_host import apply_qt_scroll as commit
    return commit(area, binding, offset)


def apply_tk_scroll(outer: object, binding: ScrollViewportBinding,
                    offset: ScrollOffset) -> ScrollHostGeometry:
    from psx.renderers.tkinter.scroll_host import apply_tk_scroll as commit
    return commit(outer, binding, offset)


def apply_kivy_scroll(view: object, binding: ScrollViewportBinding,
                      offset: ScrollOffset) -> ScrollHostGeometry:
    from psx.renderers.kivy.scroll_host import apply_kivy_scroll as commit
    return commit(view, binding, offset)


def apply_headless_scroll(binding: ScrollViewportBinding,
                          offset: ScrollOffset) -> ScrollHostGeometry:
    """Return a deterministic projection without touching a native widget."""
    return host_geometry(binding, offset)
