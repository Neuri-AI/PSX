"""Internal passthrough container adapter for the Qt renderer.

Keeps the top-level host widget stable when the wrapped subtree changes its
own root type. Not part of the public portable API.
"""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError


class QtBoxAdapter:
    def __init__(self, *, widget_class, layout_class, binding_package):
        self._widget_class = widget_class
        self._layout_class = layout_class
        self._binding_package = binding_package

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        widget = self._widget_class()
        layout = self._layout_class(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        return QtHandle("Box", widget, layout=layout, props=dict(node.props))

    def update(self, renderer, handle, changed, removed):
        if changed or removed:
            raise RendererCapabilityError(
                f"Box is an internal container and does not accept props: "
                f"{', '.join(sorted(set(changed) | removed))}"
            )

    def insert(self, renderer, parent, child, index):
        parent.layout.insertWidget(index, child.widget)
        # Fill the whole box; the layout's default centers a single child
        # with a small sizeHint instead of stretching it.
        parent.layout.setStretch(index, 1)
        parent.layout.setAlignment(child.widget, self._align_none())
        return True

    def move(self, renderer, parent, child, index):
        parent.layout.removeWidget(child.widget)
        parent.layout.insertWidget(index, child.widget)
        parent.layout.setStretch(index, 1)
        parent.layout.setAlignment(child.widget, self._align_none())
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        parent.layout.removeWidget(child.widget)
        _release(child)
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Box does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()

    def _align_none(self):
        core = importlib.import_module(f"{self._binding_package}.QtCore")
        flags = getattr(core.Qt, "AlignmentFlag", core.Qt)
        return flags(0)


def make_qt_box_adapter(renderer):
    return QtBoxAdapter(
        widget_class=renderer._widget,
        layout_class=renderer._hbox,
        binding_package=renderer._binding_package,
    )