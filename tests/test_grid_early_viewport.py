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


def test_unwrapped_native_receipts_recompute_current_width_rectangles():
    from psx.layout.grid.grid_early_viewport import select_wider_unwrapped_flows

    _normalized, grid = board(4)
    metrics = IntrinsicSizes(5, 20, 10, 20, 20, 20)

    def layout(width, generation, *, reusable=None, reject_native=False):
        def measure(*args):
            if reject_native:
                raise AssertionError("A certified intrinsic receipt was remeasured")
            return metrics
        return prepare_composed_grid(
            grid, content_width=width, generation=generation,
            current_generation=generation, measure_leaf=measure,
            is_ui_thread=lambda: True, engine=PythonLayoutEngine(),
            viewport_constraints=viewport(width), reusable_flows=reusable,
        )

    first = layout(480, 1)
    reusable = select_wider_unwrapped_flows(grid, first, content_width=560)
    assert len(reusable) == 4
    changed = layout(560, 2, reusable=reusable, reject_native=True)
    full = layout(560, 2)
    assert changed.prepared.placements == full.prepared.placements
    for node_id, flow in changed.nested_flow.items():
        assert flow.result.boxes == full.nested_flow[node_id].result.boxes
        root = flow.prepared.snapshot.nodes[0].node_id
        assert dict(flow.result.boxes)[root].border.width == 128


def test_exact_structural_receipts_cache_without_solving_offscreen_flow_details():
    from psx.layout.grid.grid_early_viewport import select_wider_unwrapped_flows

    normalized, grid = board(96)
    metrics = IntrinsicSizes(5, 20, 10, 20, 20, 20)

    def layout(width, generation, **kwargs):
        return prepare_composed_grid(
            grid, content_width=width, generation=generation,
            current_generation=generation, measure_leaf=lambda *args: metrics,
            is_ui_thread=lambda: True, engine=PythonLayoutEngine(),
            viewport_constraints=viewport(width), **kwargs,
        )

    first = layout(480, 1)
    workset = SimpleNamespace(_accepted={
        item.node_id: SimpleNamespace(epoch=7, native_y=item.y)
        for item in first.prepared.placements
    })
    static = build_early_viewport_plan(normalized, grid)
    deferred = select_pre_measurement_deferred_flows(
        normalized, grid, first, workset, viewport_height=100, epoch=7,
        static_plan=static, content_width=560,
    )
    reusable = select_wider_unwrapped_flows(
        grid, first, content_width=560, static_plan=static)
    assert deferred and len(reusable) == 96
    current = layout(560, 2, deferred_flows=deferred, reusable_flows=reusable)
    full = layout(560, 2)
    assert not current.provisional_ids
    assert current.native_deferred_flows == frozenset(deferred)
    assert current.prepared.placements == full.prepared.placements
    assert current.content_height == full.content_height
    for item_id in deferred:
        assert current.nested_flow[item_id] is first.nested_flow[item_id]
    cache = AcceptedGridGeometryReuse()
    cache.begin(normalized, 7, "qt", 1.0, {})
    key = path_identity(grid.path)
    cache.stage(key, grid, 560, viewport(560), current)
    cache.accept()
    hit = cache.lookup(key, grid, 560, viewport(560), 3)
    assert hit is not None and hit.native_deferred_flows == frozenset(deferred)
    # Exposure changes the viewport receipt; native promotion cannot reuse
    # a hidden detail layout merely because its outer width was seen before.
    assert cache.lookup(key, grid, 560, viewport(560, 4000), 3) is None


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

    # A viewport receipt can reuse only its already solved P0/P1, while
    # preserving the dirty P2 flag. It is never an exact structural cache hit.
    cache.early_plan(key, normalized, grid)
    cache.stage_viewport(key, grid, 560, viewport(560), changed)
    cache.discard()
    assert cache.lookup_viewport(key, 560, viewport(560), 3) is None
    cache.stage_viewport(key, grid, 560, viewport(560), changed)
    cache.accept()
    replay = cache.lookup_viewport(key, 560, viewport(560), 3)
    assert replay is not None
    assert replay.provisional_ids == changed.provisional_ids
    assert replay.prepared.generation == 3
    assert cache.lookup(key, grid, 560, viewport(560), 3) is None
    assert cache.lookup_viewport(key, 560, viewport(560, 200), 3) is None
    cache.begin(normalized, 5, "qt", 1.0, {})
    assert cache.lookup_viewport(key, 560, viewport(560), 3) is None


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


def test_narrower_certified_text_cards_use_prior_row_bounds_before_measurement():
    """A narrower normal-flow card cannot shrink and pull P2 rows onscreen."""
    normalized, grid = board(100)
    accepted, _ = compose(grid, 480, 1)
    workset = SimpleNamespace(_accepted={
        item.node_id: SimpleNamespace(epoch=3, native_y=item.y)
        for item in accepted.prepared.placements
    })
    plan = build_early_viewport_plan(normalized, grid)
    legacy = select_pre_measurement_deferred_flows(
        normalized, grid, accepted, workset, viewport_height=650,
        epoch=3, static_plan=plan,
    )
    narrowed = select_pre_measurement_deferred_flows(
        normalized, grid, accepted, workset, viewport_height=650,
        epoch=3, static_plan=plan, content_width=400,
    )
    assert len(narrowed) > len(legacy)
    assert narrowed


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

def test_500_card_native_leaf_reads_drop_by_more_than_half_before_solver():
    """Structural P1 rows preserve complete visible placement; the other
    hundreds of Flow cards do not need fresh native width probes at all.
    """
    normalized, grid = board(500)
    full_before, _ = compose(grid, 480, 1)
    workset = SimpleNamespace(_accepted={
        placement.node_id: SimpleNamespace(
            epoch=1, native_y=placement.y
        ) for placement in full_before.prepared.placements
    })
    plan = build_early_viewport_plan(normalized, grid)
    deferred = select_pre_measurement_deferred_flows(
        normalized, grid, full_before, workset,
        viewport_height=100, epoch=1, static_plan=plan,
    )
    assert len(deferred) > 250, (
        "Only the structural and visible prefix should have been measured"
    )
    sparse, sparse_reads = compose(grid, 560, 2, deferred=deferred)
    baseline, baseline_reads = compose(grid, 560, 2)
    assert len(sparse_reads) < len(baseline_reads) / 2
    assert sparse.provisional_ids == frozenset(deferred)
    exact = {placement.node_id: placement
             for placement in baseline.prepared.placements}
    for placement in sparse.prepared.placements:
        if placement.node_id not in deferred:
            assert placement == exact[placement.node_id]

def test_early_geometry_rejects_negative_and_unknown_css_margin_values():
    from psx.layout.grid.grid_early_viewport import _negative
    from psx.layout.contracts.lengths import Length
    assert not _negative(0)
    assert not _negative("12px")
    assert not _negative("3%")
    assert not _negative(("0px", "10px", "0px", "0px"))
    for value in ("-1px", "-12%", "calc(0px - 20px)", "auto",
                  "var(--gap)", float("nan"), Length.px(-4)):
        assert _negative(value), (
            f"Unknown or signed margin escaped the early viewport proof: {value!r}"
        )
