"""Built-in Column adapter for the Qt renderer."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from psx.core.contracts import (
    COLUMN_DEFAULTS,
    COLUMN_PROPS,
    validate_column_props,
)
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.column import (
    child_align,
    child_expand,
    normalize_padding,
    updated_column_props,
)


class QtColumnAdapter:
    def __init__(
        self,
        *,
        widget_class: type,
        layout_class: type,
        align_left: object,
        align_hcenter: object,
        align_right: object,
        align_none: object,
    ) -> None:
        self._widget_class = widget_class
        self._layout_class = layout_class
        self._alignments = {
            "start": align_left,
            "center": align_hcenter,
            "end": align_right,
            "stretch": align_none,
        }

    # -- lifecycle --------------------------------------------------------

    def create(self, renderer, node, parent):
        widget = self._widget_class()
        layout = self._layout_class(widget)
        props = {**COLUMN_DEFAULTS, **node.props}
        validate_column_props(props)
        self._apply_container(widget, layout, props)
        from psx.renderers.qt.pyqt import QtHandle  # local import to avoid cycles
        return QtHandle("Column", widget, layout=layout, props=props)

    def update(self, renderer, handle, changed, removed):
        target = handle
        props = updated_column_props(target.props, changed, removed)
        self._apply_container(target.widget, target.layout, props)
        target.props = props
        self._reapply_children(target)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Column does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()

    # -- child-lifecycle hooks -------------------------------------------

    def insert(self, renderer, parent, child, index):
        container = parent
        container.layout.insertWidget(index, child.widget)
        self._reapply_children(container)
        return True

    def move(self, renderer, parent, child, index):
        container = parent
        container.layout.removeWidget(child.widget)
        container.layout.insertWidget(index, child.widget)
        self._reapply_children(container)
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release  # local import to avoid cycles
        container = parent
        container.layout.removeWidget(child.widget)
        _release(child)
        self._reapply_children(container)
        return True

    # -- helpers ----------------------------------------------------------

    def _apply_container(self, widget, layout, props):
        l, t, r, b = normalize_padding(props["padding"])
        layout.setContentsMargins(l, t, r, b)
        layout.setSpacing(int(props["spacing"]))
        widget.setEnabled(bool(props["enabled"]))

    def _reapply_children(self, container):
        layout = container.layout
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is None:
                continue
            stretch = 1 if child_expand(container.props, index) else 0
            layout.setStretch(index, stretch)
            align_name = child_align(container.props, index)
            layout.setAlignment(widget, self._alignments[align_name])


def make_qt_column_adapter(renderer) -> QtColumnAdapter:
    import importlib
    # ``_binding`` is normalized for internal comparisons (``pyside6``),
    # while Python module imports require the package's original casing.
    core = importlib.import_module(f"{renderer._binding_package}.QtCore")
    qt = core.Qt
    flags = getattr(qt, "AlignmentFlag", qt)
    return QtColumnAdapter(
        widget_class=renderer._widget,
        layout_class=renderer._vbox,
        align_left=flags.AlignLeft,
        align_hcenter=flags.AlignHCenter,
        align_right=flags.AlignRight,
        align_none=flags(0),
    )
