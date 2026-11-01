"""Rust-only Cinnamon acceptance: run after fallback directory is removed.

This test is intentionally executable only when the real _sfle_native wheel
is installed. It is a hard dependency audit, not a mock import exercise.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def test_legacy_sfle_directory_has_been_removed():
    import psx
    assert not (Path(psx.__file__).parent / "sfle").exists()


def test_rust_does_not_import_python_solver_during_loading_or_layout():
    import _sfle_native
    assert callable(_sfle_native.compute_json)
    from psx.layout.engine.backend import RustLayoutEngine, load_layout_engine
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
    )
    engine = load_layout_engine()
    assert isinstance(engine, RustLayoutEngine)
    assert engine.backend_name == "rust"
    assert not [x for x in sys.modules if x.startswith("psx.layout.fallback")]

    snapshot = LayoutInput(
        1, 12, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(100, True), AvailableSize(60, True)),
        (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", 100.0), ("height", 60.0),
            )),
            LayoutNode("child", "root", "Box", (
                ("width", 20.0), ("height", 20.0),
                ("min_width", 0.0),
            )),
        ),
        (),
    )
    result = engine.compute(snapshot)
    assert dict(result.boxes)["child"].border.width == 20
    assert not [x for x in sys.modules if x.startswith("psx.layout.fallback")]


def test_rust_only_markup_css_and_renderer_imports():
    modules = (
        "psx",
        "psx.markup.html_aliases",
        "psx.core.layout_tree",
        "psx.css.geometry",
        "psx.renderers.headless",
        "psx.renderers.qt.pyqt",
        "psx.renderers.tkinter.tkinter",
        "psx.renderers.kivy.kivy",
    )
    for module in modules:
        importlib.import_module(module)
    assert not [x for x in sys.modules if x.startswith("psx.layout.fallback")]


def test_rust_only_actual_headless_flex_commit():
    from psx import Flex, Text
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, IntrinsicSizes,
    )
    # The HEADLESS toolkit is responsible for supplying real/host-known
    # intrinsic metrics. Rust is responsible for computing used geometry.
    def intrinsic(node):
        if node.type == "Text":
            return IntrinsicSizes(140, 140, 20, 20, 140, 20, baseline=15)
        return None
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(400, True), AvailableSize(300, True),
        ),
        measure_intrinsic=intrinsic,
    )
    root = Reconciler(renderer).render(
        Flex(Text("Hello, Rust only"), direction="row", width=320, height=50)
    )
    assert renderer.sfle_result is not None
    assert root is not None
    assert not [x for x in sys.modules if x.startswith("psx.layout.fallback")]


def test_rust_only_measured_block_and_inline_flow():
    """Independent Rust Block/Inline layout, no fallback import or geometry shim."""
    from psx.layout.engine.backend import load_layout_engine
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, IntrinsicSizes, LayoutInput,
        LayoutNode, MeasuredBox, WritingDirection,
    )
    constraints = LayoutConstraints(AvailableSize(240, True), AvailableSize(400, True))
    measurements = (
        MeasuredBox("button", IntrinsicSizes(40, 40, 12, 12, 40, 12),
                    constraints, 1),
        MeasuredBox("text", IntrinsicSizes(100, 100, 30, 30, 100, 30),
                    constraints, 1),
    )
    engine = load_layout_engine()
    block = LayoutInput(
        1, 7, WritingDirection.LTR, constraints,
        (
            LayoutNode("root", None, "div", ()),
            LayoutNode("button", "root", "Button", ()),
            LayoutNode("text", "root", "Text", ()),
        ),
        measurements,
    )
    boxes = dict(engine.compute(block).boxes)
    assert boxes["root"].border.height == 42
    assert boxes["button"].border.width == 40
    assert boxes["text"].border.y == 12
    assert boxes["text"].border.height == 30

    inline = LayoutInput(
        1, 8, WritingDirection.LTR, constraints,
        (
            LayoutNode("root", None, "div", (("display", "inline"),)),
            LayoutNode("button", "root", "Button", ()),
            LayoutNode("text", "root", "Text", ()),
        ),
        measurements,
    )
    rects = dict(engine.compute(inline).boxes)
    assert rects["button"].border.x == 0
    assert rects["text"].border.x == 40
    assert rects["text"].border.y == 0
    assert not [key for key in sys.modules if key.startswith("psx.layout.fallback")]


def test_rust_only_grid_math_uses_real_pyo3_kernel():
    from psx.layout.grid.contracts import GridSlot
    from psx.layout.grid.solver import compute_grid, grid_widths
    slots = (GridSlot("a", 6), GridSlot("b", 6))
    allocation = grid_widths(slots, 800, 4)
    assert allocation == {"a": 398.0, "b": 398.0}
    rows = compute_grid(slots, 800, 4, 5, {"a": 15, "b": 30})
    assert len(rows) == 1
    left, right = rows[0]
    assert left.x_raw == 0
    assert left.width_raw == 398 * 64
    assert right.x_raw == 402 * 64
    assert right.height_raw == 30 * 64
    assert not [key for key in sys.modules if key.startswith("psx.layout.fallback")]


def test_rust_only_headless_grid_reconciliation_and_resize():
    from psx import Grid, GridItem, Text
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.layout.contracts.model import AvailableSize, LayoutConstraints, IntrinsicSizes

    def viewport(width):
        return LayoutConstraints(AvailableSize(width, True),
                                 AvailableSize(100, True))

    def measure(node, allocated_width):
        assert node.type == "Text"
        height = 30 if allocated_width < 390 else 10
        return IntrinsicSizes(0, allocated_width, 0, height,
                              allocated_width, height)

    renderer = HeadlessRenderer(sfle_constraints=viewport(800),
                                measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    tree = Grid(
        GridItem(Text("a", key="leaf"), span={"base": 12, "md": 6}, key="a"),
        GridItem(Text("b", key="leaf"), span={"base": 12, "md": 6}, key="b"),
        gap=4,
    )
    try:
        root = reconciler.render(tree)
        assert root.children[0].handle.geometry.width == 398
        assert root.children[1].handle.geometry.x == 402
        renderer.set_sfle_constraints(viewport(767))
        renderer.commit_layout(root)
        assert root.children[0].handle.geometry.width == 767
        assert root.children[1].handle.geometry.y == 14
        assert renderer.grid_result[1].max_readback_error == 0
        assert not [key for key in sys.modules
                    if key.startswith("psx.layout.fallback")]
    finally:
        reconciler.unmount()


def _rust_only_grid_renderer(width=800):
    from psx.renderers.headless import HeadlessRenderer
    from psx.layout.contracts.model import IntrinsicSizes, AvailableSize, LayoutConstraints

    def measure(node, allocated_width=None):
        if node.type == "Text":
            width = 20 if allocated_width is None else allocated_width
            height = 30 if width < 390 else 10
            return IntrinsicSizes(0, width, 0, height, width, height)
        # The toolkit may request a content-independent initial hint for
        # Scroll or other containers. Their *used* geometry comes from Rust.
        return IntrinsicSizes(0, 0, 0, 0, 0, 0)
    return HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(width, True), AvailableSize(100, True),
        ),
        measure_intrinsic=measure,
    )


def test_rust_only_nested_grid_keeps_content_breakpoints_and_widget_identity():
    from psx import Grid, GridItem, Text
    from psx.core.reconcile import Reconciler
    from psx.layout.contracts.model import LayoutConstraints, AvailableSize
    renderer = _rust_only_grid_renderer()
    reconciler = Reconciler(renderer)
    nested = Grid(
        GridItem(
            Grid(
                GridItem(Text("nested a"), key="a", span={"base": 12, "md": 6}),
                GridItem(Text("nested b"), key="b", span={"base": 12, "md": 6}),
                gap=4,
            ),
            key="nested", span={"base": 12, "md": 6},
        ),
        GridItem(Text("outer"), key="outer", span={"base": 12, "md": 6}),
        gap=4,
    )
    try:
        root = reconciler.render(nested)
        subgrid = root.children[0].children[0]
        first = subgrid.children[0].handle
        second = subgrid.children[1].handle
        assert first.geometry.width == 398
        renderer.set_sfle_constraints(
            LayoutConstraints(AvailableSize(1600, True), AvailableSize(100, True))
        )
        renderer.commit_layout(root)
        assert first.geometry.width == 397
        assert second.geometry.width == 397
        assert subgrid.children[0].handle is first
        assert renderer.grid_result[1].max_readback_error == 0
        assert not [k for k in sys.modules if k.startswith("psx.layout.fallback")]
    finally:
        reconciler.unmount()


def test_rust_only_mixed_flex_grid_allocates_width_without_python_math():
    from psx import Flex, Grid, GridItem, Text
    from psx.core.reconcile import Reconciler
    from psx.layout.contracts.model import LayoutConstraints, AvailableSize
    renderer = _rust_only_grid_renderer()
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(Flex(
            Grid(
                GridItem(Text("left"), key="left", span={"base": 12, "md": 6}),
                GridItem(Text("right"), key="right", span={"base": 12, "md": 6}),
                gap=4,
            ),
            direction="column", width="100%", height=100,
        ))
        grid = root.children[0]
        first = grid.children[0].handle
        leaf = grid.children[0].children[0].handle
        assert grid.handle.geometry.width == 800
        assert first.geometry.width == 398
        renderer.set_sfle_constraints(
            LayoutConstraints(AvailableSize(767, True), AvailableSize(100, True))
        )
        renderer.commit_layout(root)
        assert grid.handle.geometry.width == 767
        assert first.geometry.width == 767
        assert grid.children[0].handle is first
        assert grid.children[0].children[0].handle is leaf
        assert not [k for k in sys.modules if k.startswith("psx.layout.fallback")]
    finally:
        reconciler.unmount()


def test_rust_only_grid_inside_scroll_flex_preserves_identity():
    from psx import Flex, Grid, GridItem, Text, Scroll
    from psx.core.reconcile import Reconciler
    renderer = _rust_only_grid_renderer()
    reconciler = Reconciler(renderer)

    def tree():
        return Grid(
            GridItem(Text("a"), span={"base": 12, "md": 6}, key="a"),
            GridItem(Text("b"), span={"base": 12, "md": 6}, key="b"),
            gap=4,
        )

    def scene(width):
        return Flex(
            Scroll(
                Flex(tree(), direction="column", width=width, height="240px",
                     key="content", align_items="stretch"),
                key="viewport", direction="both",
                layout_width="120px", layout_height="80px",
                flex_basis="120px", flex_shrink=0,
            ),
            direction="row", width="800px", height="100px",
            align_items="flex-start",
        )

    try:
        root = reconciler.render(scene("800px"))
        grid = root.children[0].children[0].children[0]
        original = grid.children[0].handle
        assert grid.handle.geometry.width == 800
        assert original.geometry.width == 398
        changed = reconciler.render(scene("600px"))
        grid = changed.children[0].children[0].children[0]
        assert grid.children[0].handle is original
        assert grid.handle.geometry.width == 600
        assert original.geometry.width == 600
        assert not [k for k in sys.modules if k.startswith("psx.layout.fallback")]
    finally:
        reconciler.unmount()

def test_rust_only_public_manifests_and_default_inline_dispatch():
    """Calling inline layout without an explicit engine must use the Rust ABI."""
    from psx.layout.engine.backend import RustLayoutEngine, load_layout_engine
    from psx.layout.inline.semantic_inline_text import (
        InlineTextSource, InlineTextMetrics, layout_inline_text,
    )
    engine = load_layout_engine()
    assert isinstance(engine, RustLayoutEngine)
    assert engine.capabilities.engine_name == "rust"
    assert engine.capabilities.status("block_flow_measured") == "certified"
    assert engine.capabilities.status("grid_12_columns") == "certified"
    assert engine.capabilities.status("inline_text_ltr_normal") == "certified"

    def metrics(_id, txt):
        return InlineTextMetrics(6.0 * len(txt), 14.0, 10.0)

    result = layout_inline_text(
        (InlineTextSource("source", "hello world"),),
        120.0, metrics,
    )
    assert result.line_count == 1
    assert [fragment.text for fragment in result.fragments if fragment.text.strip()] == [
        "hello", "world",
    ]
    assert not [module for module in sys.modules
                if module.startswith("psx.layout.fallback")]


def test_rust_only_public_contract_imports_do_not_load_fallback():
    import psx.layout as layout
    assert layout.LayoutEngine is not None
    assert layout.UnsupportedLayoutFeature is not None
    assert "LayoutEngine" in layout.__all__
    assert "UnsupportedLayoutFeature" in layout.__all__
    assert not [module for module in sys.modules
                if module.startswith("psx.layout.fallback")]

def test_all_shared_migration_modules_import_without_python_fallback():
    """Every migrated non-solver module must import with the fallback deleted."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    mapping = json.loads(
        (root / "scripts/layout_migration_manifest.json").read_text()
    )["sourceToTarget"]
    module_paths = sorted({
        target.removesuffix(".py").replace("/", ".")
        for target in mapping.values()
        if target.startswith("psx/layout/")
        and not target.startswith((
            "psx/layout/fallback/", "psx/layout/compat/",
        ))
        and not target.endswith("/__init__.py")
    })
    assert module_paths
    for name in module_paths:
        importlib.import_module(name)
    assert not [module for module in sys.modules
                if module.startswith("psx.layout.fallback")]

