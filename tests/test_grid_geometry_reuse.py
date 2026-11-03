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
