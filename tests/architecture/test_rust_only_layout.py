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
