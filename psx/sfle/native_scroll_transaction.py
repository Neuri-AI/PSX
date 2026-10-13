"""Transactional native Scroll viewport state, separate from immutable SFLE boxes.

Read and restore only mounted Scroll hosts, leaving focus and widget identity
untouched. Callers enforce UI-thread ownership and generation validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class ScrollHostSnapshot:
    host: object
    backend: str
    values: tuple
    logical: object
    previous_overflow: object


def capture_scroll_hosts(backend: str, handles: Mapping[str, object]) -> tuple[ScrollHostSnapshot, ...]:
    snapshots = []
    for handle in handles.values():
        host = getattr(handle, "widget", handle)
        if not getattr(host, "_psx_sfle_scroll", False):
            continue
        logical = getattr(host, "_psx_scroll_logical_offset", None)
        overflow = getattr(host, "_psx_scroll_previous_overflow", None)
        if backend == "qt":
            content = host._psx_content
            h, v = host.horizontalScrollBar(), host.verticalScrollBar()
            values = (content.width(), content.height(), h.maximum(), v.maximum(), h.value(), v.value())
        elif backend == "tk":
            canvas = host._psx_canvas
            values = (canvas.itemcget(host._psx_window, "width"),
                      canvas.itemcget(host._psx_window, "height"),
                      canvas.cget("scrollregion"), canvas.canvasx(0), canvas.canvasy(0),
                      host._psx_scroll_region)
        elif backend == "kivy":
            values = (tuple(host._psx_content.size), tuple(host._psx_content.size_hint),
                      host.scroll_x, host.scroll_y)
        else:
            raise ValueError("Unsupported native Scroll backend")
        snapshots.append(ScrollHostSnapshot(host, backend, values, logical, overflow))
    return tuple(snapshots)


def restore_scroll_hosts(snapshots: tuple[ScrollHostSnapshot, ...]) -> None:
    """Rollback native viewport extents and offsets if a commit fails."""
    for saved in reversed(snapshots):
        host, values = saved.host, saved.values
        if saved.backend == "qt":
            width, height, maximum_x, maximum_y, x, y = values
            host._psx_content.resize(width, height)
            h, v = host.horizontalScrollBar(), host.verticalScrollBar()
            h.setRange(0, maximum_x)
            v.setRange(0, maximum_y)
            h.setValue(x)
            v.setValue(y)
        elif saved.backend == "tk":
            width, height, region, x, y, cached_region = values
            canvas = host._psx_canvas
            canvas.itemconfigure(host._psx_window, width=width, height=height)
            canvas.configure(scrollregion=region)
            host._psx_scroll_region = cached_region
            limits = cached_region if cached_region is not None else (0, 0, 0, 0)
            canvas.xview_moveto(float(x) / max(1.0, float(limits[2])))
            canvas.yview_moveto(float(y) / max(1.0, float(limits[3])))
        else:
            size, hints, x, y = values
            host._psx_content.size_hint = hints
            host._psx_content.size = size
            host.scroll_x, host.scroll_y = x, y
        host._psx_scroll_logical_offset = saved.logical
        host._psx_scroll_previous_overflow = saved.previous_overflow


def prior_scroll_offset(snapshots: tuple[ScrollHostSnapshot, ...], host: object):
    """Read offset from the pre-transaction viewport, before resize resets it."""
    from .scroll_offsets import ScrollOffset

    for saved in snapshots:
        if saved.host is not host:
            continue
        if saved.backend == "qt":
            return ScrollOffset(float(saved.values[4]), float(saved.values[5]))
        if saved.backend == "tk":
            return ScrollOffset(max(0.0, float(saved.values[3])),
                                max(0.0, float(saved.values[4])))
        old_x, old_y = saved.previous_overflow or (
            max(0.0, saved.values[0][0] - host.width),
            max(0.0, saved.values[0][1] - host.height),
        )
        return ScrollOffset(max(0.0, float(saved.values[2]) * old_x),
                            max(0.0, (1.0 - float(saved.values[3])) * old_y))
    raise KeyError("Scroll host not present in transaction snapshot")