def test_rust_only_entire_public_numerical_contract_without_python():
    """Mandatory Rust mode: all common kernel operations run after removal."""
    from psx.layout.engine.backend import RustLayoutEngine, load_layout_engine
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
        WritingDirection,
    )
    from psx.layout.grid.contracts import GridSlot
    from psx.layout.inline.semantic_inline_text import (
        InlineTextMetrics, InlineTextSource,
    )
    engine = load_layout_engine()
    assert isinstance(engine, RustLayoutEngine)
    width = LayoutConstraints(AvailableSize(200, True),
                              AvailableSize(80, True))
    snapshot = LayoutInput(
        1, 21, WritingDirection.LTR, width, (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", "200px"), ("height", "80px"),
            )),
            LayoutNode("leaf", "root", "Box", (
                ("width", "40px"), ("height", "20px"),
            )),
        ), (),
    )
    computed = engine.compute(snapshot)
    assert engine.compute_provisional(snapshot).boxes == computed.boxes
    assert engine.compute_incremental(
        snapshot, previous_input=snapshot,
        previous_result=computed,
    ) == computed
    grid = engine.compute_grid(
        (GridSlot("a", 6), GridSlot("b", 6)),
        200.0, column_gap=4.0,
        item_heights={"a": 20.0, "b": 30.0},
    )
    assert grid[0][0].width_raw == 98 * 64
    inline = engine.layout_inline_text(
        (InlineTextSource("text", "abc def"),),
        100.0,
        lambda _node, text: InlineTextMetrics(8.0 * len(text), 16.0, 12.0),
    )
    assert inline.line_count == 1
    assert engine.capabilities.status("full_layout_compute") == "certified"
    assert engine.capabilities.status("incremental_layout_compute") == "certified"
    assert engine.capabilities.status("provisional_layout_compute") == "certified"
    assert not [name for name in sys.modules
                if name.startswith("psx.layout.fallback")]

