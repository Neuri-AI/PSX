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
            self._psx_sfle_scroll = False
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
            # Desktop trackpads already deliver phased QWheelEvent streams.
            # Grabbing a QScroller touch gesture on the same viewport gives
            # two different handlers ownership of one gesture and may leave
            # the scroller in a kinetic state after wheel input has stopped.
            # The Scroll viewport owns wheel deltas directly instead.
            self._psx_subpixel_remainder = {"x": 0.0, "y": 0.0}

        def eventFilter(self, source, event):
            if source is self.viewport() and event.type() == event_type.Resize:
                self._refresh_indicators()
            return super().eventFilter(source, event)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._refresh_indicators()

        def _psx_scroll_delta(self, dx, dy):
            """Consume X/Y movement once, handing unconsumed travel to parent."""
            from psx.renderers.components.scroll import consume_scroll
            props = self._psx_props
            remaining_x, remaining_y = float(dx), float(dy)
            if props is not None and props["enabled"]:
                allow_x, allow_y = scroll_axes(props["direction"])
                for axis, delta, enabled in (
                    ("x", remaining_x, allow_x),
                    ("y", remaining_y, allow_y),
                ):
                    if not enabled or not delta:
                        continue
                    bar = (self.horizontalScrollBar() if axis == "x"
                           else self.verticalScrollBar())
                    maximum = float(bar.maximum())
                    if maximum <= 0:
                        self._psx_subpixel_remainder[axis] = 0.0
                        continue
                    pending = delta + self._psx_subpixel_remainder[axis]
                    next_value, residual = consume_scroll(
                        float(bar.value()), maximum, pending,
                    )
                    position = round(next_value)
                    bar.setValue(position)
                    # Keep fractional trackpad travel between events. Rounding
                    # each delta independently makes slow or resumed scrolling
                    # appear frozen on high-resolution macOS trackpads.
                    self._psx_subpixel_remainder[axis] = (
                        next_value - float(position) if not residual else 0.0
                    )
                    # Only the current gesture's travel may chain to an
                    # ancestor; fractional carry belongs to this viewport.
                    if axis == "x":
                        remaining_x = residual
                    else:
                        remaining_y = residual
            consumed = (dx - remaining_x, dy - remaining_y)
            if consumed != (0, 0):
                self._fade.start(750)
                self._refresh_indicators(active=True)
            if remaining_x or remaining_y:
                ancestor = self.parentWidget()
                while ancestor is not None:
                    if hasattr(ancestor, "_psx_scroll_delta"):
                        tail = ancestor._psx_scroll_delta(remaining_x, remaining_y)
                        remaining_x, remaining_y = tail
                        break
                    ancestor = ancestor.parentWidget()
            return remaining_x, remaining_y

        def wheelEvent(self, event):
            if self._psx_props is None or not self._psx_props["enabled"]:
                event.ignore()
                return
            pixel = event.pixelDelta()
            angle = event.angleDelta()
            # Qt positive wheel delta points up/left, opposite to logical
            # increasing top-left SFLE offsets.
            dx = -float(pixel.x()) if pixel.x() else -float(angle.x()) * 48 / 120
            dy = -float(pixel.y()) if pixel.y() else -float(angle.y()) * 48 / 120
            shift = getattr(getattr(qt, "KeyboardModifier", qt), "ShiftModifier")
            if event.modifiers() & shift and not dx:
                dx, dy = dy, 0.0
            if not (dx or dy):
                event.ignore()
                return
            residual = self._psx_scroll_delta(dx, dy)
            if residual == (dx, dy):
                event.ignore()
            else:
                event.accept()

        def keyPressEvent(self, event):
            from psx.sfle.scroll_events import scroll_key_delta
            from psx.sfle.scroll_offsets import ScrollOffset
            props = self._psx_props
            if props is None or not props["enabled"]:
                event.ignore()
                return
            keys = getattr(qt, "Key", qt)
            names = {
                keys.Key_Left: "Left", keys.Key_Right: "Right",
                keys.Key_Up: "Up", keys.Key_Down: "Down",
                keys.Key_PageUp: "PageUp", keys.Key_PageDown: "PageDown",
                keys.Key_Home: "Home", keys.Key_End: "End",
            }
            name = names.get(event.key())
            if name is None:
                super().keyPressEvent(event)
                return
            horizontal = self.horizontalScrollBar()
            vertical = self.verticalScrollBar()
            dx, dy = scroll_key_delta(
                name, viewport_width=self.viewport().width(),
                viewport_height=self.viewport().height(),
                offset=ScrollOffset(horizontal.value(), vertical.value()),
                maximum_x=horizontal.maximum(), maximum_y=vertical.maximum(),
            )
            allow_x, allow_y = scroll_axes(props["direction"])
            dx = dx if allow_x else 0.0
            dy = dy if allow_y else 0.0
            before = horizontal.value(), vertical.value()
            horizontal.setValue(before[0] + round(dx))
            vertical.setValue(before[1] + round(dy))
            if before != (horizontal.value(), vertical.value()):
                event.accept()
                self._refresh_indicators(active=True)
            else:
                event.ignore()

        def configure(self, props):
            self._psx_props = props
            if not props["enabled"]:
                self._psx_subpixel_remainder = {"x": 0.0, "y": 0.0}
            self.setEnabled(props["enabled"])
            if self._psx_sfle_scroll:
                self.setMinimumWidth(0)
                self.setMaximumWidth(16777215)
            else:
                self.setFixedWidth(round(props["width"])) if props["width"] is not None else self.setMinimumWidth(0)
            if props["width"] is None:
                self.setMaximumWidth(16777215)
            if self._psx_sfle_scroll:
                self.setMinimumHeight(0)
                self.setMaximumHeight(16777215)
            else:
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
        sfle = renderer._sfle_constraints is not None
        layout = None
        if not sfle:
            layout_type = renderer._hbox if props["content_direction"] == "horizontal" else renderer._vbox
            layout = layout_type(content)
        area.setWidget(content)
        area._psx_sfle_scroll = sfle
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
        if layout is not None:
            layout.setDirection(
                direction_type.LeftToRight if props["content_direction"] == "horizontal"
                else direction_type.TopToBottom
            )
            left, top, right, bottom = scroll_padding(props)
            layout.setContentsMargins(left, top, right, bottom)
            layout.setSpacing(props["spacing"])
        area.configure(props)
        if not area._psx_sfle_scroll:
            area._psx_content.adjustSize()
        area._refresh_indicators()

    def update(self, renderer, handle, changed, removed):
        props = updated_scroll_props(handle.props, changed, removed)
        area = handle.widget
        self._apply(area, props)
        handle.props = props

    def insert(self, renderer, parent, child, index):
        if parent.widget._psx_sfle_scroll:
            if child.widget.parentWidget() is not parent.widget._psx_content:
                child.widget.setParent(parent.widget._psx_content)
            child.widget.show()
            return True
        parent.layout.insertWidget(index, child.widget)
        parent.widget._psx_content.adjustSize()
        return True

    def move(self, renderer, parent, child, index):
        if parent.widget._psx_sfle_scroll:
            return True
        parent.layout.removeWidget(child.widget)
        parent.layout.insertWidget(index, child.widget)
        parent.widget._psx_content.adjustSize()
        return True

    def remove(self, renderer, parent, child):
        from psx.renderers.qt.pyqt import _release
        if parent.widget._psx_sfle_scroll:
            _release(child)
            return True
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
