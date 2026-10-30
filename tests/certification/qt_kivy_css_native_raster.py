"""Capture actual Qt/QSS and Kivy/SDL2 CSS surfaces as comparable rasters.

The same immutable computed CSS is projected to the two native painters in
independent GUI processes. This fixture checks a *bounded* solid-color card
subset, not text/font raster equivalence or an entire application screenshot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops


CANVAS = (220, 140)
CARD = (20, 20, 180, 100)
CASES = (
    ("light", "#e9edf3", "#ffffff", "#364152", 8, 2),
    ("dark", "#161d2d", "#303a4d", "#d2a251", 16, 2),
)


def css(background: str, border: str, radius: int, width: int) -> str:
    return (
        "div {background-color:" + background +
        "; border-color:" + border +
        "; border-width:" + str(width) + "px; border-radius:" +
        str(radius) + "px}"
    )


def computed(sheet: str):
    from psx.css.cascade import StyleTarget, resolve_style
    from psx.css.parser import parse_stylesheet
    return resolve_style(parse_stylesheet(sheet), StyleTarget("div"))


def render_qt(out: Path, background: str, fill: str, border: str,
              radius: int, width: int) -> None:
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QRect
    from psx.css.native_paint import qt_semantic_stylesheet

    app = QApplication.instance() or QApplication(["qt-kivy-raster"])
    parent = QWidget()
    parent.setObjectName("rasterParent")
    parent.resize(*CANVAS)
    parent.setStyleSheet(
        "QWidget#rasterParent { background-color: " + background + "; }"
    )
    child = QWidget(parent)
    child.setObjectName("rasterCard")
    child.setGeometry(*CARD)
    child.setStyleSheet(
        "QWidget#rasterCard {" +
        qt_semantic_stylesheet(computed(css(fill, border, radius, width))) +
        "}"
    )
    parent.show()
    app.processEvents()
    assert parent.grab(QRect(0, 0, *CANVAS)).save(str(out), "PNG")
    parent.close()
    app.processEvents()


def render_kivy(out: Path, background: str, fill: str, border: str,
                radius: int, width: int) -> None:
    from kivy.core.window import Window
    from kivy.base import EventLoop
    from kivy.uix.widget import Widget
    from kivy.clock import Clock
    from psx.renderers.kivy.kivy import KivyHandle, KivyRenderer

    def rgb(value):
        return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    Window.size = CANVAS
    Window.clearcolor = (*rgb(background), 1)
    root = Widget(size_hint=(None, None), size=CANVAS)
    card = Widget(size_hint=(None, None), pos=(CARD[0], CARD[1]),
                  size=(CARD[2], CARD[3]))
    renderer = KivyRenderer()
    renderer.apply_css(
        KivyHandle("div", card, {}), computed(css(fill, border, radius, width))
    )
    root.add_widget(card)
    Window.add_widget(root)
    try:
        for _ in range(8):
            Clock.tick()
            EventLoop.idle()
        result = Window.screenshot(name=str(out))
        assert result and Path(result).is_file(), result
        if Path(result) != out:
            from shutil import copyfile
            copyfile(result, out)
    finally:
        Window.remove_widget(root)


def _rgb(value: str):
    return tuple(bytes.fromhex(value.removeprefix("#")))


def _category(pixel, choices):
    return min(range(len(choices)), key=lambda index: sum(
        (pixel[axis] - choices[index][axis]) ** 2 for axis in range(3)
    ))


def compare(out: Path, name: str, background: str, fill: str, border: str,
            radius: int, width: int):
    from PIL import ImageOps
    qt = Image.open(out / (name + "-qt.png")).convert("RGB")
    kv = Image.open(out / (name + "-kivy.png")).convert("RGB")
    assert qt.size == kv.size == CANVAS, (qt.size, kv.size)
    reference = (_rgb(background), _rgb(fill), _rgb(border))
    # The center must be the declared fill in both real toolkit rasters.
    center = (CARD[0] + CARD[2] // 2, CANVAS[1] - CARD[1] - CARD[3] // 2)
    assert _category(qt.getpixel(center), reference) == 1
    assert _category(kv.getpixel(center), reference) == 1
    # Rounded corners must show the authored parent color, never a native
    # theme blue/gray or a Kivy checker texture.
    corners = (
        (CARD[0], CANVAS[1] - CARD[1] - CARD[3]),
        (CARD[0] + CARD[2] - 1, CANVAS[1] - CARD[1] - CARD[3]),
        (CARD[0], CANVAS[1] - CARD[1] - 1),
        (CARD[0] + CARD[2] - 1, CANVAS[1] - CARD[1] - 1),
    )
    for point in corners:
        assert _category(qt.getpixel(point), reference) == 0, (point, qt.getpixel(point))
        assert _category(kv.getpixel(point), reference) == 0, (point, kv.getpixel(point))
    categories_qt = [_category(pixel, reference) for pixel in qt.getdata()]
    categories_kivy = [_category(pixel, reference) for pixel in kv.getdata()]
    disagreement = sum(a != b for a, b in zip(categories_qt, categories_kivy))
    # Compare only the authored card's corner regions; differing system window
    # decorations are not part of the captured client rectangle.
    samples = []
    for x0 in (CARD[0], CARD[0] + CARD[2] - radius):
        for y0 in (CANVAS[1] - CARD[1] - CARD[3],
                   CANVAS[1] - CARD[1] - radius):
            for y in range(y0, y0 + radius):
                for x in range(x0, x0 + radius):
                    samples.append(
                        _category(qt.getpixel((x, y)), reference) !=
                        _category(kv.getpixel((x, y)), reference)
                    )
    rate = sum(samples) / len(samples)
    ImageChops.difference(qt, kv).save(out / (name + "-difference.png"))
    metrics = {
        "case": name, "corner_class_disagreement": round(rate, 6),
        "all_pixel_class_disagreement": round(disagreement / (CANVAS[0] * CANVAS[1]), 6),
        "qt_reference": "PySide6 QWidget/QSS real grab",
        "kivy_native": "SDL2/OpenGL real window screenshot",
        "pixel_perfect_claim": False,
    }
    (out / (name + ".json")).write_text(json.dumps(metrics, indent=2))
    assert rate <= 0.35, metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--renderer", choices=("qt", "kivy"))
    parser.add_argument("--case")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.renderer:
        item = next(value for value in CASES if value[0] == args.case)
        name, background, fill, border, radius, width = item
        fn = render_qt if args.renderer == "qt" else render_kivy
        fn(output / (name + "-" + args.renderer + ".png"),
           background, fill, border, radius, width)
        return
    environment = dict(os.environ)
    environment.update(KIVY_NO_ARGS="1", KIVY_NO_FILELOG="1",
                       QT_QPA_PLATFORM="offscreen")
    for item in CASES:
        for renderer in ("qt", "kivy"):
            result = subprocess.run(
                [sys.executable, "-m",
                 "tests.certification.qt_kivy_css_native_raster",
                 "--renderer", renderer, "--case", item[0],
                 "--output", str(output)],
                env=environment, capture_output=True, text=True, timeout=90,
            )
            assert result.returncode == 0, (
                renderer, item[0], result.stdout, result.stderr
            )
        compare(output, *item)


if __name__ == "__main__":
    main()
