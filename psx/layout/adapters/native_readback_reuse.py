"""Transaction-local native geometry readback reuse.

A native rectangle captured for rollback at the beginning of an owner-thread
commit is already a real toolkit read. It can serve as the post-commit
readback *only if that widget was not written and no native scroll or
external owner could have changed it*. This keeps a full per-node receipt
for parity validation without issuing two identical Tcl/Qt property reads
for every inert offscreen and onscreen sibling.

Kivy is deliberately live-read until observable asynchronous canvas
transforms can be proven independent. This is not widget virtualization.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from psx.layout.contracts.tree_identity import LayoutTreeIdentity


def readback_reusing_prior(
    backend: str,
    nodes: tuple[LayoutTreeIdentity, ...],
    handles: Mapping[str, Any],
    before: Mapping[str, Any],
    mutated_ids: frozenset[str],
    external_ids: frozenset[str],
    read_widget: Callable[[str, Any], dict[str, float]],
    *,
    deferred_ids: frozenset[str] = frozenset(),
) -> dict[str, dict[str, float]]:
    if backend not in ("qt", "tk", "kivy"):
        raise ValueError("Unknown native geometry backend")
    result = {}
    native_scroll_descendants = set()
    for node in nodes:
        identifier = node.node_id
        if identifier in deferred_ids:
            # A deferred rectangle is deliberately NOT a fresh native
            # readback receipt. Its solver box remains authoritative.
            continue
        parent_id = node.parent_id
        if parent_id is not None and (
            parent_id in native_scroll_descendants
            or getattr(getattr(handles.get(parent_id), "widget", handles.get(parent_id)),
                       "_psx_sfle_scroll", False)
        ):
            native_scroll_descendants.add(identifier)
        widget = handles[identifier]
        native_widget = getattr(widget, "widget", widget)
        previous = before.get(identifier)
        # Only *unmodified* ordinary Qt and explicit Tk place placements
        # can rely on the native snapshot already read on the UI thread.
        # External ports/Scroll owners and Kivy must always be read live.
        allow = (
            backend in ("qt", "tk")
            and parent_id is not None
            and identifier not in mutated_ids
            and identifier not in external_ids
            and identifier not in native_scroll_descendants
            and not getattr(native_widget, "_psx_sfle_scroll", False)
            and previous is not None
        )
        if allow and backend == "qt":
            if (isinstance(previous, tuple) and len(previous) == 4
                    and all(isinstance(x, (int, float)) for x in previous)):
                result[identifier] = dict(zip(
                    ("x", "y", "width", "height"),
                    (float(x) for x in previous),
                ))
                continue
        elif allow and backend == "tk":
            # Explicit pixel placements are stable when their parent's
            # geometry changes; relative placement coordinates are not.
            if isinstance(previous, Mapping) and all(
                key in previous for key in ("x", "y", "width", "height")
            ):
                try:
                    relative = any(
                        float(previous.get(key) or 0.0)
                        for key in ("relx", "rely", "relwidth", "relheight")
                    )
                    if not relative:
                        result[identifier] = {
                            axis: float(previous[axis])
                            for axis in ("x", "y", "width", "height")
                        }
                except (ValueError, TypeError, OverflowError):
                    pass
                else:
                    if not relative:
                        continue
        result[identifier] = read_widget(identifier, widget)
    return result
