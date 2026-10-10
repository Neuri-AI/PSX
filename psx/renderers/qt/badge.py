"""Portable Qt Badge based on a self-sizing noninteractive QLabel."""

from __future__ import annotations

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.badge import badge_props, badge_style, updated_badge_props


class QtBadgeAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = badge_props(node.props)
        widget = renderer._widgets.QLabel()
        self._apply(widget, props)
        return QtHandle("Badge", widget, props=props)

    @staticmethod
    def _apply(widget, props):
        foreground, background, stroke, font_size, px, py = badge_style(props)
        font = widget.font()
        font.setPointSize(font_size)
        widget.setFont(font)
        widget.setText(props["label"])
        height = widget.fontMetrics().height() + py * 2 + 2
        radius = height // 2 if props["shape"] == "pill" else 5
        background_value = background if background else "transparent"
        border = "none" if props["appearance"] == "filled" else f"1px solid {stroke}"
        widget.setStyleSheet(
            "QLabel {"
            f"color: {foreground}; background-color: {background_value}; "
            f"border: {border}; border-radius: {radius}px;"
            f"padding: {py}px {px}px;"
            "}"
        )
        widget.setEnabled(props["enabled"])
        widget.setAccessibleName(props["label"])
        widget.adjustSize()
        widget.setFixedSize(widget.sizeHint())

    def update(self, renderer, handle, changed, removed):
        props = updated_badge_props(handle.props, changed, removed)
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Badge does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        widget.setParent(None)
        widget.deleteLater()
