"""Incremental Cinnamon opt-in reuse regression tests."""
from dataclasses import replace

from psx import Flex, psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.incremental_result_reuse import reuse_unchanged_layout
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot


def _input(*, width=160, generation=1, gap="8px"):
    tree = psx(
        f'<Flex direction="row" width="120px" height="40px" gap="{gap}">'
        '<Flex width="40px" height="10px" />'
        '<Flex width="30px" height="10px" />'
        '</Flex>'
    )
    constraints = LayoutConstraints(AvailableSize(width, True), AvailableSize(90, True))
    return prepare_native_layout_snapshot(
        normalize_flex_tree(tree), constraints, generation=generation
    ).snapshot


def test_identical_snapshot_reuses_boxes_without_changing_generation():
    engine = PythonLayoutEngine()
    original = _input(generation=1)
    prior = engine.compute(original)
    current = replace(original, generation=2)
    reused = reuse_unchanged_layout(original, prior, current)
    assert reused is not None
    assert reused.generation == 2
    assert reused.boxes == prior.boxes
    assert reused.boxes == engine.compute(current).boxes
    assert engine.compute_incremental(
        current, previous_input=original, previous_result=prior
    ).boxes == engine.compute(current).boxes


def test_layout_and_environment_mutations_force_full_compute():
    engine = PythonLayoutEngine()
    original = _input()
    prior = engine.compute(original)
    for current in (
        _input(gap="15px", generation=2),
        _input(width=200, generation=2),
    ):
        assert reuse_unchanged_layout(original, prior, current) is None
        assert engine.compute_incremental(
            current, previous_input=original, previous_result=prior
        ).boxes == engine.compute(current).boxes
    same = replace(original, generation=2)
    assert reuse_unchanged_layout(
        original, prior, same, native_measurement_invalidated=True
    ) is None
    assert reuse_unchanged_layout(
        original, replace(prior, generation=99), same
    ) is None
    assert reuse_unchanged_layout(
        original, replace(prior, diagnostics=("unsafe",)), same
    ) is None


def test_changed_measurement_revision_and_structure_disable_reuse():
    from psx.sfle.model import IntrinsicSizes, MeasuredBox
    engine = PythonLayoutEngine()
    original = _input()
    prior = engine.compute(original)
    metric = IntrinsicSizes(10, 10, 10, 10, 10, 10)
    leaf = original.nodes[-1].node_id
    measured = replace(original, measurements=(
        MeasuredBox(leaf, metric, original.constraints, 1),
    ))
    assert reuse_unchanged_layout(original, prior, measured) is None
    changed_structure = replace(original, nodes=original.nodes[:-1])
    assert reuse_unchanged_layout(original, prior, changed_structure) is None


def test_context_plan_scopes_changed_flex_sibling_without_partial_solver_claim():
    from psx.sfle.context_invalidation_plan import plan_context_invalidation
    from psx.sfle.model import LayoutNode
    initial = _input()
    nodes = list(initial.nodes)
    # Modify the first child, leaving the second independent child untouched.
    first = nodes[1]
    nodes[1] = replace(
        first, style=tuple((key, "50px" if key == "width" else value)
                           for key, value in first.style),
    )
    current = replace(initial, generation=2, nodes=tuple(nodes))
    plan = plan_context_invalidation(initial, current)
    assert not plan.full_recompute
    assert plan.dirty_nodes == frozenset({first.node_id})
    assert initial.nodes[2].node_id not in plan.dirty_nodes
    engine = PythonLayoutEngine()
    assert engine.compute_incremental(
        current, previous_input=initial,
        previous_result=engine.compute(initial),
    ).boxes == engine.compute(current).boxes
    assert plan_context_invalidation(initial, _input(width=200)).full_recompute
    assert plan_context_invalidation(None, current).full_recompute
