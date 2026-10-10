"""Portable Qt Badge painted with native QPainter for stable hot updates."""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import badge_props, badge_style, updated_badge_props


def _badge_widget_class(binding: str):
    core = importlib.import_module(f"{binding}.QtCore")
    gui = importlib.import_module(f"{binding}.QtGui")
    widgets = importlib.import_module(f"{binding}.QtWidgets")
    qt = core.Qt
    alignment = getattr(getattr(qt, "AlignmentFlag", qt), "AlignCenter")
    no_pen = getattr(getattr(qt, "PenStyle", qt), "NoPen")
    antialiasing = getattr(
        getattr(gui.QPainter, "RenderHint", gui.QPainter), "Antialiasing"
    )

    class PaintedBadge(widgets.QWidget):
        """Measure each state afresh and paint shape and centered text together."""

        def __init__(self):
            super().__init__()
            self._psx_props = None
            self._psx_style = None

        def set_props(self, props):
            foreground, background, stroke, font_size, px, py = badge_style(props)
            font = self.font()
            font.setPointSize(font_size)
            self.setFont(font)

            metrics = gui.QFontMetrics(font)
            width = max(1, metrics.horizontalAdvance(props["label"]) + 2 * px + 4)
            height = max(1, metrics.height() + 2 * py + 4)

            self._psx_props = props
            self._psx_style = (foreground, background, stroke)
            self.setEnabled(props["enabled"])
            self.setAccessibleName(props["label"])

            # Measure from the new font/text on every update, not from a
            # QLabel sizeHint constrained by an earlier setFixedSize().
            self.setFixedSize(width, height)
            self.updateGeometry()
            self.update()

        def paintEvent(self, event):
            if self._psx_props is None:
                return
            props = self._psx_props
            foreground, background, stroke = self._psx_style
            painter = gui.QPainter(self)
            painter.setRenderHint(antialiasing, True)

            inset = 0.5
            rect = core.QRectF(
                inset, inset, max(0.0, self.width() - 2 * inset),
                max(0.0, self.height() - 2 * inset),
            )
            radius = rect.height() / 2 if props["shape"] == "pill" else 5.0
            radius = min(radius, rect.width() / 2)

            if props["appearance"] == "outline":
                painter.setBrush(no_pen)
                painter.setPen(gui.QPen(gui.QColor(stroke), 1))
            else:
                painter.setPen(no_pen)
                painter.setBrush(gui.QColor(background))
            painter.drawRoundedRect(rect, radius, radius)

            painter.setPen(gui.QColor(foreground))
            painter.setFont(self.font())
            painter.drawText(core.QRectF(self.rect()), alignment, props["label"])
            painter.end()

    return PaintedBadge


class QtBadgeAdapter:
    def __init__(self):
        self._classes = {}

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = badge_props(node.props)
        binding = renderer._binding_package
        widget_type = self._classes.get(binding)
        if widget_type is None:
            widget_type = self._classes[binding] = _badge_widget_class(binding)
        widget = widget_type()
        widget.set_props(props)
        return QtHandle("Badge", widget, props=props)

    def update(self, renderer, handle, changed, removed):
        props = updated_badge_props(handle.props, changed, removed)
        handle.widget.set_props(props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Badge does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        widget.setParent(None)
        widget.deleteLater()
