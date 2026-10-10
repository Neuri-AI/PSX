"""Built-in Divider adapter for the Qt renderer.

Estructura interna (orientación horizontal):

    Sin hijo:  [ línea──────────────── ]
    Con hijo:  [ línea─── ]  [ hijo ]  [ ───línea ]

El layout es QHBoxLayout (horizontal) o QVBoxLayout (vertical). El hijo se
inserta siempre entre las dos líneas, en el índice 1.

La metadata de las líneas vive en el propio widget raíz del Divider, no en
el ``QtHandle`` (que usa ``slots=True`` y no acepta atributos dinámicos).
"""

from __future__ import annotations

from psx.core.contracts import DIVIDER_DEFAULTS, validate_divider_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.divider import (
    divider_props,
    needs_custom_paint,
    updated_divider_props,
)


class QtDividerAdapter:
    def __init__(self, *, frame_class, layout_h, layout_v):
        self._frame_class = frame_class
        self._layout_h = layout_h
        self._layout_v = layout_v

    # -- lifecycle --------------------------------------------------------

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        props = divider_props({**DIVIDER_DEFAULTS, **node.props})
        validate_divider_props(props)

        widget = self._frame_class()
        layout = self._layout_h(widget) if props["orientation"] == "horizontal" \
            else self._layout_v(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        line_before = self._make_line(renderer, widget, props)
        layout.addWidget(line_before)

        if node.children:
            line_after = self._make_line(renderer, widget, props)
            layout.addWidget(line_after)
            widget._psx_line_after = line_after
        else:
            widget._psx_line_after = None

        widget._psx_line_before = line_before
        handle = QtHandle("Divider", widget, layout=layout, props=props)
        self._apply_stretch(widget)
        return handle

    def update(self, renderer, handle, changed, removed):
        props = updated_divider_props(handle.props, changed, removed)
        handle.props = props
        binding = renderer._binding_package
        widget = handle.widget
        self._apply_line(widget._psx_line_before, props, binding)
        if widget._psx_line_after is not None:
            self._apply_line(widget._psx_line_after, props, binding)
        self._apply_stretch(widget)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Divider does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        widget = parent.widget
        target = 1 if widget._psx_line_after is not None else 0
        parent.layout.insertWidget(target, child.widget)
        self._apply_stretch(widget)
        return True

    def move(self, renderer, parent, child, index):
        widget = parent.widget
        parent.layout.removeWidget(child.widget)
        target = 1 if widget._psx_line_after is not None else 0
        parent.layout.insertWidget(target, child.widget)
        self._apply_stretch(widget)
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        parent.layout.removeWidget(child.widget)
        _release(child)
        self._apply_stretch(parent.widget)
        return True

    # -- helpers ----------------------------------------------------------

    def _make_line(self, renderer, parent_widget, props):
        line = self._frame_class(parent_widget)
        self._apply_line(line, props, renderer._binding_package)
        return line

    def _apply_stretch(self, widget):
        layout = widget.layout()
        count = layout.count()
        if widget._psx_line_after is None:
            for i in range(count):
                layout.setStretch(i, 1)
            return
        for i in range(count):
            item = layout.itemAt(i)
            w = item.widget()
            is_line = w is widget._psx_line_before or w is widget._psx_line_after
            layout.setStretch(i, 1 if is_line else 0)

    @staticmethod
    def _apply_line(widget, props, binding):
        import importlib
        widgets = importlib.import_module(f"{binding}.QtWidgets")
        frame = widgets.QFrame
        shape = getattr(frame, "Shape", frame)
        shadow = getattr(frame, "Shadow", frame)

        p = divider_props(props)
        is_h = p["orientation"] == "horizontal"

        if needs_custom_paint(p):
            widget.setFrameShape(shape.NoFrame)
            widget.setFrameShadow(shadow.Plain)
            widget.setLineWidth(0)
            bg = p["color"] or "palette(mid)"
            widget.setStyleSheet(f"background-color: {bg};")
            if is_h:
                widget.setFixedHeight(p["thickness"])
                widget.setMinimumWidth(0)
                widget.setMaximumWidth(16777215)
            else:
                widget.setFixedWidth(p["thickness"])
                widget.setMinimumHeight(0)
                widget.setMaximumHeight(16777215)
            return

        widget.setStyleSheet("")
        if is_h:
            widget.setFixedHeight(16777215)
            widget.setMinimumHeight(0)
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(16777215)
        else:
            widget.setFixedWidth(16777215)
            widget.setMinimumWidth(0)
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(16777215)
        widget.setFrameShape(shape.HLine if is_h else shape.VLine)
        widget.setFrameShadow(shadow.Plain)
        widget.setLineWidth(1)


def make_qt_divider_adapter(renderer):
    """Construye el adapter usando QFrame, no renderer._widget (que es QWidget)."""
    import importlib
    widgets = importlib.import_module(f"{renderer._binding_package}.QtWidgets")
    return QtDividerAdapter(
        frame_class=widgets.QFrame,
        layout_h=renderer._hbox,
        layout_v=renderer._vbox,
    )