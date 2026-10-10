"""F2.2.4 explicit parent content box to child CSS measurement constraints."""

from __future__ import annotations

import pytest

from psx.sfle.constraint_propagation import (
    ChildSizing, plan_styled_measurements, resolve_child_constraints,
)
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from psx.sfle.sizing import ResolutionKind


def dimension(value: float | None, definite: bool = True) -> AvailableSize:
    return AvailableSize(value, definite)


def constraints(width: AvailableSize, height: AvailableSize) -> LayoutConstraints:
    return LayoutConstraints(width, height)


def size(width: float, height: float) -> LayoutConstraints:
    return constraints(dimension(width), dimension(height))


def tree() -> LayoutInput:
    return LayoutInput(
        schema_version=1,
        generation=9,
        direction=WritingDirection.LTR,
        constraints=size(300, 200),
        nodes=(
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("child", "root", "Flex", ()),
            LayoutNode("leaf", "child", "Text", ()),
        ),
        measurements=(),
    )


def test_child_percentages_use_parent_content_corresponding_axes():
    result = resolve_child_constraints(
        size(200, 80), ChildSizing(Length.percent(0.5), Length.percent(0.25)),
    )
    assert result.constraints == size(100, 20)
    assert result.width_kind == ResolutionKind.USED
    assert result.height_kind == ResolutionKind.USED


def test_indefinite_parent_height_keeps_percentage_unresolved():
    parent = constraints(dimension(200), dimension(900, False))
    result = resolve_child_constraints(
        parent, ChildSizing(Length.percent(0.5), Length.percent(0.25)),
    )
    assert result.constraints.width == dimension(100)
    assert result.constraints.height == dimension(None, False)
    assert result.height_kind == ResolutionKind.UNRESOLVED_PERCENT


def test_auto_and_intrinsic_are_not_guessed_as_parent_dimensions():
    result = resolve_child_constraints(
        size(200, 80), ChildSizing(
            Length(LengthKind.AUTO), Length(LengthKind.MAX_CONTENT),
        ),
    )
    assert result.constraints == constraints(dimension(None, False), dimension(None, False))
    assert result.width_kind == ResolutionKind.AUTO
    assert result.height_kind == ResolutionKind.INTRINSIC


def test_explicit_pixels_need_no_definite_parent_axis():
    parent = constraints(dimension(None, False), dimension(None, False))
    result = resolve_child_constraints(
        parent, ChildSizing(Length.px(30), Length.px(12)),
    )
    assert result.constraints == size(30, 12)


def test_styled_tree_connects_known_parent_content_to_measurement_plan():
    plan = plan_styled_measurements(
        tree(),
        parent_content=(("root", size(200, 80)), ("child", size(100, 20))),
        child_sizing=(
            ("child", ChildSizing(Length.percent(0.5), Length.percent(0.25))),
            ("leaf", ChildSizing(Length.percent(0.5), Length.px(10))),
        ),
    )
    assert [request.node_id for request in plan.requests] == ["leaf", "child", "root"]
    assert plan.requests[0].constraints == size(50, 10)
    assert plan.requests[1].constraints == size(100, 20)
    assert plan.requests[2].constraints == size(300, 200)


def test_missing_established_parent_content_is_not_inferred_from_constraints():
    with pytest.raises(SFLEError) as exc:
        plan_styled_measurements(
            tree(),
            parent_content=(("root", size(200, 80)),),
            child_sizing=(
                ("child", ChildSizing(Length.px(100), Length.px(20))),
                ("leaf", ChildSizing(Length.percent(0.5), Length.px(10))),
            ),
        )
    assert exc.value.code == DiagnosticCode.UNSUPPORTED_MEASUREMENT


def test_duplicate_and_unknown_inputs_are_rejected():
    with pytest.raises(SFLEError):
        plan_styled_measurements(
            tree(),
            parent_content=(("root", size(200, 80)), ("root", size(200, 80))),
            child_sizing=(),
        )
    with pytest.raises(SFLEError):
        plan_styled_measurements(
            tree(),
            parent_content=(("missing", size(200, 80)),),
            child_sizing=(),
        )
    with pytest.raises(SFLEError):
        plan_styled_measurements(
            tree(),
            parent_content=(("root", size(200, 80)),),
            child_sizing=(("root", ChildSizing(Length.px(1), Length.px(2))),),
        )


def test_invalid_length_type_and_negative_used_size_rejected():
    with pytest.raises(TypeError):
        ChildSizing("50%", Length.px(10))
    with pytest.raises(ValueError):
        resolve_child_constraints(
            size(100, 100), ChildSizing(Length.px(-2), Length.px(10)),
        )


def test_used_boxes_supply_css_content_instead_of_border_dimensions():
    from psx.sfle.constraint_propagation import plan_used_box_measurements
    from psx.sfle.model import BoxRect, Rect

    def box(width: float, height: float) -> BoxRect:
        content = Rect(4, 6, width, height)
        border = Rect(0, 0, width + 8, height + 12)
        return BoxRect(content, border, border, border)

    plan = plan_used_box_measurements(
        tree(),
        used_boxes=(("root", box(200, 80)), ("child", box(100, 20))),
        child_sizing=(
            ("child", ChildSizing(Length.percent(0.5), Length.percent(0.25))),
            ("leaf", ChildSizing(Length.percent(0.5), Length.px(10))),
        ),
    )
    assert [request.node_id for request in plan.requests] == ["leaf", "child", "root"]
    assert plan.requests[0].constraints == size(50, 10)
    assert plan.requests[1].constraints == size(100, 20)


def test_missing_duplicate_and_wrong_type_used_boxes_fail_closed():
    from psx.sfle.constraint_propagation import plan_used_box_measurements
    from psx.sfle.model import BoxRect, Rect

    rect = Rect(0, 0, 200, 80)
    used = BoxRect(rect, rect, rect, rect)
    styles = (
        ("child", ChildSizing(Length.percent(0.5), Length.px(20))),
        ("leaf", ChildSizing(Length.px(10), Length.px(10))),
    )
    for boxes in ((), (("root", used), ("root", used)), (("missing", used),)):
        with pytest.raises(SFLEError):
            plan_used_box_measurements(tree(), used_boxes=boxes, child_sizing=styles)
    with pytest.raises(TypeError):
        plan_used_box_measurements(
            tree(), used_boxes=(("root", size(200, 80)),), child_sizing=styles,
        )
