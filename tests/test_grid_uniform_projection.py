"""Compressed structural receipts must equal Cinnamon's complete Grid solve."""
from types import SimpleNamespace

import pytest

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.layout.contracts.model import AvailableSize, IntrinsicSizes, LayoutConstraints
from psx.layout.engine.backend import load_layout_engine
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.grid_early_viewport import build_early_viewport_plan
from psx.layout.grid.grid_native_composition import prepare_composed_grid
from psx.layout.grid.grid_uniform_projection import (
    certify_uniform_flows, prepare_uniform_grid, prepare_deferred_grid_window,
)


def viewport(width, height=100):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))


def scene(count):
    body = "".join(
        f'<GridItem span="3" key="card-{i}"><div style="padding:12px">'
        '<div>Title</div><div>Value</div></div></GridItem>' for i in range(count))
    normalized = normalize_flex_tree(psx(f'<div><Grid gap="7.5px">{body}</Grid></div>'))
    return normalized, normalized._participating_roots()[0].effective_children[0]


def native_engine():
    engine = load_layout_engine()
    if not callable(getattr(getattr(engine, "_module", None),
                            "compute_uniform_grid_template", None)):
        pytest.skip("Optional indexed Cinnamon transport is unavailable")
    return engine


def compose(grid, width, engine):
    return prepare_composed_grid(grid, content_width=width, generation=1,
        current_generation=1, measure_leaf=lambda *args: IntrinsicSizes(8, 30, 12, 20, 30, 20),
        is_ui_thread=lambda: True, engine=engine, viewport_constraints=viewport(width))


def test_indexed_tracks_and_visible_flow_boxes_equal_complete_solve(monkeypatch):
    engine = native_engine()
    normalized, grid = scene(400)
    initial = compose(grid, 480, engine)
    proof = certify_uniform_flows(initial, build_early_viewport_plan(normalized, grid))
    assert proof is not None
    calls, compute = [], engine.compute

    def audited(snapshot):
        calls.append(snapshot.nodes[0].node_id)
        return compute(snapshot)

    monkeypatch.setattr(engine, "compute", audited)
    # A previously live offscreen group participates in the native transition
    # even though the new viewport alone would not select it.
    live = SimpleNamespace(node=grid.effective_children[-1].source)
    for width in (560, 701.125, 900):
        calls.clear()
        projected = prepare_uniform_grid(proof, width=width, viewport=viewport(width),
            generation=2, engine=engine, native_instances=(live,))
        assert projected is not None
        assert not projected.provisional_ids
        assert len(calls) == len(projected.viewport_roots) < 20
        assert initial.prepared.child_ids[-1] in projected.viewport_roots
        complete = compose(grid, width, engine)
        assert tuple(projected.prepared.placements) == complete.prepared.placements
        assert tuple(projected.prepared.rows) == complete.prepared.rows
        assert projected.content_height == complete.content_height
        for identifier in projected.viewport_roots:
            assert projected.nested_flow[identifier].result.boxes == complete.nested_flow[identifier].result.boxes
        assert len(projected.native_deferred_flows) > 380


def test_projection_fails_closed_for_uncertain_width_partial_rows_and_backend():
    engine = native_engine()
    normalized, grid = scene(40)
    initial = compose(grid, 480, engine)
    proof = certify_uniform_flows(initial, build_early_viewport_plan(normalized, grid))
    args = dict(width=560, viewport=viewport(560), generation=2, native_instances=())
    assert prepare_uniform_grid(proof, engine=PythonLayoutEngine(), **args) is None
    assert prepare_uniform_grid(proof, engine=engine, **dict(args, pixel_scale=2)) is None
    assert prepare_uniform_grid(proof, engine=engine, **dict(args, width=1)) is None
    reasons = []
    assert prepare_uniform_grid(proof, engine=engine, report_fallback=reasons.append,
                                **dict(args, width=1)) is None
    assert reasons == ["text-width-dependency"]
    partial_root, partial_grid = scene(41)
    partial = compose(partial_grid, 480, engine)
    assert certify_uniform_flows(partial, build_early_viewport_plan(partial_root, partial_grid)) is None


