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


def test_incremental_solver_skips_unchanged_sibling_flex_sizing():
    from psx.sfle.model import LayoutNode

    def snapshot(left_width: int, generation: int):
        markup = psx(
            '<Flex direction="row" width="300px" height="100px">'
            f'<Flex width="{left_width}px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '<Flex width="50px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '</Flex>'
        )
        return prepare_native_layout_snapshot(
            normalize_flex_tree(markup),
            LayoutConstraints(AvailableSize(300, True), AvailableSize(100, True)),
            generation=generation,
        ).snapshot

    engine = PythonLayoutEngine()
    before = snapshot(40, 1)
    after = snapshot(60, 2)
    prior_result = engine.compute(before)
    receipt: list[str] = []
    incremental = engine.compute_incremental(
        after, previous_input=before, previous_result=prior_result,
        reused_contexts=receipt,
    )
    assert incremental.boxes == engine.compute(after).boxes
    right = after.nodes[3].node_id
    assert right in receipt, receipt


def test_incremental_solver_falls_back_when_measurement_environment_changes():
    engine = PythonLayoutEngine()
    original = _input()
    prior = engine.compute(original)
    current = _input(generation=2, width=180)
    reused: list[str] = []
    actual = engine.compute_incremental(
        current, previous_input=original, previous_result=prior,
        reused_contexts=reused,
    )
    assert actual.boxes == engine.compute(current).boxes
    assert reused == []


def test_repeated_context_updates_reuse_independent_subtree_across_1000_cycles():
    """Cinnamon's incremental result must always equal a full solve."""
    def snapshot(width, generation):
        markup = psx(
            '<Flex direction="row" width="350px" height="100px">'
            f'<Flex width="{width}px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '<Flex width="50px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '</Flex>'
        )
        return prepare_native_layout_snapshot(
            normalize_flex_tree(markup),
            LayoutConstraints(AvailableSize(350, True), AvailableSize(100, True)),
            generation=generation,
        ).snapshot

    engine = PythonLayoutEngine()
    previous = snapshot(40, 1)
    prior = engine.compute(previous)
    receipts = 0
    for generation in range(2, 1002):
        current = snapshot(40 if generation % 2 else 60, generation)
        reused = []
        result = engine.compute_incremental(
            current, previous_input=previous,
            previous_result=prior, reused_contexts=reused,
        )
        assert result.boxes == engine.compute(current).boxes
        independent = current.nodes[3].node_id
        assert independent in reused, generation
        receipts += 1
        previous, prior = current, result
    assert receipts == 1000


def test_changed_measurements_invalidate_only_changed_context_when_structure_stable():
    from psx.sfle.context_invalidation_plan import plan_context_invalidation
    from psx.sfle.model import IntrinsicSizes, MeasuredBox
    base = _input()
    leaf = base.nodes[-1].node_id
    size = IntrinsicSizes(16, 16, 12, 12, 16, 12)
    prior = replace(base, measurements=(
        MeasuredBox(leaf, size, base.constraints, 1),
    ))
    changed = replace(prior, generation=2, measurements=(
        MeasuredBox(leaf, size, prior.constraints, 2),
    ))
    plan = plan_context_invalidation(prior, changed)
    assert not plan.full_recompute
    assert plan.dirty_nodes == frozenset({leaf})
    assert base.nodes[1].node_id not in plan.dirty_nodes
