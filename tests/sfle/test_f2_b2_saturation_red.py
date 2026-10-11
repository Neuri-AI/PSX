"""B2 RED: every root box edge and nested coordinate uses saturating LayoutUnits.

Extreme dimensions must never escape signed int32 raw pixel bounds even if
multiple individually valid padding/border values are accumulated.
"""
from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
from psx.sfle.fixed_point import I32_MAX, I32_MIN, SCALE
from psx.sfle.margin_flex_pipeline import MarginFlexBox
from psx.sfle.margin_tree import MarginTreeNode, _translate, compute_margin_tree
from psx.sfle.model import Rect

MAX = I32_MAX / SCALE
MIN = I32_MIN / SCALE


def test_B2_root_padding_and_border_saturate_every_intermediate_dimension():
    root = MarginTreeNode(
        "root", None, MAX, 20.0,
        edges=UsedBoxEdges(
            padding=UsedEdges(left=16.0, right=8.0),
            border=UsedEdges(left=4.0, right=2.0),
        ),
    )
    box = compute_margin_tree((root,), generation=9).boxes[0]
    assert box.content.x == 20.0
    assert box.padding.width == MAX
    assert box.border.width == MAX
    for rect in (box.content, box.padding, box.border):
        for dimension in ("x", "y", "width", "height"):
            value = getattr(rect, dimension)
            assert MIN <= value <= MAX
            assert int(value * SCALE) == value * SCALE


def test_B2_nested_positive_and_negative_translation_saturates():
    original = MarginFlexBox(
        "a",
        Rect(100.0, -100.0, 12.0, 13.0),
        Rect(100.0, -100.0, 12.0, 13.0),
        Rect(100.0, -100.0, 12.0, 13.0),
        0.0, 0.0, 0,
    )
    translated = _translate(original, MAX, MIN)
    for rect in (translated.content, translated.padding, translated.border):
        assert rect.x == MAX
        assert rect.y == MIN
        assert rect.width == 12.0
        assert rect.height == 13.0


def test_B2_edge_pipeline_python_inset_saturates_physical_offsets():
    from psx.sfle.box_geometry import used_box_rect, UsedBoxEdges, UsedEdges
    from psx.sfle.model import Rect
    from psx.sfle.fixed_point import I32_MIN, I32_MAX, SCALE
    maximum=I32_MAX/SCALE
    minimum=I32_MIN/SCALE
    original=Rect(maximum, minimum, maximum, maximum)
    edges=UsedBoxEdges(margin=UsedEdges(left=32.0,top=16.0))
    box=used_box_rect(original, edges)
    assert box.border.x==maximum
    assert box.border.y==minimum+16.0
    assert box.border.width==maximum-32.0
    assert box.border.height==maximum-16.0
    for value in (box.border.x,box.border.y,box.border.width,box.border.height):
        assert minimum<=value<=maximum
        assert value*SCALE==int(value*SCALE)
