"""Backend-owned native scroll extent/offset projection.

Cinnamon emits immutable viewport and content geometry. This module only
commits it to the already mounted native widget.
"""
from __future__ import annotations
from psx.layout.adapters.native_scroll_hosts import host_geometry, ScrollHostGeometry
from psx.layout.scroll.native_scroll_viewport import ScrollViewportBinding
from psx.layout.scroll.scroll_offsets import ScrollOffset

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
    area._psx_scroll_logical_offset = geometry.offset
    return geometry
