"""Backend-owned native scroll extent/offset projection.

Cinnamon emits immutable viewport and content geometry. This module only
commits it to the already mounted native widget.
"""
from __future__ import annotations
from psx.layout.adapters.native_scroll_hosts import host_geometry, ScrollHostGeometry
from psx.layout.scroll.native_scroll_viewport import ScrollViewportBinding
from psx.layout.scroll.scroll_offsets import ScrollOffset

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
    # The native Canvas fills the viewport outside its child window. Its
    # default theme color must not leak through an explicitly painted CSS
    # content root when the viewport is taller than its content.
    background = None
    native_content = getattr(outer, "_psx_content", None)
    # GridItem may sit between Scroll's content frame and the CSS-painted
    # formatting root. The viewport must not show a theme color in the
    # space outside that root or while its native children are repositioned.
    # Walk only the single-content chain; do not borrow a card's background.
    candidate = native_content
    while candidate is not None:
        background = getattr(candidate, "_psx_css_background", None)
        if background is not None:
            break
        get_children = getattr(candidate, "winfo_children", None)
        children = get_children() if callable(get_children) else ()
        children = [child for child in children
                    if child is not getattr(candidate, "_psx_css_fill_canvas", None)]
        candidate = children[0] if len(children) == 1 else None
    if background is not None:
        canvas.configure(background=background)
        if native_content is not None and hasattr(native_content, "configure"):
            try:
                native_content.configure(style=(
                    f"PsxScrollContent{id(native_content)}.TFrame"))
                from tkinter import ttk
                ttk.Style(native_content).configure(
                    native_content.cget("style"), background=background)
            except (AttributeError, TypeError):
                pass
    outer._psx_scroll_region = region
    # Tk fractions address the entire content extent, not the overflow extent.
    canvas.xview_moveto(geometry.offset.x / content_width if content_width else 0.0)
    canvas.yview_moveto(geometry.offset.y / content_height if content_height else 0.0)
    outer._psx_scroll_logical_offset = geometry.offset
    return geometry
