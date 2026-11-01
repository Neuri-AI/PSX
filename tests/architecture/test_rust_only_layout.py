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
