"""Early P2 Grid optimization must skip *upstream* native measurement.

Only already committed immutable Flow cards whose old and target bounds are
both outside the viewport may reuse prior intrinsic hints. Those results
are provisional and MUST be replaced with full Cinnamon geometry at idle.
"""
from types import SimpleNamespace

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.layout.contracts.model import AvailableSize, IntrinsicSizes, LayoutConstraints
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.grid_early_viewport import (
    build_early_viewport_plan, select_pre_measurement_deferred_flows,
)
from psx.layout.grid.grid_geometry_reuse import AcceptedGridGeometryReuse
from psx.layout.grid.grid_native_composition import prepare_composed_grid
from psx.layout.projection.native_layout_snapshot import path_identity


def viewport(width, height=100):
    return LayoutConstraints(
        AvailableSize(width, True), AvailableSize(height, True)
    )


def board(count=96):
    cards = "".join(
        f'<GridItem span="3" key="card-{i}">'
        f'<div><div>Card {i}</div><div>Value {i * 17}</div></div>'
        '</GridItem>' for i in range(count)
    )
    tree = normalize_flex_tree(psx(f'<div><Grid gap="16px">{cards}</Grid></div>'))
    root = tree._participating_roots()[0]
    assert len(root.effective_children) == 1
    grid = root.effective_children[0]
    assert grid.type == "Grid"
    return tree, grid


def compose(grid, width, gen, *, deferred=None):
    reads = []
    def measure(identifier, node, available):
        reads.append((identifier, available))
        return IntrinsicSizes(5, available, 10, 20, available, 20)
    composition = prepare_composed_grid(
        grid, content_width=width, generation=gen,
        current_generation=gen, measure_leaf=measure,
        is_ui_thread=lambda: True, engine=PythonLayoutEngine(),
        viewport_constraints=viewport(width),
        deferred_flows=deferred,
    )
    return composition, reads


def test_early_p2_defers_upstream_native_measurement_but_preserves_visible_rows():
    normalized, grid = board()
    first, first_reads = compose(grid, 480, 1)
    assert first_reads and len(first.nested_flow) == 96
    # The workset carries physically committed, previously read-back native
    # Y positions. Its real plan/accept lifecycle is separately certified.
    receipts = {
        item.node_id: SimpleNamespace(epoch=4, native_y=item.y)
        for item in first.prepared.placements
    }
    workset = SimpleNamespace(_accepted=receipts)
    plan = build_early_viewport_plan(normalized, grid)
    assert plan is not None
    deferred = select_pre_measurement_deferred_flows(
        normalized, grid, first, workset, viewport_height=100,
        epoch=4, static_plan=plan,
    )
    assert 0 < len(deferred) < 96
    changed, sparse_reads = compose(grid, 560, 2, deferred=deferred)
    exact, exact_reads = compose(grid, 560, 2)
    assert len(sparse_reads) < len(exact_reads)
    assert changed.provisional_ids == frozenset(deferred)
    full = {p.node_id: p for p in exact.prepared.placements}
    for item in changed.prepared.placements:
        if item.node_id not in deferred:
            assert item == full[item.node_id]
    assert changed.prepared.generation == 2
    # Never promote provisional heights into a full accepted cache.
    cache = AcceptedGridGeometryReuse()
    cache.begin(normalized, 4, "qt", 1.0, {})
    key = path_identity(grid.path)
    cache.stage(key, grid, 560, viewport(560), changed)
    cache.accept()
    assert cache.lookup(key, grid, 560, viewport(560), 3) is None
    assert not exact.provisional_ids


def test_early_p2_refuses_invalidation_and_unproven_previous_position():
    normalized, grid = board(60)
    first, _ = compose(grid, 480, 1)
    plan = build_early_viewport_plan(normalized, grid)
    assert plan is not None
    receipts = {
        item.node_id: SimpleNamespace(epoch=7, native_y=item.y)
        for item in first.prepared.placements
    }
    workset = SimpleNamespace(_accepted=receipts)
    select = lambda **kw: select_pre_measurement_deferred_flows(
        normalized, grid, first, workset, viewport_height=100,
        static_plan=plan, **kw,
    )
    assert select(epoch=7)
    assert select(epoch=8) == {}
    # Newly exposed items at old/native Y cannot be classified P2.
    for receipt in receipts.values():
        receipt.native_y = 0
    assert select(epoch=7) == {}
    assert select(epoch=7, overscan=5000) == {}


def test_interactive_and_responsive_grids_are_never_provisionally_skipped():
    tree, grid = board(24)
    from psx import Grid, GridItem, Button
    from psx.core.layout_tree import normalize_flex_tree
    responsive = normalize_flex_tree(
        Grid(GridItem(Button("Update"), span={"base":12, "md":6}))
    )
    assert build_early_viewport_plan(responsive, responsive) is None
    # A single small viewport cannot prove any row below the screen using
    # 96px overscan when only six zero-height rows are available.
    first, _ = compose(grid, 480, 1)
    receipts = {
        item.node_id: SimpleNamespace(epoch=4, native_y=item.y)
        for item in first.prepared.placements
    }
    deferred = select_pre_measurement_deferred_flows(
        tree, grid, first, SimpleNamespace(_accepted=receipts),
        viewport_height=650, epoch=4,
    )
    assert not deferred
