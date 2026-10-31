"""Regression: CSS img one-axis sizing must transfer native aspect ratio.

The native width/height props are intentionally unset. Browser-style CSS
on <img> owns used geometry; painting must never reserve the source's
unscaled intrinsic block size after a CSS width override.
"""
from dataclasses import replace
import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.lengths import Length
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints,
    LayoutInput, LayoutNode, MeasuredBox, WritingDirection,
)
from psx.sfle.replaced_image_sizing import with_replaced_image_aspect_ratios


def _input(image_style, *, viewport=800, source=(400, 300)):
    constraints = LayoutConstraints(
        AvailableSize(viewport, True), AvailableSize(600, True),
    )
    nodes = (
        LayoutNode("root", None, "Flex", (
            ("direction", "column"), ("align_items", "center"),
            ("justify_content", "center"), ("row_gap", "16px"),
        )),
        LayoutNode("image", "root", "Image", tuple(image_style.items())),
        LayoutNode("heading", "root", "Text", ()),
        LayoutNode("button", "root", "Button", ()),
    )
    w, h = source
    measurements = tuple(
        MeasuredBox(name, IntrinsicSizes(wi, wi, hi, hi, wi, hi),
                    constraints, 1)
        for name, wi, hi in (
            ("image", float(w), float(h)),
            ("heading", 200.0, 40.0),
            ("button", 84.0, 26.0),
        )
    )
    return LayoutInput(1, 1, WritingDirection.LTR,
                       constraints, nodes, measurements)


@pytest.mark.parametrize("style,expected", [
    ({"layout_width": Length.px(200)}, (200, 150)),
    ({"layout_height": Length.px(75)}, (100, 75)),
    ({"layout_width": Length.percent(0.25)}, (200, 150)),
    ({"layout_width": Length.px(200),
      "layout_height": Length.px(80)}, (200, 80)),
    ({}, (400, 300)),
])
def test_css_image_intrinsic_aspect_controls_its_actual_layout_box(style, expected):
    snapshot = with_replaced_image_aspect_ratios(_input(style))
    projected = dict(snapshot.nodes[1].style)
    if ("layout_width" in style) != ("layout_height" in style):
        assert projected["aspect_ratio"] == pytest.approx(4 / 3)
    else:
        assert "aspect_ratio" not in projected
    boxes = dict(PythonLayoutEngine().compute(snapshot).boxes)
    assert boxes["image"].content.width == pytest.approx(expected[0], abs=1 / 64)
    assert boxes["image"].content.height == pytest.approx(expected[1], abs=1 / 64)
    # Flex gap belongs between the *used painted image box* and heading.
    assert boxes["heading"].border.y - (
        boxes["image"].border.y + boxes["image"].border.height
    ) == pytest.approx(16, abs=1 / 64)


def test_css_image_resizes_without_reusing_old_native_height():
    for viewport, image_width in ((800, 200), (1200, 300), (400, 100)):
        snapshot = with_replaced_image_aspect_ratios(_input(
            {"layout_width": Length.percent(.25)}, viewport=viewport,
        ))
        boxes = dict(PythonLayoutEngine().compute(snapshot).boxes)
        assert boxes["image"].content.width == pytest.approx(image_width, abs=1 / 64)
        assert boxes["image"].content.height == pytest.approx(image_width * .75, abs=1 / 64)


def test_css_explicit_second_axis_and_aspect_are_not_overwritten():
    snapshot = _input({"layout_width": "200px", "aspect_ratio": 2.0})
    resolved = with_replaced_image_aspect_ratios(snapshot)
    assert dict(resolved.nodes[1].style)["aspect_ratio"] == 2.0
    assert with_replaced_image_aspect_ratios(resolved) == resolved


def test_missing_image_intrinsic_ratio_does_not_guess():
    snapshot = _input({"layout_width": "200px"}, source=(0, 0))
    assert "aspect_ratio" not in dict(
        with_replaced_image_aspect_ratios(snapshot).nodes[1].style
    )
