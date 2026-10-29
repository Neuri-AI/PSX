"""Algorithmic regression: common native Flow/Grid operations must be linear.

These checks count real snapshot traversal work rather than measuring wall
time, which varies across GitHub CI operating systems and hardware.
"""
from __future__ import annotations

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.grid_native_composition import (
    _FlowContainingWidths, nested_flow_grid_width,
)
from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _node(name, parent, component, **style):
    return LayoutNode(name, parent, component, tuple(sorted(style.items())))


def _request(nodes, measurements=(), width=720):
    viewport = LayoutConstraints(AvailableSize(width, True), AvailableSize(650, True))
    return LayoutInput(
        1, 1, WritingDirection.LTR, viewport, nodes, tuple(measurements),
    )


def test_sibling_flex_subtrees_do_not_rescan_every_flow_node():
    class CountedNodes(tuple):
        visits = 0

        def __iter__(self):
            self.visits += len(self)
            return super().__iter__()

    n = 120
    nodes = [_node("root", None, "div", display="block")]
    measures = []
    constraints = LayoutConstraints(
        AvailableSize(720, True), AvailableSize(None, False))
    for i in range(n):
        flex = f"flex-{i}"
        leaf = f"leaf-{i}"
        nodes.extend((
            _node(flex, "root", "Flex", direction="column"),
            _node(leaf, flex, "Text"),
        ))
        measures.append(MeasuredBox(
            leaf, IntrinsicSizes(12, 40, 15, 16, 40, 16),
            constraints, 1,
        ))
    counted = CountedNodes(nodes)
    request = _request(counted, measures)
    counted.visits = 0
    output = dict(compute_measured_block_snapshot(
        request, flex_engine=PythonLayoutEngine(),
    ).boxes)
    assert len(output) == 2 * n + 1
    assert output["leaf-0"].content.height > 0
    assert output[f"leaf-{n-1}"].content.y > output["leaf-0"].content.y
    # The former flex_node scanned all 2*N+1 snapshot nodes once for
    # each of N sibling Flexes: quadratic. Only a bounded number of
    # complete snapshot passes is allowed.
    assert counted.visits <= 12 * len(counted)


def test_nested_grid_parent_widths_are_memoized_across_many_siblings(monkeypatch):
    from psx.sfle import lengths

    depth = 100
    siblings = 90
    nodes = [_node("root", None, "div", layout_padding_left="2px")]
    parent = "root"
    for i in range(depth):
        node_id = f"layer-{i}"
        nodes.append(_node(
            node_id, parent, "div", layout_padding_left="2px",
        ))
        parent = node_id
    for i in range(siblings):
        nodes.append(_node(f"grid-{i}", parent, "Grid"))
    snapshot = _request(tuple(nodes), width=600)
    resolver = _FlowContainingWidths(snapshot, 600)
    original = lengths.parse_length
    calls = []

    def counted(value):
        calls.append(value)
        return original(value)

    with monkeypatch.context() as patch:
        patch.setattr(lengths, "parse_length", counted)
        output = [
            resolver.resolve(f"grid-{i}") for i in range(siblings)
        ]

    assert all(value == 600 - (depth + 1) * 2 for value in output)
    assert len(calls) == depth + 1
    assert nested_flow_grid_width(snapshot, "grid-80", 600) == output[80]


def test_memoized_grid_width_preserves_css_percentages_and_auto_branch():
    nodes = (
        _node("root", None, "div", layout_width="50%",
              layout_padding_left="60px"),
        _node("parent", "root", "div", layout_padding_left="10%",
              layout_padding_right="20px"),
        _node("grid-a", "parent", "Grid"),
        _node("middle", "parent", "div", layout_width="auto",
              layout_padding_left="99px"),
        _node("grid-b", "middle", "Grid"),
    )
    snapshot = _request(nodes, width=600)
    resolver = _FlowContainingWidths(snapshot, 600)
    # Root explicit 50% skips its padding. Parent uses containing 300.
    assert resolver.resolve("grid-a") == 250
    # An explicit 'auto' similarly skips its own edge branch.
    assert resolver.resolve("grid-b") == 250
    for node_id in ("grid-a", "grid-b"):
        assert nested_flow_grid_width(snapshot, node_id, 600) == resolver.resolve(node_id)


def test_nonpreorder_flow_input_retains_layout_order_fallback():
    constraints = LayoutConstraints(
        AvailableSize(200, True), AvailableSize(120, True))
    root = _node("root", None, "div", display="block")
    flex_a = _node("a", "root", "Flex", direction="column")
    flex_b = _node("b", "root", "Flex", direction="column")
    leaf_a = _node("a-leaf", "a", "Text")
    leaf_b = _node("b-leaf", "b", "Text")
    measures = tuple(MeasuredBox(
        leaf.node_id, IntrinsicSizes(10, 20, 10, 10, 20, 10),
        constraints, 1,
    ) for leaf in (leaf_a, leaf_b))
    ordered = _request((root, flex_a, leaf_a, flex_b, leaf_b), measures, 200)
    interleaved = _request((root, flex_a, flex_b, leaf_a, leaf_b), measures, 200)
    expected = dict(compute_measured_block_snapshot(
        ordered, flex_engine=PythonLayoutEngine(),
    ).boxes)
    actual = dict(compute_measured_block_snapshot(
        interleaved, flex_engine=PythonLayoutEngine(),
    ).boxes)
    assert expected == actual
