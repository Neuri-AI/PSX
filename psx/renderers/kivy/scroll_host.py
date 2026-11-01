"""Backend-owned native scroll extent/offset projection.

Cinnamon emits immutable viewport and content geometry. This module only
commits it to the already mounted native widget.
"""
from __future__ import annotations
from psx.layout.adapters.native_scroll_hosts import host_geometry, ScrollHostGeometry
from psx.layout.scroll.native_scroll_viewport import ScrollViewportBinding
from psx.layout.scroll.scroll_offsets import ScrollOffset

def apply_kivy_scroll(view: object, binding: ScrollViewportBinding,
                      offset: ScrollOffset) -> ScrollHostGeometry:
    """Translate SFLE top-left Y offsets to Kivy's bottom-left scroll fraction."""
    geometry = host_geometry(binding, offset)
    content = view._psx_content
    # Kivy dispatches size/scroll property changes synchronously. Repeating
    # unchanged writes while Cinnamon commits can re-enter native ScrollView
    # positioning callbacks during viewport resizing or sidebar updates.
    if tuple(getattr(content, "size_hint", ())) != (None, None):
        content.size_hint = (None, None)
    if tuple(getattr(content, "size", ())) != geometry.content_size:
        content.size = geometry.content_size
    scroll_x = (geometry.offset.x / binding.overflow_x
                if binding.clip_x and binding.overflow_x else 0.0)
    scroll_y = (1.0 - geometry.offset.y / binding.overflow_y
                if binding.clip_y and binding.overflow_y else 1.0)
    if getattr(view, "scroll_x", None) != scroll_x:
        view.scroll_x = scroll_x
    if getattr(view, "scroll_y", None) != scroll_y:
        view.scroll_y = scroll_y
    view._psx_scroll_logical_offset = geometry.offset
    view._psx_scroll_previous_overflow = (binding.overflow_x, binding.overflow_y)
    return geometry
