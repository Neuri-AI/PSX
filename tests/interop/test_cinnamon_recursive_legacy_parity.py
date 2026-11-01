"""All three legacy recursive APIs must produce exact Rust/Python equivalence.

Uses the actual installed _sfle_native wheel and independent Python solver.
A missing native ABI is a failure, not a skip or an implicit Python fallback.
"""
from __future__ import annotations
import random
import pytest

from psx.layout.contracts.lengths import Length, LengthKind
from psx.layout.contracts.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
    IntrinsicSizes, MeasuredBox, WritingDirection,
)
from psx.layout.contracts.recursive_tree import (
    AutoCrossSize, FlexBasis, IntrinsicLeafStyle,
    MarginFlexItem, MarginTreeNode,
)
from psx.layout.runtime.constraint_propagation import ChildSizing
from psx.layout.runtime.recursive_geometry import compute_margin_tree
from psx.layout.runtime.recursive_measurement import measure_resolved_margin_tree
from psx.layout.runtime.recursive_pipeline import compute_recursive_pipeline
from psx.layout.runtime.native_lifecycle import NativeLayoutLifecycle, layout_and_commit
from psx.layout.runtime.native_measurement import NativeMeasurementPort
from psx.layout.engine.backend import RustLayoutEngine, load_layout_engine
from psx.layout.fallback.engine import PythonLayoutEngine


@pytest.fixture(scope="module")
def engines():
    rust = load_layout_engine()
    assert isinstance(rust, RustLayoutEngine)
    assert callable(getattr(rust._module, "compute_recursive_tree_json", None))
    assert rust.capabilities.status("recursive_resolved_flex") == "certified"
    assert PythonLayoutEngine().capabilities.status("recursive_resolved_flex") == "certified"
    return rust, PythonLayoutEngine()


def tree(child_width=20.0, *, nested=False):
    root = MarginTreeNode("root", None, 150, 80)
    child = MarginTreeNode(
        "child", "root", child_width, 18,
        MarginFlexItem("child", FlexBasis(child_width, child_width, grow=0, shrink=0), 18),
    )
    if not nested:
        return (root, child)
    leaf = MarginTreeNode(
        "leaf", "child", 10, 8,
        MarginFlexItem("leaf", FlexBasis(10, 10, grow=0, shrink=0), 8),
    )
    return (root, child, leaf)


def snapshot(nodes, generation=7):
    return LayoutInput(
        1, generation, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(150, True), AvailableSize(80, True)),
        tuple(LayoutNode(n.node_id, n.parent_id, "Flex", ()) for n in nodes),
        (),
    )


def port(receipts):
    def measure(req):
        receipts.append((req.node_id, req.constraints, req.revision))
        width = req.constraints.width.value
        height = 12 if width is not None and width >= 100 else 24
        return MeasuredBox(
            req.node_id, IntrinsicSizes(20, 60, 8, height, 60, height),
            req.constraints, req.revision,
        )
    return NativeMeasurementPort(lambda: True, measure)


def sizing(nodes):
    return tuple((n.node_id, ChildSizing(Length.px(n.width), Length.px(n.height)))
                 for n in nodes[1:])


@pytest.mark.parametrize("nested", (False, True))
def test_measure_resolved_margin_tree_engine_equivalence(engines, nested):
    nodes = tree(nested=nested)
    input_ = snapshot(nodes)
    outs = []
    for engine in engines:
        calls = []
        result = measure_resolved_margin_tree(
            input_, nodes, child_sizing=sizing(nodes),
            port=port(calls), current_generation=7,
            engine=engine,
        )
        outs.append((result, calls))
    assert outs[0] == outs[1]


@pytest.mark.parametrize("nested", (False, True))
def test_layout_and_commit_equivalence(engines, nested):
    nodes = tree(nested=nested)
    input_ = snapshot(nodes)
    outs = []
    for engine in engines:
        calls, committed = [], []
        lifecycle = NativeLayoutLifecycle(
            lambda: 7, port(calls), committed.append,
        )
        output = layout_and_commit(
            input_, nodes, lifecycle, child_sizing=sizing(nodes),
            engine=engine,
        )
        assert committed == [output]
        outs.append((output, calls))
    assert outs[0] == outs[1]


def test_intrinsic_growth_and_multiround_convergence_equivalence(engines):
    nodes = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("leaf", "root", 0, 0,
                       MarginFlexItem("leaf", FlexBasis(0, 0, grow=1, shrink=1), 0)),
    )
    input_ = snapshot(nodes)
    results = []
    for engine in engines:
        calls = []
        result = compute_recursive_pipeline(
            input_, nodes,
            child_sizing=(("leaf", ChildSizing(Length(LengthKind.AUTO),
                                              Length(LengthKind.AUTO))),),
            native_port=port(calls), current_generation=7,
            intrinsic_leaves=(IntrinsicLeafStyle("leaf", Length(LengthKind.AUTO)),),
            engine=engine,
        )
        assert result.deferred == ()
        assert result.geometry.boxes[1].content.width == 150
        results.append((result, calls))
    assert results[0] == results[1]


def test_auto_cross_sizing_and_commit_equivalence(engines):
    nodes = (
        MarginTreeNode("root", None, 150, 80),
        MarginTreeNode("container", "root", 20, 0,
            MarginFlexItem("container", FlexBasis(20, 20, grow=0, shrink=0), 0)),
        MarginTreeNode("leaf", "container", 20, 18,
            MarginFlexItem("leaf", FlexBasis(20, 20, grow=0, shrink=0), 18)),
    )
    input_ = snapshot(nodes)
    styles = (
        ("container", ChildSizing(Length.px(20), Length(LengthKind.AUTO))),
        ("leaf", ChildSizing(Length.px(20), Length.px(18))),
    )
    outputs = []
    for engine in engines:
        calls, commits = [], []
        lifecycle = NativeLayoutLifecycle(lambda: 7, port(calls), commits.append)
        result = layout_and_commit(
            input_, nodes, lifecycle, child_sizing=styles,
            auto_cross=(AutoCrossSize("container"),), engine=engine,
        )
        assert commits == [result]
        assert result.geometry.boxes[1].content.height == 18
        outputs.append((result, calls))
    assert outputs[0] == outputs[1]


def test_seeded_recursive_geometry_with_nested_flex_parity(engines):
    rng = random.Random(101619)
    for trial in range(120):
        child_width = rng.randint(1, 70)
        nodes = tree(child_width, nested=bool(trial % 2))
        native = compute_margin_tree(nodes, generation=trial, engine=engines[0])
        fallback = compute_margin_tree(nodes, generation=trial, engine=engines[1])
        assert native == fallback, (trial, nodes, native, fallback)


def test_default_recursive_backend_is_rust_and_does_not_import_fallback(engines):
    assert isinstance(load_layout_engine(), RustLayoutEngine)
    nodes = tree()
    expected = compute_margin_tree(nodes, generation=7, engine=engines[0])
    assert compute_margin_tree(nodes, generation=7) == expected