def test_clamped_native_width_is_not_proof_that_wrapped_height_is_stable():
    engine = native_engine()
    _normalized, grid = scene(4)

    def constrained(*args):
        # Toolkit ports can clamp their preferred width while reporting a
        # multi-line texture. The independent natural receipt is authoritative.
        return IntrinsicSizes(10, 100, 20, 40, 100, 40)

    constrained.unwrapped = lambda *args: IntrinsicSizes(10, 300, 20, 20, 300, 20)
    result = prepare_composed_grid(grid, content_width=480, generation=1,
        current_generation=1, measure_leaf=constrained, is_ui_thread=lambda: True,
        engine=engine, viewport_constraints=viewport(480))
    assert all(flow.unwrapped_at_width is None for flow in result.nested_flow.values())


def test_width_dependent_tail_never_enters_measurement_or_visible_geometry():
    engine = native_engine()
    normalized, grid = scene(400)
    initial = compose(grid, 480, engine)
    proof = certify_uniform_flows(initial, build_early_viewport_plan(normalized, grid))
    reads = []

    def measured(identifier, node, width):
        reads.append(identifier)
        height = 40 if width < proof.threshold else 20
        return IntrinsicSizes(8, 30, 12, height, 30, height)

    def complete(root):
        return prepare_composed_grid(root, content_width=100, generation=2,
            current_generation=2, measure_leaf=measured, is_ui_thread=lambda: True,
            engine=engine, viewport_constraints=viewport(100))

    projected = prepare_deferred_grid_window(proof, width=100, viewport=viewport(100),
        generation=2, engine=engine, native_instances=(), compose_prefix=complete)
    assert projected is not None and projected.provisional_ids
    assert len(reads) == len(projected.viewport_roots) * 2 < 40
    assert projected.content_width == 100
    full = complete(grid)
    expected = {p.node_id: p for p in full.prepared.placements}
    for placement in projected.prepared.placements.selected(projected.viewport_roots):
        assert placement == expected[placement.node_id]
    first_dirty = len(projected.viewport_roots)
    assert projected.prepared.placements[first_dirty].y >= 196
    assert projected.native_deferred_flows == frozenset()
    # Its provisional extent cannot masquerade as complete current geometry.
    from psx.layout.grid.grid_geometry_reuse import AcceptedGridGeometryReuse
    cache = AcceptedGridGeometryReuse()
    cache.begin(normalized, 0, "qt", 1, {})
    cache.stage(projected.prepared.grid_id, grid, 100, viewport(100), projected)
    cache.accept()
    assert cache.lookup(projected.prepared.grid_id, grid, 100, viewport(100), 3) is None


def test_native_baseline_is_clamped_to_authored_cross_box_like_python():
    from psx.layout.contracts.model import LayoutInput, LayoutNode, MeasuredBox, WritingDirection
    from psx.layout.contracts.lengths import Length

    engine = native_engine()
    constraints = viewport(800, 50)
    nodes = (
        LayoutNode("root", None, "Flex", (("direction", "row"), ("align_items", "flex-start"))),
        LayoutNode("text", "root", "Text", (("layout_width", Length.px(80)),
            ("layout_height", Length.px(20)), ("flex_basis", Length.px(80)), ("flex_shrink", 0))),
    )
    metrics = IntrinsicSizes(20, 80, 30, 30, 80, 30, baseline=27)
    request = LayoutInput(1, 1, WritingDirection.LTR, constraints, nodes,
                         (MeasuredBox("text", metrics, constraints, 0),))
    expected = PythonLayoutEngine().compute(request)
    actual = engine.compute(request)
    assert actual.boxes == expected.boxes
