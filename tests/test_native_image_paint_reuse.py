"""Native Qt/Tk Image redraws are avoided only with identical accepted pixels.

This is a conservative occlusion-safe paint cache: already painted pixels
remain available on native expose/scroll without hiding interactive widgets.
"""
from __future__ import annotations

import os
import sys
import pytest


@pytest.mark.skipif(sys.platform == "linux" and not os.environ.get("DISPLAY")
                    and os.environ.get("QT_QPA_PLATFORM") != "offscreen",
                    reason="Qt native Image requires Qt display/offscreen platform")
def test_qt_composited_image_keeps_pixmap_on_same_native_bounds():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtGui import QPixmap, QColor
    from psx.renderers.qt.image import QtImageAdapter

    app = QApplication.instance() or QApplication(["cinnamon-image-reuse"])
    widget = QLabel()
    source = QPixmap(64, 32)
    source.fill(QColor("#39ecc1"))
    widget._psx_pixmap_cache = source
    widget._psx_props = {"fit": "contain", "alt": "logo"}
    widget._psx_sfle_paint_cache = None
    try:
        QtImageAdapter.paint_sfle(widget, 120, 60, "PySide6")
        first = widget.pixmap().cacheKey()
        assert first
        QtImageAdapter.paint_sfle(widget, 120, 60, "PySide6")
        assert widget.pixmap().cacheKey() == first
        QtImageAdapter.paint_sfle(widget, 121, 60, "PySide6")
        resized = widget.pixmap().cacheKey()
        assert resized != first
        widget._psx_props = {"fit": "cover", "alt": "logo"}
        QtImageAdapter.paint_sfle(widget, 121, 60, "PySide6")
        assert widget.pixmap().cacheKey() != resized
        accepted = widget.pixmap().cacheKey()
        widget.clear()  # Real external native invalidation
        QtImageAdapter.paint_sfle(widget, 121, 60, "PySide6")
        assert widget.pixmap().cacheKey() != accepted
    finally:
        widget.deleteLater()


def test_tk_composited_image_skips_pillow_and_tcl_photo_on_cache_hits(monkeypatch):
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image
    from psx.renderers.tkinter.image import TkImageAdapter

    root = tk.Tk()
    root.withdraw()
    widget = ttk.Label(root)
    widget._psx_image_cache = Image.new("RGBA", (80, 40), (57, 236, 193, 255))
    widget._psx_props = {"fit": "contain"}
    widget._psx_photo = None
    widget._psx_sfle_paint_cache = None
    from psx.renderers.tkinter import image as image_module
    original = image_module.ImageTk.PhotoImage
    calls = []

    def count_photo(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(image_module.ImageTk, "PhotoImage", count_photo)
    try:
        TkImageAdapter.paint_sfle(widget, 120, 60)
        first = widget._psx_photo
        assert len(calls) == 1
        TkImageAdapter.paint_sfle(widget, 120, 60)
        assert len(calls) == 1
        assert widget._psx_photo is first
        TkImageAdapter.paint_sfle(widget, 121, 60)
        assert len(calls) == 2
        widget._psx_props = {"fit": "cover"}
        TkImageAdapter.paint_sfle(widget, 121, 60)
        assert len(calls) == 3
        widget.configure(image="")
        TkImageAdapter.paint_sfle(widget, 121, 60)
        assert len(calls) == 4
    finally:
        widget.destroy()
        root.destroy()
