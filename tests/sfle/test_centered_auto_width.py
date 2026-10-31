"""Regression: a centered column flex block uses CSS shrink-to-fit width.

The nested block is represented as a Flex participant by the HTML/CSS
snapshot bridge; no Qt widget or guessed geometry is needed for this test.
"""
import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _layout(viewport: int, *, fixed: bool = False):
    constraints = LayoutConstraints(
        AvailableSize(viewport, True), AvailableSize(600, True),
    )
    paragraph_style = (("direction", "column"),)
    if fixed:
        paragraph_style += (("layout_width", "350px"),)
    nodes = (
        LayoutNode("root", None, "Flex", (
            ("direction", "column"), ("align_items", "center"),
            ("row_gap", "16px"),
        )),
        LayoutNode("paragraph", "root", "Flex", paragraph_style),
        LayoutNode("text", "paragraph", "Text", ()),
    )
    measured = MeasuredBox(
        "text", IntrinsicSizes(
            min_content_width=75, max_content_width=302,
            min_content_height=18, max_content_height=18,
            preferred_width=302, preferred_height=18,
        ),
        LayoutConstraints(AvailableSize(None, False), AvailableSize(None, False)),
        1,
    )
    return dict(PythonLayoutEngine().compute(LayoutInput(
        1, 1, WritingDirection.LTR, constraints, nodes, (measured,),
    )).boxes)


@pytest.mark.parametrize("viewport,expected", [(800, 302), (140, 140), (60, 75)])
def test_centered_auto_width_is_shrink_to_fit(viewport, expected):
    rectangles = _layout(viewport)
    assert rectangles["root"].content.width == viewport
    assert abs(rectangles["paragraph"].content.width - expected) <= 1 / 64
    assert abs(rectangles["text"].content.width - expected) <= 1 / 64


def test_explicit_width_is_not_overridden_by_shrink_to_fit():
    rectangles = _layout(140, fixed=True)
    assert rectangles["paragraph"].content.width == 350
