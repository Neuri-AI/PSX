"""F2.2.4 restricted CSS used-size preparation regression tests."""

import pytest

from psx.sfle.constraint_propagation import ChildSizing
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.percentage_box_sizing import BoxSizing
from psx.sfle.sizing import ResolutionKind
from psx.sfle.used_size import resolve_used_content_size


def constraints(width: AvailableSize, height: AvailableSize) -> LayoutConstraints:
    return LayoutConstraints(width, height)


def definite(value: float) -> AvailableSize:
    return AvailableSize(value, True)


def indefinite() -> AvailableSize:
    return AvailableSize(None, False)


def test_percent_border_box_content_resolution():
    used = resolve_used_content_size(
        constraints(definite(200), definite(80)),
        ChildSizing(Length.percent(0.5), Length.percent(0.25)),
        box_sizing=BoxSizing.BORDER_BOX,
        horizontal_padding_border=20,
        vertical_padding_border=10,
    )
    assert used.content == constraints(definite(80), definite(10))
    assert used.width_kind == ResolutionKind.USED


def test_content_box_does_not_subtract_edges():
    used = resolve_used_content_size(
        constraints(definite(200), definite(80)),
        ChildSizing(Length.px(100), Length.px(20)),
        box_sizing=BoxSizing.CONTENT_BOX,
        horizontal_padding_border=20,
        vertical_padding_border=10,
    )
    assert used.content == constraints(definite(100), definite(20))


def test_border_box_has_padding_border_floor():
    used = resolve_used_content_size(
        constraints(definite(200), definite(80)),
        ChildSizing(Length.px(10), Length.px(8)),
        box_sizing=BoxSizing.BORDER_BOX,
        horizontal_padding_border=20,
        vertical_padding_border=10,
    )
    assert used.content == constraints(definite(0), definite(0))


def test_auto_and_indefinite_percentage_remain_unresolved():
    used = resolve_used_content_size(
        constraints(definite(200), indefinite()),
        ChildSizing(Length(LengthKind.AUTO), Length.percent(0.5)),
        box_sizing=BoxSizing.CONTENT_BOX,
    )
    assert used.content == constraints(indefinite(), indefinite())
    assert used.width_kind == ResolutionKind.AUTO
    assert used.height_kind == ResolutionKind.UNRESOLVED_PERCENT


@pytest.mark.parametrize("edges", [-1.0, float("nan"), float("inf")])
def test_invalid_edges_rejected_even_when_axis_unresolved(edges: float):
    with pytest.raises(ValueError):
        resolve_used_content_size(
            constraints(indefinite(), indefinite()),
            ChildSizing(Length(LengthKind.AUTO), Length(LengthKind.AUTO)),
            box_sizing=BoxSizing.CONTENT_BOX,
            horizontal_padding_border=edges,
        )
