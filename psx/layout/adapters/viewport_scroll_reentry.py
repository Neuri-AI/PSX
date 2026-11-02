"""Coalesced, owner-thread scroll reentry for deferred Grid geometry.

Scroll hosts remain native and own their offsets. When a Grid subtree has
uncommitted offscreen geometry, one native scroll notification schedules a
normal Cinnamon transaction at the new scroll offset. This must NEVER run
inside a native geometry commit or create a second geometry authority.
"""
from __future__ import annotations


def request_scroll_reentry(renderer, host, schedule) -> None:
    if (not getattr(host, "_psx_viewport_has_deferred", False)
            or not getattr(host, "_psx_sfle_scroll", False)
            or getattr(renderer, "_sfle_constraints", None) is None
            or getattr(renderer, "_sfle_mounted_root", None) is None
            or getattr(host, "_psx_viewport_reentry_pending", False)):
        return
    if getattr(renderer, "_sfle_in_commit", False):
        # Native Scroll can clamp its offset while Cinnamon is committing
        # geometry. The event must be replayed only after full acceptance.
        queued = getattr(renderer, "_psx_scroll_after_commit", None)
        if queued is None:
            queued = {}
            renderer._psx_scroll_after_commit = queued
        queued[id(host)] = host
        return
    host._psx_viewport_reentry_pending = True

    def perform():
        host._psx_viewport_reentry_pending = False
        root = getattr(renderer, "_sfle_mounted_root", None)
        if (root is None or getattr(renderer, "_sfle_in_commit", False)
                or not getattr(host, "_psx_viewport_has_deferred", False)):
            return
        # Rust still owns all widths, wrapping and Grid row allocations.
        # The native workset updates only groups whose visibility changed.
        renderer.commit_layout(root)

    try:
        schedule(perform)
    except BaseException:
        host._psx_viewport_reentry_pending = False
        raise


def flush_scroll_reentry_after_commit(renderer, schedule) -> None:
    """Replay native scroll changes that occurred inside the commit."""
    queued = getattr(renderer, "_psx_scroll_after_commit", None)
    renderer._psx_scroll_after_commit = {}
    if not queued:
        return
    for host in queued.values():
        if getattr(host, "_psx_viewport_has_deferred", False):
            request_scroll_reentry(renderer, host, schedule)
