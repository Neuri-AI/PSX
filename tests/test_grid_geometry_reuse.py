"""Exact before-measurement Grid cache: lifecycle, generations and safety."""
from dataclasses import replace

from psx import Button, Grid, GridItem, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.layout.contracts.model import AvailableSize, IntrinsicSizes, LayoutConstraints
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.grid_geometry_reuse import AcceptedGridGeometryReuse
from psx.layout.grid.grid_native_composition import prepare_composed_grid
from psx.layout.projection.native_layout_snapshot import path_identity


def viewport(width=480, height=650):
    return LayoutConstraints(
        AvailableSize(width, True), AvailableSize(height, True),
    )


def original_grid(n=24):
    return normalize_flex_tree(
        Grid(*(GridItem(Text(f"Card {i}"), span=3, key=f"card-{i}")
               for i in range(n)), gap="16px")
    )


def calculate(grid, *, width=480, generation=1):
    calls = []
    def leaf(identifier, node, available):
        calls.append((identifier, available))
        return IntrinsicSizes(20, available, 16, 20, available, 20)
    result = prepare_composed_grid(
        grid, content_width=width, generation=generation,
        current_generation=generation, measure_leaf=leaf,
        is_ui_thread=lambda: True, engine=PythonLayoutEngine(),
        viewport_constraints=viewport(width),
    )
    assert len(calls) == len(grid.effective_children)
    return result


def test_certified_exact_layout_skips_measurement_and_renews_every_receipt():
    grid = original_grid()
    cache = AcceptedGridGeometryReuse(limit=3)
    key = path_identity(grid.path)
    initial = calculate(grid, generation=1)
    cache.begin(grid, 5, "qt", 1.0, {})
    assert cache.lookup(key, grid, 480, viewport(), 2) is None
    cache.stage(key, grid, 480, viewport(), initial)
    # Failed transactions must never publish a speculative layout.
    cache.discard()
    assert cache.lookup(key, grid, 480, viewport(), 2) is None
    cache.stage(key, grid, 480, viewport(), initial)
    cache.accept()
    before = initial.prepared.placements
    after = cache.lookup(key, grid, 480, viewport(), 18)
    assert after is not None
    assert after.prepared.generation == 18
    assert all(revision == 18 for _, revision in
               after.prepared.measurement_revisions)
    assert after.prepared.placements == before
    assert cache.hits == 1
    assert cache.lookup(key, grid, 481, viewport(481), 18) is None
    assert cache.lookup(key, grid, 480, viewport(480, 651), 18) is None


def test_no_cross_epoch_backend_retina_breakpoint_or_tree_identity():
    grid = original_grid(12)
    key = path_identity(grid.path)
    cache = AcceptedGridGeometryReuse()
    result = calculate(grid)
    cache.begin(grid, 1, "qt", 1.0, {})
    cache.stage(key, grid, 480, viewport(), result)
    cache.accept()
    assert cache.lookup(key, grid, 480, viewport(), 2) is not None
    for root, epoch, backend, scale, bp in (
        (grid, 2, "qt", 1.0, {}),
        (grid, 1, "tk", 1.0, {}),
        (grid, 1, "qt", 2.0, {}),
        (grid, 1, "qt", 1.0, {"md": 720}),
        (original_grid(12), 1, "qt", 1.0, {}),
    ):
        cache.begin(root, epoch, backend, scale, bp)
        assert cache.lookup(key, root, 480, viewport(), 3) is None
        cache.begin(grid, 1, "qt", 1.0, {})
        cache.stage(key, grid, 480, viewport(), result)
        cache.accept()


def test_interactive_control_is_never_memoized_as_immutable_geometry():
    grid = normalize_flex_tree(Grid(GridItem(Button("Submit"), span=12)))
    cache = AcceptedGridGeometryReuse()
    cache.begin(grid, 1, "qt", 1.0, {})
    key = path_identity(grid.path)
    assert not cache.eligible(key, grid)
    assert cache.lookup(key, grid, 480, viewport(), 1) is None


def test_lru_is_bounded_across_responsive_widths():
    grid = original_grid(12)
    key = path_identity(grid.path)
    cache = AcceptedGridGeometryReuse(limit=2)
    cache.begin(grid, 1, "qt", 1.0, {})
    for width in (480, 560, 640):
        cache.stage(key, grid, width, viewport(width),
                    calculate(grid, width=width))
        cache.accept()
    assert cache.lookup(key, grid, 480, viewport(480), 4) is None
    assert cache.lookup(key, grid, 560, viewport(560), 4) is not None
    assert cache.lookup(key, grid, 640, viewport(640), 4) is not None


