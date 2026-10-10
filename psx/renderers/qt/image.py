"""Built-in Image adapter for the Qt renderer.

Loads a local file into a QPixmap, caches it by source path, and re-scales
it into the widget's target rectangle using the shared geometry helpers.
Uses QPainter to compose the final pixmap so all four fit modes are honoured
(contain letterboxes, cover crops, fill stretches, none centers).
"""

from __future__ import annotations

import importlib

from psx.core.contracts import IMAGE_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.image import (
    compute_fit_rect,
    compute_target_size,
    image_props,
    updated_image_props,
)


class QtImageAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.qt.pyqt import QtHandle
        props = image_props({**IMAGE_DEFAULTS, **node.props})

        binding = renderer._binding_package
        widgets = importlib.import_module(f"{binding}.QtWidgets")
        core = importlib.import_module(f"{binding}.QtCore")

        widget = widgets.QLabel()
        widget.setAlignment(core.Qt.AlignCenter)
        widget.setAccessibleName(props["alt"])
        widget._psx_source = None
        widget._psx_pixmap_cache = None
        widget._psx_props = props

        self._load_and_apply(widget, props, binding)
        return QtHandle("Image", widget, props=props)

    def update(self, renderer, handle, changed, removed):
        props = updated_image_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget._psx_props = props
        self._load_and_apply(widget, props, renderer._binding_package)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Image does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        handle.widget.setParent(None)
        handle.widget.deleteLater()

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _load_and_apply(widget, props, binding):
        core = importlib.import_module(f"{binding}.QtCore")
        gui = importlib.import_module(f"{binding}.QtGui")

        source = props["source"]
        if widget._psx_source != source:
            pixmap = gui.QPixmap(source)
            widget._psx_pixmap_cache = pixmap if not pixmap.isNull() else None
            widget._psx_source = source

        pixmap = widget._psx_pixmap_cache
        if pixmap is None:
            # Could not load the image: fall back to the alt text.
            widget.setText(props["alt"])
            widget.setPixmap(gui.QPixmap())
            return

        src_w, src_h = pixmap.width(), pixmap.height()
        target_w, target_h = compute_target_size(
            src_w, src_h, props["width"], props["height"],
        )
        if target_w <= 0 or target_h <= 0:
            widget.setPixmap(pixmap)
            return

        x, y, w, h = compute_fit_rect(
            src_w, src_h, target_w, target_h, props["fit"],
        )

        scaled = pixmap.scaled(
            max(1, int(round(w))), max(1, int(round(h))),
            core.Qt.IgnoreAspectRatio,
            core.Qt.SmoothTransformation,
        )
        canvas = gui.QPixmap(int(target_w), int(target_h))
        canvas.fill(gui.QColor(0, 0, 0, 0))
        painter = gui.QPainter(canvas)
        painter.drawPixmap(int(round(x)), int(round(y)), scaled)
        painter.end()

        widget.setPixmap(canvas)
        widget.setFixedSize(int(target_w), int(target_h))
        widget.setAccessibleName(props["alt"])
        widget.setEnabled(props["enabled"])