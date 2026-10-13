"""Apply immutable SFLE Scroll geometry to native viewport hosts.

The caller owns the UI thread and must validate its layout generation before
calling a host port. Scroll offsets never mutate SFLE Rect values.
"""
from __future__ import annotations

from dataclasses import dataclass

from .native_scroll_viewport import ScrollViewportBinding
from .scroll_offsets import ScrollOffset, clamp_scroll_offset


@dataclass(frozen=True, slots=True)
class ScrollHostGeometry:
    offset: ScrollOffset
    viewport_size: tuple[float, float]
    content_size: tuple[float, float]


def binding_from_host(props: dict, viewport: object, content: object) -> ScrollViewportBinding:
    """Adapt SFLE boxes and validated Scroll props without layout recomputation."""
    from .model import Rect

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
    """Bind SFLE content extent and logical top-left offsets to QScrollArea."""
    geometry = host_geometry(binding, offset)
    content = area._psx_content
    content.resize(round(geometry.content_size[0]), round(geometry.content_size[1]))
    horizontal = area.horizontalScrollBar()
    vertical = area.verticalScrollBar()
    # Hidden/offscreen QScrollArea widgets may not have calculated scroll
    # ranges yet. SFLE's viewport and content extents are authoritative.
    if hasattr(horizontal, "setRange"):
        horizontal.setRange(0, round(binding.overflow_x) if binding.clip_x else 0)
    if hasattr(vertical, "setRange"):
        vertical.setRange(0, round(binding.overflow_y) if binding.clip_y else 0)
    horizontal.setValue(round(geometry.offset.x))
    vertical.setValue(round(geometry.offset.y))
    return geometry


def apply_tk_scroll(outer: object, binding: ScrollViewportBinding,
                    offset: ScrollOffset) -> ScrollHostGeometry:
    """Use Canvas clipping and scrollregion, never requested native child size."""
    geometry = host_geometry(binding, offset)
    canvas = outer._psx_canvas
    content_width, content_height = geometry.content_size
    canvas.itemconfigure(outer._psx_window, width=round(content_width),
                         height=round(content_height))
    region = (0, 0, round(content_width), round(content_height))
    canvas.configure(scrollregion=region)
    outer._psx_scroll_region = region
    # Tk fractions address the entire content extent, not the overflow extent.
    canvas.xview_moveto(geometry.offset.x / content_width if content_width else 0.0)
    canvas.yview_moveto(geometry.offset.y / content_height if content_height else 0.0)
    return geometry


def apply_kivy_scroll(view: object, binding: ScrollViewportBinding,
                      offset: ScrollOffset) -> ScrollHostGeometry:
    """Translate SFLE top-left Y offsets to Kivy's bottom-left scroll fraction."""
    geometry = host_geometry(binding, offset)
    content = view._psx_content
    content.size_hint = (None, None)
    content.size = geometry.content_size
    view.scroll_x = (geometry.offset.x / binding.overflow_x
                     if binding.clip_x and binding.overflow_x else 0.0)
    view.scroll_y = (1.0 - geometry.offset.y / binding.overflow_y
                     if binding.clip_y and binding.overflow_y else 1.0)
    return geometry


def apply_headless_scroll(binding: ScrollViewportBinding,
                          offset: ScrollOffset) -> ScrollHostGeometry:
    """Return a deterministic projection without touching a native widget."""
    return host_geometry(binding, offset)
