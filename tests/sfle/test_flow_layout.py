"""Fixed-point block flow placement regressions (pure geometry only)."""
import pytest

from psx.sfle.flow_layout import BlockItem, InlineAtom, layout_block_children, layout_inline_atoms


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


def test_atomic_inline_boxes_wrap_and_preserve_source_order():
    positions = layout_inline_atoms(100, (
        InlineAtom(60, 20, 15),
        InlineAtom(40, 10, 8),
        InlineAtom(35, 12, 9),
    ))
    assert [(p.x, p.y, p.width, p.height) for p in positions] == [
        (0, 0, 60, 20),
        (60, 7, 40, 10),
        (0, 20, 35, 12),
    ]


def test_tall_inline_descent_affects_next_line():
    positions = layout_inline_atoms(40, (
        InlineAtom(40, 30, 10),
        InlineAtom(40, 12, 9),
    ))
    assert positions[1].y == 30


def test_oversized_inline_atom_overflows_instead_of_shrinking():
    assert layout_inline_atoms(20, (InlineAtom(45, 12, 10),))[0].width == 45


def test_inline_atom_rejects_invalid_baseline():
    with pytest.raises(ValueError, match="inline box metrics"):
        layout_inline_atoms(100, (InlineAtom(20, 10, 11),))