def test_rust_only_incremental_reports_actual_reused_subtrees():
    """Rust's incremental receipt must originate in the native solver."""
    from dataclasses import replace
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput,
        LayoutNode, WritingDirection,
    )
    from psx.layout.engine.backend import load_layout_engine, RustLayoutEngine

    snapshot = LayoutInput(
        1, 41, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(300, True),
                          AvailableSize(100, True)),
        (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", "300px"), ("height", "100px"),
            )),
            LayoutNode("left", "root", "Flex", (
                ("width", "40px"), ("height", "25px"), ("flex_shrink", 0),
            )),
            LayoutNode("left_leaf", "left", "Flex", (
                ("width", "20px"), ("height", "10px"),
            )),
            LayoutNode("right", "root", "Flex", (
                ("width", "50px"), ("height", "25px"), ("flex_shrink", 0),
            )),
            LayoutNode("right_leaf", "right", "Flex", (
                ("width", "20px"), ("height", "10px"),
            )),
        ), (),
    )
    engine = load_layout_engine()
    assert isinstance(engine, RustLayoutEngine)
    before = engine.compute(snapshot)
    nodes = list(snapshot.nodes)
    nodes[1] = replace(nodes[1], style=(
        ("width", "60px"), ("height", "25px"), ("flex_shrink", 0),
    ))
    changed = replace(snapshot, generation=42, nodes=tuple(nodes))
    reused = []
    incremental = engine.compute_incremental(
        changed, previous_input=snapshot,
        previous_result=before, reused_contexts=reused,
    )
    assert incremental == engine.compute(changed)
    assert "right" in reused, reused
    assert not [name for name in sys.modules
                if name.startswith("psx.layout.fallback")]

