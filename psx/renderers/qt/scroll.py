"""Qt Scroll: QScrollArea viewport, managed layout and overlay indicators."""

from __future__ import annotations

import importlib

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.scroll import (
    scroll_axes, scroll_padding, scroll_props, updated_scroll_props,
)


def _scroll_area_class(binding: str):
    core = importlib.import_module(f"{binding}.QtCore")
    widgets = importlib.import_module(f"{binding}.QtWidgets")
    qt = core.Qt
    policy = getattr(qt, "ScrollBarPolicy", qt)
    orientation = getattr(qt, "Orientation", qt)
    align = getattr(qt, "AlignmentFlag", qt)
    event_type = getattr(core.QEvent, "Type", core.QEvent)
    no_focus = getattr(getattr(qt, "FocusPolicy", qt), "NoFocus")

    class OverlayArea(widgets.QScrollArea):
        def __init__(self):
            super().__init__()
            self.setWidgetResizable(False)
            self.setFrameShape(widgets.QFrame.Shape.NoFrame if hasattr(widgets.QFrame, "Shape") else widgets.QFrame.NoFrame)
            self.setHorizontalScrollBarPolicy(policy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(policy.ScrollBarAlwaysOff)
            self._psx_props = None
            self._indicators = {}
            self._fade = core.QTimer(self)
            self._fade.setSingleShot(True)
            self._fade.timeout.connect(self._refresh_indicators)
            for axis, orient in (("x", orientation.Horizontal), ("y", orientation.Vertical)):
                indicator = widgets.QScrollBar(orient, self.viewport())
                indicator.setFocusPolicy(no_focus)
                indicator.setStyleSheet(
                    "QScrollBar { background: transparent; border: none; }"
                    "QScrollBar:vertical { width: 7px; }"
                    "QScrollBar:horizontal { height: 7px; }"
                    "QScrollBar::handle { background: #88888899; border-radius: 3px; min-height: 18px; min-width: 18px; }"
                    "QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }"
                    "QScrollBar::add-page, QScrollBar::sub-page { background: none; }"
                )
                native = self.horizontalScrollBar() if axis == "x" else self.verticalScrollBar()
                indicator.valueChanged.connect(native.setValue)
                native.valueChanged.connect(indicator.setValue)
                native.rangeChanged.connect(
                    lambda low, high, target=indicator: target.setRange(low, high)
                )
                self._indicators[axis] = indicator
            self.viewport().installEventFilter(self)

        def eventFilter(self, source, event):
            if source is self.viewport() and event.type() == event_type.Resize:
                self._refresh_indicators()
            return super().eventFilter(source, event)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._refresh_indicators()

        def wheelEvent(self, event):
            props = self._psx_props
            if props is None or not props["enabled"]:
                event.ignore()
                return
            dx, dy = scroll_axes(props["direction"])
            delta = event.angleDelta()
            horizontal = abs(delta.x()) > abs(delta.y())
            allowed = dx if horizontal else dy
            bar = self.horizontalScrollBar() if horizontal else self.verticalScrollBar()
            amount = delta.x() if horizontal else delta.y()
            can_move = (
                (amount > 0 and bar.value() > bar.minimum())
                or (amount < 0 and bar.value() < bar.maximum())
            )
            if allowed and can_move:
                super().wheelEvent(event)
                self._fade.start(750)
                self._refresh_indicators(active=True)
                return
            # Native Qt wheel dispatch will offer an ignored event to an
            # enclosing scroll area. Avoid consuming at the boundary.
            event.ignore()

        def configure(self, props):
            self._psx_props = props
            self.setEnabled(props["enabled"])
            self.setFixedWidth(round(props["width"])) if props["width"] is not None else self.setMinimumWidth(0)
            if props["width"] is None:
                self.setMaximumWidth(16777215)
            self.setFixedHeight(round(props["height"])) if props["height"] is not None else self.setMinimumHeight(0)
            if props["height"] is None:
                self.setMaximumHeight(16777215)
            self._refresh_indicators()

        def _refresh_indicators(self, *, active=False):
            props = self._psx_props
            if props is None:
                return
            dx, dy = scroll_axes(props["direction"])
            viewport = self.viewport()
            for axis, indicator in self._indicators.items():
                native = self.horizontalScrollBar() if axis == "x" else self.verticalScrollBar()
                maximum = native.maximum()
                permitted = dx if axis == "x" else dy
                indicator.setPageStep(native.pageStep())
                indicator.setRange(native.minimum(), maximum)
                indicator.setValue(native.value())
                visible = (
                    props["scrollbar"] == "always"
                    or (props["scrollbar"] == "auto" and (active or self._fade.isActive()))
                )
                indicator.setVisible(visible and permitted and maximum > 0)
                if axis == "x":
                    indicator.setGeometry(2, max(0, viewport.height() - 9), max(0, viewport.width() - 11), 7)
                else:
                    indicator.setGeometry(max(0, viewport.width() - 9), 2, 7, max(0, viewport.height() - 11))
                indicator.raise_()

    return OverlayArea


class QtScrollAdapter:
    def __init__(self):
        self._classes = {}

    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle

        props = scroll_props(node.props)
        binding = renderer._binding_package
        cls = self._classes.get(binding)
        if cls is None:
            cls = self._classes[binding] = _scroll_area_class(binding)
        area = cls()
        content = renderer._widgets.QWidget()
        layout_type = renderer._hbox if props["content_direction"] == "horizontal" else renderer._vbox
        layout = layout_type(content)
        area.setWidget(content)
        area._psx_binding = binding
        area._psx_content = content
        area._psx_layout = layout
        self._apply(area, props)
        return QtHandle("Scroll", area, layout=layout, props=props)

    @staticmethod
    def _apply(area, props):
        layout = area._psx_layout
        direction_type = getattr(importlib.import_module(
            f"{area._psx_binding}.QtWidgets"
        ).QBoxLayout, "Direction", importlib.import_module(
            f"{area._psx_binding}.QtWidgets"
        ).QBoxLayout)
        layout.setDirection(
            direction_type.LeftToRight if props["content_direction"] == "horizontal"
            else direction_type.TopToBottom
        )
        left, top, right, bottom = scroll_padding(props)
        layout.setContentsMargins(left, top, right, bottom)
        layout.setSpacing(props["spacing"])
        area.configure(props)
        area._psx_content.adjustSize()
        area._refresh_indicators()

    def update(self, renderer, handle, changed, removed):
        props = updated_scroll_props(handle.props, changed, removed)
        area = handle.widget
        self._apply(area, props)
        handle.props = props

    def insert(self, renderer, parent, child, index):
        parent.layout.insertWidget(index, child.widget)
        parent.widget._psx_content.adjustSize()
        return True

    def move(self, renderer, parent, child, index):
        parent.layout.removeWidget(child.widget)
        parent.layout.insertWidget(index, child.widget)
        parent.widget._psx_content.adjustSize()
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        parent.layout.removeWidget(child.widget)
        _release(child)
        parent.widget._psx_content.adjustSize()
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Scroll does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        area = handle.widget
        area._fade.stop()
        area.setParent(None)
        area.deleteLater()
