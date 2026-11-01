"""Pure delegation of source-owned inline fragments to renderer paint ports.

No QPainter, tkinter.Canvas or Kivy canvas/texture operations belong here.
The three renderer-owned ports implement all native mutation and teardown.
"""
from __future__ import annotations
from collections.abc import Mapping

from psx.layout.inline.semantic_inline_text import InlineTextFragment
from psx.renderers.qt.inline_paint import paint as _qt_paint, clear as _qt_clear
from psx.renderers.tkinter.inline_paint import paint as _tk_paint, clear as _tk_clear
from psx.renderers.kivy.inline_paint import paint as _kivy_paint, clear as _kivy_clear

def project_native_inline_paint(
    renderer,
    backend: str,
    widgets: Mapping[str, object],
    fragment_plan: Mapping[str, tuple[InlineTextFragment, ...]],
    boxes,
) -> None:
    """Repaint only original source Text hosts after Cinnamon's native commit.

    Called on each backend's owning UI thread, never from a worker.
    """
    clear = {"qt": _qt_clear, "tk": _tk_clear, "kivy": _kivy_clear}[backend]
    previous = getattr(renderer, "_sfle_semantic_inline_widgets", {})
    next_widgets = {node_id: widgets[node_id] for node_id in fragment_plan}
    for node_id, widget in previous.items():
        if next_widgets.get(node_id) is not widget:
            try:
                clear(widget)
            except (RuntimeError, AttributeError, ValueError):
                # A native owner may already have destroyed the widget.
                pass
    for node_id, fragments in fragment_plan.items():
        widget = widgets[node_id]
        box = boxes[node_id].content
        if backend == "qt":
            _qt_paint(widget, fragments, box, renderer._binding_package)
        elif backend == "tk":
            _tk_paint(widget, fragments, box)
        else:
            _kivy_paint(widget, fragments, box)
    renderer._sfle_semantic_inline_widgets = next_widgets


def release_native_inline_paint(renderer, backend: str) -> None:
    """Remove painter hooks on remount/unmount and release native references."""
    previous = getattr(renderer, "_sfle_semantic_inline_widgets", {})
    clear = {"qt": _qt_clear, "tk": _tk_clear, "kivy": _kivy_clear}[backend]
    renderer._sfle_semantic_inline_widgets = {}
    for widget in previous.values():
        try:
            clear(widget)
        except Exception:
            # A disposed QObject, Tcl widget or Kivy canvas may no longer
            # admit native calls; never retain or resurrect that owner.
            continue