def test_rust_only_legacy_measured_flow_dispatch_uses_real_native_kernel():
    """The historical projection entry point is usable without fallback."""
    from psx.layout.contracts.flow import BlockItem, InlineAtom
    from psx.layout.projection.display_context import (
        resolve_display, layout_measured_children,
    )
    from psx.layout.engine.backend import load_layout_engine
    engine = load_layout_engine()
    assert engine.capabilities.status("measured_flow_primitives") == "certified"
    children = (
        BlockItem(60, 20, margin_top=5),
        BlockItem(40, 10, margin_top=3),
    )
    block = layout_measured_children(
        resolve_display("div"), 200, children,
    )
    assert len(block) == 2
    assert block[0].y == 5
    assert block[1].y == 28
    atoms = (InlineAtom(70, 20, 15), InlineAtom(50, 10, 8))
    inline = layout_measured_children(
        resolve_display("span"), 100, atoms,
    )
    assert [(p.x, p.y) for p in inline] == [(0, 0), (0, 20)]
    assert not [name for name in sys.modules
                if name.startswith("psx.layout.fallback")]


def test_rust_only_historical_measurement_and_css_planning_without_fallback():
    """Former Python-only planners are usable after deleting fallback/."""
    from psx.layout.contracts.used_size import UsedSizeTree
    from psx.layout.runtime.remeasurement import plan_remeasurement
    from psx.layout.runtime.constraint_propagation import (
        ChildSizing, plan_styled_measurements, resolve_child_constraints,
    )
    from psx.layout.projection.size_resolution import (
        ResolutionKind, SizeProperty, resolve_length,
    )
    from psx.layout.contracts.lengths import Length
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
        WritingDirection,
    )
    constraints = LayoutConstraints(
        AvailableSize(240, True), AvailableSize(100, True),
    )
    root = LayoutNode("root", None, "Flex", ())
    child = LayoutNode("child", "root", "Text", ())
    snapshot = LayoutInput(
        1, 9, WritingDirection.LTR, constraints, (root, child), (),
    )
    css = ChildSizing(Length.percent(0.5), Length.px(20))
    child_resolved = resolve_child_constraints(constraints, css)
    assert child_resolved.width_kind == ResolutionKind.USED
    assert child_resolved.constraints.width.value == 120
    assert resolve_length(
        Length.percent(0.5), SizeProperty.WIDTH,
        containing_inline_size=constraints.width,
        containing_block_axis_size=constraints.width,
        flex_container_main_size=constraints.width,
    ).require_used() == 120

    plan = plan_styled_measurements(
        snapshot, parent_content=(("root", constraints),),
        child_sizing=(("child", css),),
    )
    assert tuple(req.node_id for req in plan.requests) == ("child", "root")
    used_before = UsedSizeTree(8, (
        ("root", constraints),
        ("child", LayoutConstraints(AvailableSize(120, True),
                                    AvailableSize(20, True))),
    ), ())
    used_after = UsedSizeTree(9, (
        ("root", constraints),
        ("child", LayoutConstraints(AvailableSize(100, True),
                                    AvailableSize(20, True))),
    ), ())
    delta = plan_remeasurement(snapshot, used_before, used_after)
    assert delta.changed == ("child",)
    assert delta.remeasure == ("child", "root")
    assert delta.deferred == ()
    assert not [name for name in sys.modules
                if name.startswith("psx.layout.fallback")]