def test_shared_width_pattern_preserves_partial_final_row_allocations():
    from psx.core.grid_contract import GRID_BREAKPOINTS
    from psx.layout.grid.grid_native_measurement import GridStructureReuse, measure_grid_native
    from psx.layout.runtime.native_measurement import NativeMeasurementPort

    for count in (1, 3, 5, 7, 9):
        grid = original_grid(count)
        structure = GridStructureReuse().prepare(grid, 700, GRID_BREAKPOINTS, 1)

        class Source:
            def __init__(self):
                self.reads = []

            def port(self):
                return NativeMeasurementPort(lambda: True, lambda request: None)

            def measure_width(self, identifier, width):
                self.reads.append((identifier, width))
                return IntrinsicSizes(0, width, 0, 20, width, 20)

        native, full = Source(), Source()
        args = dict(grid=grid, content_width=700, mounted_ids=structure.ids,
                    revisions={key: 1 for key in structure.ids}, generation=1,
                    current_generation=1, engine=PythonLayoutEngine())
        sparse = measure_grid_native(**args, source=native, structure=structure)
        exact = measure_grid_native(**args, source=full)
        assert native.reads == full.reads
        assert sparse.placements == exact.placements


def test_flattened_grid_batch_has_live_widget_identity_fence():
    from types import SimpleNamespace
    from psx.layout.grid.grid_native_plan import GridNativePlacement

    grid = original_grid(12)
    key = path_identity(grid.path)
    cache = AcceptedGridGeometryReuse()
    cache.begin(grid, 1, "qt", 1.0, {})
    first = object()
    second = object()
    handles = {
        101: SimpleNamespace(widget=first),
        102: SimpleNamespace(widget=second),
    }
    placements = (
        GridNativePlacement("card-a", 1, 2, 100, 30, 100, 30, False, False),
        GridNativePlacement("card-b", 1, 40, 100, 30, 100, 30, False, False),
    )
    widgets = {"card-a": first, "card-b": second}
    cache.batch_stage(key, grid, 480, viewport(), 650,
                      placements, widgets, {"card-a": 650, "card-b": 650},
                      handles)
    # A rollback cannot leave a valid geometry receipt.
    cache.discard()
    assert cache.batch_lookup(key, 480, viewport(), 650, handles) is None
    cache.batch_stage(key, grid, 480, viewport(), 650,
                      placements, widgets, {"card-a": 650, "card-b": 650},
                      handles)
    cache.accept()
    batch, rebound, heights = cache.batch_lookup(
        key, 480, viewport(), 650, handles,
    )
    assert batch is placements
    assert rebound == widgets
    assert heights["card-b"] == 650
    assert cache.batch_hits == 1
    # Replacing the mounted native handle without a matching structural
    # receipt must never return coordinates bound to the stale widget.
    handles[102] = SimpleNamespace(widget=object())
    assert cache.batch_lookup(key, 480, viewport(), 650, handles) is None


def test_renderer_unmount_clear_releases_saved_tree_and_receipts():
    grid = original_grid(8)
    key = path_identity(grid.path)
    cache = AcceptedGridGeometryReuse()
    cache.begin(grid, 1, "qt", 1.0, {})
    cache.stage(key, grid, 480, viewport(), calculate(grid))
    cache.accept()
    assert cache._root is grid and cache._entries
    cache.clear()
    assert cache._root is None
    assert not cache._entries and not cache._latest and not cache._batch_entries
    assert not cache._safety and not cache._early_plans
    assert cache.lookup(key, grid, 480, viewport(), 2) is None


def test_external_text_ref_is_not_certified_as_immutable_native_geometry():
    grid = normalize_flex_tree(
        Grid(GridItem(Text("Mutable through a ref", ref=object()), span=12))
    )
    cache = AcceptedGridGeometryReuse()
    cache.begin(grid, 1, "qt", 1.0, {})
    assert not cache.eligible(path_identity(grid.path), grid)

def test_last_accepted_grid_compositions_are_bounded_even_for_many_grids():
    grid = original_grid(4)
    cache = AcceptedGridGeometryReuse(limit=2)
    cache.begin(grid, 1, "qt", 1.0, {})
    composition = calculate(grid)
    for grid_id in ("first", "second", "third"):
        cache.stage(grid_id, grid, 480, viewport(), composition)
        cache.accept()
    assert len(cache._latest) == 2
    assert cache.latest("first") is None
    assert cache.latest("second") is composition
    assert cache.latest("third") is composition
