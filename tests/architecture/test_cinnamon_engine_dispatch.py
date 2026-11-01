"""Numerical API dependency direction: shared façades know only LayoutEngine.

These tests deliberately use an engine with *no* backend_name. They fail if
Grid, Inline, or recursive geometry selects an implementation by name, reaches
for a native module, or accidentally re-enters the shared façade.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from psx.layout.contracts.model import WritingDirection
from psx.layout.contracts.recursive_tree import MarginTreeNode
from psx.layout.engine.backend import RustLayoutEngine
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.contracts import GridPackingError, GridSlot
from psx.layout.grid.solver import compute_grid
from psx.layout.inline.semantic_inline_text import (
    InlineTextMetrics, InlineTextSource, layout_inline_text,
)
from psx.layout.runtime.recursive_geometry import compute_margin_tree


class ContractOnlyEngine:
    """Method shape alone, not backend identity, controls public delegation."""

    def __init__(self):
        self.calls = []
        self.result = object()

    def compute_grid(self, *args, **kwargs):
        self.calls.append(("grid", args, kwargs))
        return self.result

    def layout_inline_text(self, *args, **kwargs):
        self.calls.append(("inline", args, kwargs))
        return self.result

    def compute_recursive_tree(self, *args, **kwargs):
        self.calls.append(("recursive", args, kwargs))
        return self.result


def _measure(_node_id, text):
    return InlineTextMetrics(len(text) * 8.0, 16.0, 12.0)


def test_shared_facades_dispatch_by_method_not_backend_type_or_name():
    engine = ContractOnlyEngine()
    slots = (GridSlot("g", 6),)
    heights = {"g": 10}
    assert compute_grid(slots, 120, item_heights=heights, engine=engine) is engine.result

    sources = (InlineTextSource("text", "a b"),)
    assert layout_inline_text(sources, 140, _measure, engine=engine) is engine.result

    nodes = (MarginTreeNode("root", None, 120, 80),)
    assert compute_margin_tree(nodes, generation=5, engine=engine) is engine.result

    assert [call[0] for call in engine.calls] == ["grid", "inline", "recursive"]
    assert engine.calls[0][1] == (slots, 120, 0, 0, heights, None)
    assert engine.calls[0][2] == {"rtl": False}
    assert engine.calls[1][1] == (sources, 140, _measure)
    assert engine.calls[1][2] == {"text_align": "left"}
    assert engine.calls[2][1] == (nodes,)
    assert engine.calls[2][2] == {
        "generation": 5, "writing": WritingDirection.LTR,
        "auto_cross": (),
    }


def test_shared_facades_fail_closed_before_dispatch():
    engine = ContractOnlyEngine()
    with pytest.raises(GridPackingError):
        compute_grid((GridSlot("bad", 6),), 120, engine=engine)
    with pytest.raises(ValueError, match="Inline containing width"):
        layout_inline_text((InlineTextSource("x", "a"),), -1, _measure, engine=engine)
    with pytest.raises(ValueError, match="generation"):
        compute_margin_tree((MarginTreeNode("root", None, 1, 1),),
                            generation=-1, engine=engine)
    assert engine.calls == []


@pytest.mark.parametrize("api,args,kwargs", (
    (compute_grid, ((GridSlot("g", 6),), 120), {"item_heights": {"g": 2}}),
    (layout_inline_text, ((InlineTextSource("x", "abc"),), 100, _measure), {}),
    (compute_margin_tree, ((MarginTreeNode("root", None, 1, 1),),),
     {"generation": 1}),
))
def test_missing_numerical_method_is_an_error(api, args, kwargs):
    with pytest.raises(TypeError, match="requires an engine with"):
        api(*args, **kwargs, engine=object())


def test_concrete_engines_do_not_reenter_shared_dispatch(monkeypatch):
    """Both concrete engines call their own kernels, not the public façade."""
    import psx.layout.grid.solver as grid
    import psx.layout.inline.semantic_inline_text as inline
    import psx.layout.runtime.recursive_geometry as recursive

    def cannot_dispatch(*args, **kwargs):
        raise AssertionError("concrete engine re-entered shared dispatch")

    monkeypatch.setattr(grid, "compute_grid", cannot_dispatch)
    monkeypatch.setattr(inline, "layout_inline_text", cannot_dispatch)
    monkeypatch.setattr(recursive, "compute_margin_tree", cannot_dispatch)

    captured = []
    def fake_grid(payload):
        captured.append(("grid", json.loads(payload)))
        return "[]"

    def fake_inline(payload):
        captured.append(("inline", json.loads(payload)))
        return json.dumps({
            "fragments": [], "width": 0, "height": 0, "line_count": 0,
        })

    def fake_recursive(payload):
        captured.append(("recursive", json.loads(payload)))
        return json.dumps({"generation": 8, "boxes": []})

    rust = RustLayoutEngine(SimpleNamespace(
        compute_grid_json=fake_grid,
        compute_inline_text_json=fake_inline,
        compute_recursive_tree_json=fake_recursive,
    ))
    assert rust.compute_grid((GridSlot("g", 6),), 120, item_heights={"g": 10}) == ()
    assert rust.layout_inline_text(
        (InlineTextSource("text", "abc"),), 120, _measure,
    ).fragments == ()
    assert rust.compute_recursive_tree((), generation=8).boxes == ()
    assert [name for name, _ in captured] == ["grid", "inline", "recursive"]

    python = PythonLayoutEngine()
    assert len(python.compute_grid(
        (GridSlot("g", 6),), 120, item_heights={"g": 10},
    )) == 1
    assert python.layout_inline_text(
        (InlineTextSource("text", "abc"),), 120, _measure,
    ).fragments
    assert len(python.compute_recursive_tree(
        (MarginTreeNode("root", None, 120, 80),), generation=8,
    ).boxes) == 1


def test_shared_numerical_facades_have_no_implementation_import_or_backend_switch():
    base = Path(__file__).resolve().parents[2]
    paths = (
        "psx/layout/grid/solver.py",
        "psx/layout/inline/semantic_inline_text.py",
        "psx/layout/runtime/recursive_geometry.py",
    )
    for path in paths:
        tree = ast.parse((base / path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("psx.layout.fallback"), path
            if isinstance(node, ast.Import):
                assert not any(i.name.startswith("psx.layout.fallback")
                               for i in node.names), path
            if isinstance(node, ast.Attribute):
                assert node.attr != "backend_name", path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "psx.layout.fallback" not in node.value, path
                assert node.value != "backend_name", path