def test_rust_only_historical_used_size_tree_propagates_percentages():
    """The removed Python engine must not be required to resolve CSS sizes."""
    from psx.layout.projection.used_size_tree import (
        NodeUsedSizing, propagate_definite_used_sizes,
    )
    from psx.layout.projection.box_sizing import BoxSizing
    from psx.layout.runtime.constraint_propagation import ChildSizing
    from psx.layout.contracts.used_size import UsedSizeTree
    from psx.layout.contracts.lengths import Length
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
        WritingDirection,
    )

    def constraints(width, height):
        return LayoutConstraints(
            AvailableSize(width, width is not None),
            AvailableSize(height, height is not None),
        )

    snapshot = LayoutInput(
        1, 12, WritingDirection.LTR, constraints(300, 90),
        (
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("child", "root", "Flex", ()),
            LayoutNode("leaf", "child", "Text", ()),
        ), (),
    )
    used = propagate_definite_used_sizes(
        snapshot, root_content=constraints(200, 80),
        children=(
            NodeUsedSizing(
                "child", ChildSizing(Length.percent(0.5), Length.percent(0.5)),
                BoxSizing.BORDER_BOX, 20, 20,
            ),
            NodeUsedSizing(
                "leaf", ChildSizing(Length.percent(0.5), Length.px(10)),
            ),
        ),
    )
    assert isinstance(used, UsedSizeTree)
    assert used.generation == 12
    assert dict(used.content)["child"] == constraints(80, 20)
    assert dict(used.content)["leaf"] == constraints(40, 10)
    assert used.deferred == ()
    assert not [name for name in sys.modules
                if name.startswith("psx.layout.fallback")]

