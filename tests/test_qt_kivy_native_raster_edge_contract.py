"""Prevent false Qt/Kivy paint certification with wrong straight border widths."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tests.certification.qt_kivy_css_native_raster import CANVAS, CARD, compare


def _surface(background, fill, border, radius, width):
    canvas = Image.new("RGB", CANVAS, background)
    paint = ImageDraw.Draw(canvas)
    x, y, w, h = CARD
    top = CANVAS[1] - y - h
    paint.rounded_rectangle(
        (x, top, x + w - 1, top + h - 1),
        radius=radius, fill=fill, outline=border, width=width,
    )
    return canvas


def test_identical_native_surfaces_have_zero_straight_edge_difference(tmp_path):
    item = ("baseline", "#e9edf3", "#ffffff", "#364152", 8, 2)
    name, background, fill, border, radius, width = item
    frame = _surface(background, fill, border, radius, width)
    for renderer in ("qt", "kivy"):
        frame.save(tmp_path / f"{name}-{renderer}.png")
    compare(tmp_path, *item)
    import json
    receipt = json.loads((tmp_path / f"{name}.json").read_text())
    assert receipt["straight_edge_class_disagreement"] == 0


def test_thick_kivy_outline_cannot_pass_corner_only_certification(tmp_path):
    item = ("wrong-border", "#e9edf3", "#ffffff", "#364152", 8, 2)
    name, background, fill, border, radius, width = item
    qt = _surface(background, fill, border, radius, width)
    kivy = _surface(background, fill, border, radius, width + 3)
    qt.save(tmp_path / f"{name}-qt.png")
    kivy.save(tmp_path / f"{name}-kivy.png")
    with pytest.raises(AssertionError, match="straight_edge_class_disagreement"):
        compare(tmp_path, *item)
