"""Built-in Row adapter for the Qt renderer."""

from psx.core.contracts import ROW_DEFAULTS, validate_row_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.row import child_align, child_expand, normalize_padding, updated_row_props
from qyro_cli import container


class QtRowAdapter:
    def __init__(self, *, widget_class, layout_class, align_top, align_vcenter, align_bottom, align_none):
        self._widget_class, self._layout_class = widget_class, layout_class
        self._alignments = {"start": align_top, "center": align_vcenter,
                            "end": align_bottom, "stretch": align_none}

    def create(self, renderer, node, parent):
        widget = self._widget_class()
        layout = self._layout_class(widget)
        props = {**ROW_DEFAULTS, **node.props}
        validate_row_props(props)
        self._apply_container(widget, layout, props)
        from psx.renderers.qt.pyqt import QtHandle
        return QtHandle("Row", widget, layout=layout, props=props)

    def update(self, renderer, handle, changed, removed):
        props = updated_row_props(handle.props, changed, removed)
        self._apply_container(handle.widget, handle.layout, props)
        handle.props = props
        self._reapply_children(handle)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Row does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()

    def insert(self, renderer, parent, child, index):
        parent.layout.insertWidget(index, child.widget)
        self._reapply_children(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.layout.removeWidget(child.widget)
        parent.layout.insertWidget(index, child.widget)
        self._reapply_children(parent)
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        parent.layout.removeWidget(child.widget)
        _release(child)
        self._reapply_children(parent)
        return True

    @staticmethod
    def _apply_container(widget, layout, props):
        left, top, right, bottom = normalize_padding(props["padding"])
        layout.setContentsMargins(left, top, right, bottom)
        layout.setSpacing(int(props["spacing"]))
        widget.setEnabled(bool(props["enabled"]))

    def _reapply_children(self, container):
        for index in range(container.layout.count()):
            item = container.layout.itemAt(index)
            widget = item.widget()
            if widget is None:
                continue
            is_spacer = getattr(widget, "_psx_is_spacer", False)
            stretch = 1 if (is_spacer or child_expand(container.props, index)) else 0
            container.layout.setStretch(index, stretch)
            container.layout.setAlignment(widget, self._alignments[child_align(container.props, index)])


def make_qt_row_adapter(renderer):
    import importlib
    core = importlib.import_module(f"{renderer._binding_package}.QtCore")
    flags = getattr(core.Qt, "AlignmentFlag", core.Qt)
    return QtRowAdapter(widget_class=renderer._widget, layout_class=renderer._hbox,
                        align_top=flags.AlignTop, align_vcenter=flags.AlignVCenter,
                        align_bottom=flags.AlignBottom, align_none=flags(0))
