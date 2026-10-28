"""Real native Qt/QSS versus Tk/Canvas rounded-card raster comparison.

The Qt image is a QWidget painted by its style engine, not a synthetic
reference circle. Tk uses the actual runtime Canvas paint function, captured
from the Xvfb framebuffer. The contacts and measurements are CI artifacts;
a passing geometric regression is NOT a pixel-perfect release certificate.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageGrab
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from psx.renderers.tkinter.rounded_surface import draw_rounded_surface


PALETTES = (
    ("light", "#f5f6f8", "#ffffff", "#dedede"),
    ("dark", "#1f2430", "#343b49", "#6b7385"),
)
RADII = (4, 8, 12, 20)
WIDTHS = (1, 2)
SIZE = (160, 80)


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(bytes.fromhex(color.removeprefix("#")))


def _distance(pixel: tuple[int, ...], color: tuple[int, int, int]) -> int:
    return sum((a - b) ** 2 for a, b in zip(pixel[:3], color))


def _category(pixel: tuple[int, ...], colors: tuple[tuple[int, int, int], ...]) -> int:
    return min(range(3), key=lambda i: _distance(pixel, colors[i]))


def _qt_card(qt: QApplication, background: str, fill: str, border: str,
             radius: int, width: int) -> Image.Image:
    host = QWidget()
    host.setObjectName("psxCornerParent")
    host.resize(200, 120)
    host.setStyleSheet(
        f"QWidget#psxCornerParent {{ background-color: {background}; }}"
    )
    card = QWidget(host)
    card.setObjectName("psxCornerCard")
    card.setGeometry(20, 20, *SIZE)
    card.setStyleSheet(
        f"QWidget#psxCornerCard {{ background-color: {fill}; "
        f"border: {width}px solid {border}; border-radius: {radius}px; }}"
    )
    host.show()
    qt.processEvents()
    # Use QSS's genuine backing paint, not an analytic Qt approximation.
    image_path = Path(os.environ["PSX_CORNER_VISUAL_OUTPUT"]) / "_qt_current.png"
    assert host.grab(QRect(20, 20, *SIZE)).save(str(image_path), "PNG")
    image = Image.open(image_path).convert("RGB").copy()
    host.close()
    qt.processEvents()
    return image


def _tk_card(root: tk.Tk, background: str, fill: str, border: str,
             radius: int, width: int) -> Image.Image:
    root.configure(background=background)
    canvas = tk.Canvas(root, borderwidth=0, highlightthickness=0, takefocus=0)
    canvas.place(x=20, y=20, width=SIZE[0], height=SIZE[1])
    draw_rounded_surface(
        canvas, width=SIZE[0], height=SIZE[1], radius=radius,
        parent_color=background, fill_color=fill,
        sides={side: (width, border)
               for side in ("top", "right", "bottom", "left")},
    )
    root.update()
    assert canvas.winfo_ismapped()
    assert (canvas.winfo_width(), canvas.winfo_height()) == SIZE
    bbox = (canvas.winfo_rootx(), canvas.winfo_rooty(),
            canvas.winfo_rootx() + SIZE[0], canvas.winfo_rooty() + SIZE[1])
    image = ImageGrab.grab(bbox=bbox).convert("RGB")
    canvas.destroy()
    root.update()
    return image


def _corner_disagreement(qt: Image.Image, tk_image: Image.Image, radius: int,
                         colors: tuple[tuple[int, int, int], ...]) -> float:
    mismatch = 0
    sampled = 0
    for xbase in (0, SIZE[0] - radius):
        for ybase in (0, SIZE[1] - radius):
            for y in range(ybase, ybase + radius):
                for x in range(xbase, xbase + radius):
                    mismatch += _category(qt.getpixel((x, y)), colors) != _category(
                        tk_image.getpixel((x, y)), colors)
                    sampled += 1
    return mismatch / sampled


@pytest.mark.parametrize("palette", PALETTES, ids=lambda palette: palette[0])
@pytest.mark.parametrize("radius", RADII, ids=lambda radius: f"radius-{radius}")
@pytest.mark.parametrize("width", WIDTHS, ids=lambda width: f"stroke-{width}")
def test_qt_reference_tk_real_raster_rounded_card(
    palette: tuple[str, str, str, str], radius: int, width: int,
):
    """16 native paints; persist Qt/Tk images, pixel differences and metrics."""
    _name, background, fill, border = palette
    out = Path(os.environ["PSX_CORNER_VISUAL_OUTPUT"])
    out.mkdir(parents=True, exist_ok=True)
    qt = QApplication.instance() or QApplication(["psx-corner-visual"])
    root = tk.Tk()
    root.geometry("210x140+100+100")
    root.deiconify()
    root.update()
    try:
        qt_image = _qt_card(qt, background, fill, border, radius, width)
        tk_image = _tk_card(root, background, fill, border, radius, width)
    finally:
        root.destroy()

    assert qt_image.size == tk_image.size == SIZE
    colors = tuple(map(_rgb, (background, fill, border)))
    # Both native painters must retain intended interior and straight edges.
    center = (SIZE[0] // 2, SIZE[1] // 2)
    top = (SIZE[0] // 2, 0)
    bottom = (SIZE[0] // 2, SIZE[1] - 1)
    for rendered in (qt_image, tk_image):
        assert _category(rendered.getpixel(center), colors) == 1
        assert _category(rendered.getpixel(top), colors) == 2
        assert _category(rendered.getpixel(bottom), colors) == 2
        assert _category(rendered.getpixel((0, 0)), colors) == 0
        assert _category(rendered.getpixel((SIZE[0] - 1, 0)), colors) == 0
        assert _category(rendered.getpixel((0, SIZE[1] - 1)), colors) == 0
        assert _category(rendered.getpixel((SIZE[0] - 1, SIZE[1] - 1)), colors) == 0

    disagreement = _corner_disagreement(qt_image, tk_image, radius, colors)
    # Different QSS/Canvas antialiasing kernels and corner pixel coverage
    # legitimately differ. A grossly missing radius or border does not.
    assert disagreement <= 0.35, (
        f"Qt and Tk rounded-corner classification differs by {disagreement:.1%}"
    )

    key = f"{_name}-r{radius}-b{width}"
    qt_image.save(out / f"{key}-qt.png")
    tk_image.save(out / f"{key}-tk.png")
    difference = ImageChops.difference(qt_image, tk_image)
    difference.save(out / f"{key}-difference.png")
    with (out / f"{key}.json").open("w", encoding="utf-8") as file:
        json.dump({
            "palette": _name, "radius_px": radius, "border_width_px": width,
            "qt_reference": "QWidget/QSS", "tk_capture": "Xvfb ImageGrab",
            "corner_classification_disagreement": round(disagreement, 5),
            "pixel_difference_bbox": difference.getbbox(),
            "comparison_status": "bounded geometric parity; not pixel perfect",
        }, file, indent=2)
