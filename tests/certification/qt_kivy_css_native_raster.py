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
    ("light-button", "#e9edf3", "#ffffff", "#364152", 8, 2),
    ("dark-button", "#161d2d", "#303a4d", "#d2a251", 16, 2),
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
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget
    from PySide6.QtCore import QRect
    from psx.css.native_paint import qt_semantic_stylesheet

    app = QApplication.instance() or QApplication(["qt-kivy-raster"])
    parent = QWidget()
    parent.setObjectName("rasterParent")
    parent.resize(*CANVAS)
    parent.setStyleSheet(
        "QWidget#rasterParent { background-color: " + background + "; }"
    )
    child = (QPushButton("", parent) if "-button-" in out.name else QWidget(parent))
    child.setObjectName("rasterCard")
    child.setGeometry(*CARD)
    child_selector = "QPushButton" if "-button-" in out.name else "QWidget"
    child.setStyleSheet(
        child_selector + "#rasterCard {" +
        qt_semantic_stylesheet(computed(css(fill, border, radius, width))) +
        "}"
    )
    parent.show()
    app.processEvents()
    assert parent.grab(QRect(0, 0, *CANVAS)).save(str(out), "PNG")
    # Retina QPixmap snapshots are physical pixels; the comparison is made
    # in the reference application's logical client coordinates.
    with Image.open(out) as native_image:
        if native_image.size != CANVAS:
            native_image.convert("RGB").resize(
                CANVAS, Image.Resampling.LANCZOS
            ).save(out)
    parent.close()
    app.processEvents()


def render_kivy(out: Path, background: str, fill: str, border: str,
                radius: int, width: int) -> None:
    from kivy.core.window import Window
    from kivy.base import EventLoop
    from kivy.uix.widget import Widget
    from kivy.uix.button import Button
    from kivy.clock import Clock
    from psx.renderers.kivy.kivy import KivyHandle, KivyRenderer
    from psx.sfle.kivy_display_scale import KivyDisplayScale

    def rgb(value):
        return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    if Window is None:
        raise RuntimeError(
            "Kivy did not create a usable SDL2/OpenGL window. "
            "This native visual gate cannot pass on a runner without a "
            "graphics context; mathematical Retina tests are not a substitute."
        )
    # On Cocoa/SDL2, assigning Window.system_size is asynchronous. Sampling
    # Window.size immediately afterwards mixes the *previous* drawable size
    # with the *new* system size (e.g. 1600/220, 1200/140) and invents an
    # invalid density. Keep the real current window unchanged and capture a
    # fixed logical client-area crop from its bottom-left corner instead.
    observed = KivyDisplayScale.from_window(Window)
    display_scale = observed.css_scale
    drawable = tuple(Window.size)
    if drawable[0] < CANVAS[0] * display_scale or drawable[1] < CANVAS[1] * display_scale:
        raise RuntimeError(
            f"Native Kivy window is too small for a {CANVAS} logical crop: "
            f"size={drawable}, ratio={observed.snapshot()}"
        )
    Window.clearcolor = (*rgb(background), 1)
    root = Widget(size_hint=(None, None), size=drawable)
    is_button = "-button-" in out.name
    card = (Button(text="") if is_button else Widget())
    card.size_hint = (None, None)
    card.pos = (CARD[0] * display_scale, CARD[1] * display_scale)
    card.size = (CARD[2] * display_scale, CARD[3] * display_scale)
    renderer = KivyRenderer()
    renderer.apply_css(
        KivyHandle("Button" if is_button else "div", card, {}),
        computed(css(fill, border, radius, width))
    )
    root.add_widget(card)
    Window.add_widget(root)
    try:
        # SDL2 can yield an empty first framebuffer when a window is created
        # and captured without runTouchApp(). Request actual present frames
        # and verify that the authored fill reached the GPU before capture.
        # This is a bounded readiness check, not a synthetic screenshot.
        center = (
            round((CARD[0] + CARD[2] // 2) * display_scale),
            round(drawable[1] - (CARD[1] + CARD[3] // 2) * display_scale),
        )
        expected = _rgb(fill)
        for attempt in range(16):
            Window.canvas.ask_update()
            Clock.tick()
            EventLoop.idle()
            result = Window.screenshot(name=str(out))
            assert result and Path(result).is_file(), result
            with Image.open(result) as captured:
                pixel = captured.convert("RGB").getpixel(center)
            if sum(abs(pixel[i] - expected[i]) for i in range(3)) <= 6:
                with Image.open(result) as native_image:
                    physical_width = round(CANVAS[0] * display_scale)
                    physical_height = round(CANVAS[1] * display_scale)
                    physical_size = native_image.size
                    if physical_size[0] < physical_width or physical_size[1] < physical_height:
                        raise RuntimeError(
                            "Kivy framebuffer does not cover the logical crop: "
                            f"{physical_size} vs {physical_width}x{physical_height}"
                        )
                    native_image.convert("RGB").crop((
                        0, physical_size[1] - physical_height,
                        physical_width, physical_size[1],
                    )).resize(CANVAS, Image.Resampling.LANCZOS).save(out)
                break
        else:
            raise AssertionError(
                "Kivy SDL2 never presented authored CSS fill; "
                f"last center pixel={pixel}, expected={expected}"
            )
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
    # Measure the authored stroke independently of the four anti-aliased
    # corners. A card can otherwise pass a very generous corner tolerance
    # while Kivy draws the wrong thickness along its straight edges.
    x, y, w, h = CARD
    top = CANVAS[1] - y - h
    bottom = CANVAS[1] - y - 1
    inset = max(radius + 2, width + 2)
    edge_points = []
    for offset in range(0, max(4, width + 3)):
        edge_points.extend(
            (column, row)
            for column in range(x + inset, x + w - inset)
            for row in (top + offset, bottom - offset)
        )
        edge_points.extend(
            (column, row)
            for row in range(top + inset, bottom - inset)
            for column in (x + offset, x + w - 1 - offset)
        )
    edge_disagreement = sum(
        _category(qt.getpixel(point), reference) !=
        _category(kv.getpixel(point), reference)
        for point in edge_points
    ) / len(edge_points)
    ImageChops.difference(qt, kv).save(out / (name + "-difference.png"))
    metrics = {
        "case": name, "corner_class_disagreement": round(rate, 6),
        "all_pixel_class_disagreement": round(disagreement / (CANVAS[0] * CANVAS[1]), 6),
        "straight_edge_class_disagreement": round(edge_disagreement, 6),
        "qt_reference": "PySide6 QWidget/QSS real grab",
        "kivy_native": "SDL2/OpenGL real window screenshot",
        "pixel_perfect_claim": False,
    }
    (out / (name + ".json")).write_text(json.dumps(metrics, indent=2))
    assert rate <= 0.35, metrics
    # A mismatched straight stroke cannot hide inside a corner-only check.
    assert edge_disagreement <= 0.15, metrics


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
            command = [
                sys.executable, "-m",
                "tests.certification.qt_kivy_css_native_raster",
                "--renderer", renderer, "--case", item[0],
                "--output", str(output),
            ]
            try:
                result = subprocess.run(
                    command, env=environment, capture_output=True,
                    text=True, timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"{renderer} {item[0]} did not present a native frame "
                    "within the bounded certification window. "
                    "This is a failed native graphics gate, not a skip. "
                    f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
                ) from exc
            assert result.returncode == 0, (
                renderer, item[0], result.stdout, result.stderr
            )
        compare(output, *item)


if __name__ == "__main__":
    main()
