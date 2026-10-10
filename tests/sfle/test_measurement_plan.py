"""F2.2.4 preorder dependency planning and immutable measurement handoff."""
from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.measurement_plan import accept_measurement, plan_measurements
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)


def dimensions(w: float, h: float) -> LayoutConstraints:
    return LayoutConstraints(AvailableSize(w, True), AvailableSize(h, True))


def tree(*, generation: int = 2, cached: tuple[MeasuredBox, ...] = ()) -> LayoutInput:
    return LayoutInput(
        schema_version=1, generation=generation, direction=WritingDirection.LTR,
        constraints=dimensions(100, 100),
        nodes=(
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("child", "root", "Flex", ()),
            LayoutNode("leaf", "child", "Text", ()),
        ),
        measurements=cached,
    )


def measured(node_id: str, constraints: LayoutConstraints, revision: int) -> MeasuredBox:
    return MeasuredBox(
        node_id=node_id, constraints=constraints, revision=revision,
        intrinsic=IntrinsicSizes(4, 10, 5, 10, 7, 8),
    )


def constraints():
    return (("child", dimensions(60, 60)), ("leaf", dimensions(30, 10)))


def test_measurement_requests_follow_descendant_first_order():
    plan = plan_measurements(tree(), child_constraints=constraints())
    assert [req.node_id for req in plan.requests] == ["leaf", "child", "root"]
    assert all(req.generation == 2 for req in plan.requests)
    assert plan.reusable == ()


def test_cache_hit_requires_matching_constraints_and_revision():
    child = measured("child", dimensions(60, 60), revision=3)
    plan = plan_measurements(
        tree(cached=(child,)), child_constraints=constraints(),
        revisions=(("child", 3),),
    )
    assert [request.node_id for request in plan.requests] == ["leaf", "root"]
    assert plan.reusable == (child,)


def test_constraint_changes_invalidate_only_matching_node_snapshot():
    child = measured("child", dimensions(60, 60), revision=3)
    changed = (("child", dimensions(70, 60)), ("leaf", dimensions(30, 10)))
    plan = plan_measurements(
        tree(cached=(child,)), child_constraints=changed,
        revisions=(("child", 3),),
    )
    assert "child" in [request.node_id for request in plan.requests]
    assert plan.reusable == ()


def test_revision_change_invalidates_even_unchanged_constraints():
    child = measured("child", dimensions(60, 60), revision=2)
    plan = plan_measurements(
        tree(cached=(child,)), child_constraints=constraints(),
        revisions=(("child", 3),),
    )
    assert "child" in [request.node_id for request in plan.requests]


def test_unresolved_child_constraints_are_not_guessed_from_parent():
    with pytest.raises(SFLEError) as exc:
        plan_measurements(tree(), child_constraints=(("child", dimensions(60, 60)),))
    assert exc.value.code == DiagnosticCode.UNSUPPORTED_MEASUREMENT


def test_reject_duplicate_constraint_and_root_conflict():
    with pytest.raises(SFLEError):
        plan_measurements(
            tree(), child_constraints=(
                ("child", dimensions(60, 60)),
                ("child", dimensions(60, 60)),
            ),
        )
    with pytest.raises(SFLEError):
        plan_measurements(
            tree(), child_constraints=(("root", dimensions(90, 100)), *constraints()),
        )


def test_accept_native_measurement_only_for_current_generation():
    plan = plan_measurements(tree(), child_constraints=constraints())
    request = plan.requests[0]
    result = measured(request.node_id, request.constraints, request.revision)
    assert accept_measurement(request, result, current_generation=2) is result
    with pytest.raises(SFLEError):
        accept_measurement(request, result, current_generation=3)
    with pytest.raises(SFLEError):
        accept_measurement(request, replace(result, revision=8), current_generation=2)


def test_empty_layout_has_empty_plan():
    empty = LayoutInput(1, 0, WritingDirection.LTR, dimensions(100, 100), (), ())
    assert plan_measurements(empty).requests == ()
