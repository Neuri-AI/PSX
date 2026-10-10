"""F2.2.3 align-content distribution and integrated multi-line geometry."""

from __future__ import annotations

import pytest

from psx.sfle.align_content import AlignContent, distribute_cross_lines
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout
from psx.sfle.model import WritingDirection


def sample(name: str, *, cross: float = 20) -> MarginFlexItem:
    return MarginFlexItem(name, FlexBasis(60, 60, shrink=0), cross)


@pytest.mark.parametrize(("mode", "positions"), [
    (AlignContent.FLEX_START, (0, 30)),
    (AlignContent.FLEX_END, (50, 80)),
    (AlignContent.CENTER, (25, 55)),
    (AlignContent.SPACE_BETWEEN, (0, 80)),
    (AlignContent.SPACE_AROUND, (12.5, 67.5)),
    (AlignContent.SPACE_EVENLY, (50 / 3, 30 + 100 / 3)),
])
def test_align_content_changes_multiline_positions(mode, positions):
    layout = compute_margin_flex_layout(
        (sample("a"), sample("b")), 100, 100,
        wrap=FlexWrap.WRAP, cross_gap=10, align_content=mode,
    )
    assert layout.lines == (("a",), ("b",))
    assert tuple(box.border.y for box in layout.boxes) == pytest.approx(positions)


def test_align_content_stretch_expands_lines_not_fixed_height_items():
    layout = compute_margin_flex_layout(
        (sample("a"), sample("b")), 100, 100,
        wrap=FlexWrap.WRAP, cross_gap=10,
        align_content=AlignContent.STRETCH,
    )
    assert tuple(box.border.y for box in layout.boxes) == (0, 55)
    assert tuple(box.border.height for box in layout.boxes) == (20, 20)


def test_align_content_stretch_updates_alignment_inside_enlarged_line():
    from psx.sfle.cross_alignment import CrossAlign

    layout = compute_margin_flex_layout(
        (sample("a"), sample("b")), 100, 100,
        wrap=FlexWrap.WRAP, cross_gap=10,
        align_content=AlignContent.STRETCH,
        align_items=CrossAlign.CENTER,
    )
    assert tuple(box.border.y for box in layout.boxes) == (12.5, 67.5)


def test_wrap_reverse_starts_lines_from_bottom():
    layout = compute_margin_flex_layout(
        (sample("a"), sample("b")), 100, 100,
        wrap=FlexWrap.WRAP_REVERSE, cross_gap=10,
        align_content=AlignContent.SPACE_BETWEEN,
    )
    assert tuple(box.border.y for box in layout.boxes) == (80, 0)


def test_column_rtl_places_cross_lines_from_right():
    layout = compute_margin_flex_layout(
        (sample("a"), sample("b")), 100, 100,
        direction=FlexDirection.COLUMN,
        writing=WritingDirection.RTL,
        wrap=FlexWrap.WRAP, cross_gap=10,
        align_content=AlignContent.SPACE_BETWEEN,
    )
    assert tuple(box.border.x for box in layout.boxes) == (80, 0)


def test_nowrap_align_content_has_no_effect():
    layout = compute_margin_flex_layout(
        (sample("a"),), 100, 100, align_content=AlignContent.CENTER,
    )
    assert layout.boxes[0].border.y == 0


def test_negative_free_space_keeps_fixed_gap_and_no_distributed_gap():
    result = distribute_cross_lines(
        AlignContent.SPACE_BETWEEN, 30, (20, 20), gap=10,
    )
    assert result.starts == (0, 30)
    assert result.free_space == -20


def test_unsafe_center_keeps_negative_origin():
    result = distribute_cross_lines(
        AlignContent.CENTER, 30, (20, 20), gap=10,
    )
    assert result.starts == (-10, 20)


def test_empty_and_invalid_inputs():
    assert distribute_cross_lines(
        AlignContent.STRETCH, 100, (),
    ).starts == ()
    with pytest.raises(TypeError):
        distribute_cross_lines("center", 100, (20,))
    with pytest.raises(ValueError):
        distribute_cross_lines(AlignContent.CENTER, 100, (-5,))
