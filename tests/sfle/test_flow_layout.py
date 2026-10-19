"""Fixed-point block flow placement regressions (pure geometry only)."""
import pytest

from psx.sfle.flow_layout import BlockItem, layout_block_children


def test_block_flow_stacks_siblings_without_changing_measured_width():
    boxes = layout_block_children(320, (
        BlockItem(width=320, height=40),
        BlockItem(width=220, height=25, margin_top=10, margin_left=15),
        BlockItem(width=360, height=12),
    ))
    assert [(b.x, b.y, b.width, b.height) for b in boxes] == [
        (0, 0, 320, 40),
        (15, 50, 220, 25),
        (0, 75, 360, 12),
    ]


def test_block_margins_affect_following_child_without_false_margin_collapse():
    positions = layout_block_children(100, (
        BlockItem(90, 10, margin_bottom=6),
        BlockItem(90, 10, margin_top=4),
    ))
    assert positions[1].y == 20


def test_fractional_placement_follows_cinnamon_fixed_point():
    result = layout_block_children(300, (
        BlockItem(100, 10.125),
        BlockItem(100, 9.125),
    ))
    assert result[1].y == 10.125


@pytest.mark.parametrize("width", [-1, -0.25])
def test_reject_negative_containing_width(width):
    with pytest.raises(ValueError, match="Available block"):
        layout_block_children(width, ())


def test_reject_negative_measured_dimensions():
    with pytest.raises(ValueError, match="border-box dimensions"):
        layout_block_children(100, (BlockItem(-5, 10),))
