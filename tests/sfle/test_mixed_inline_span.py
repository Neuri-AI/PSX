"""Mixed inline text/span regression for all Cinnamon-backed native adapters.

The semantic Block/Inline compositor is shared by Qt, Tkinter and Kivy.
CSS Flex block roots use the same source nodes, but project mixed inline runs
to measured wrapping rows before invoking the selected Cinnamon engine.
"""
from __future__ import annotations

import pytest

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.native_layout_snapshot import (prepare_native_layout_snapshot, inline_atomic_text_ids)
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _constraints(width: int):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(280, True))


def _intrinsic(width: int):
    return IntrinsicSizes(width, width, 18, 18, width, 18, baseline=15)


@pytest.mark.parametrize("width", [600, 300, 140])
def test_css_flex_paragraph_treats_mixed_inline_nodes_as_wrapping_row(width):
    source = psx(
        '<div style="display:flex; flex-direction:column; align-items:center">'
        '<p>Edit <span style="color:red">src/App.tsx</span>'
        ' and save to test HMR</p></div>'
    )
    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(source), _constraints(width), generation=1,
    )
    snapshot = prepared.css_geometry_snapshot()
    by_source = {
        node.node_id: vnode for node_id, vnode in prepared.identities
        for node in snapshot.nodes if node.node_id == node_id
    }
    blocks = [
        node for node in snapshot.nodes
        if by_source[node.node_id].type == "p"
    ]
    assert len(blocks) == 1
    style = dict(blocks[0].style)
    assert blocks[0].component == "Flex"
    assert style["direction"] == "row"
    assert style["wrap"] == "wrap"
    assert style["align_self"] == "stretch"
    for node in snapshot.nodes:
        original = by_source[node.node_id]
        if original.type in ("span", "Text") and node.parent_id == blocks[0].node_id:
            assert dict(node.style)["flex_shrink"] == 0.0
    assert any(vnode.type == "span" for vnode in by_source.values())
    assert sum(1 for vnode in by_source.values() if vnode.type == "Text") >= 5
    atomic = inline_atomic_text_ids(prepared)
    assert any(by_source[identifier].type == "Text"
               and by_source[identifier].props["value"] == "src/App.tsx"
               for identifier in atomic)
    assert len(atomic) >= 5


def test_block_root_inline_span_stays_on_same_measured_line_when_it_fits():
    from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
    constraints = _constraints(400)
    nodes = (
        LayoutNode("root", None, "div", (("display", "block"),)),
        LayoutNode("p", "root", "p", (("display", "block"),)),
        LayoutNode("before", "p", "Text", ()),
        LayoutNode("span", "p", "span", (("display", "inline"),)),
        LayoutNode("inside", "span", "Text", ()),
        LayoutNode("after", "p", "Text", ()),
    )
    measurements = tuple(
        MeasuredBox(node_id, _intrinsic(px), constraints, 1)
        for node_id, px in (("before", 38), ("inside", 100), ("after", 155))
    )
    snapshot = LayoutInput(
        1, 1, WritingDirection.LTR, constraints, nodes, measurements,
    )
    boxes = dict(compute_measured_block_snapshot(snapshot).boxes)
    assert boxes["before"].content.y == boxes["inside"].content.y
    assert boxes["inside"].content.y == boxes["after"].content.y
    assert boxes["before"].content.x + 38 == boxes["inside"].content.x
    assert boxes["inside"].content.x + 100 == boxes["after"].content.x
    assert boxes["span"].content.width == boxes["inside"].content.width


def test_block_root_mixed_inline_wraps_at_available_width():
    from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
    constraints = _constraints(150)
    nodes = (
        LayoutNode("p", None, "p", (("display", "block"),)),
        LayoutNode("before", "p", "Text", ()),
        LayoutNode("span", "p", "span", (("display", "inline"),)),
        LayoutNode("inside", "span", "Text", ()),
        LayoutNode("after", "p", "Text", ()),
    )
    measurements = tuple(
        MeasuredBox(node_id, _intrinsic(px), constraints, 1)
        for node_id, px in (("before", 38), ("inside", 100), ("after", 155))
    )
    snapshot = LayoutInput(1, 1, WritingDirection.LTR, constraints, nodes, measurements)
    boxes = dict(compute_measured_block_snapshot(snapshot).boxes)
    assert boxes["before"].content.y == boxes["inside"].content.y
    assert boxes["after"].content.y >= boxes["inside"].content.y + 18
    assert boxes["p"].border.height >= 36

def test_expressive_psx_callback_and_inline_span_keep_sentence_continuous():
    from psx.markup.transform import transform_source
    authored = '''
from psx import psx

def render(count, set_count):
    return psx("""<div style="display:flex;flex-direction:column">
        <p>Edit <span>src/App.tsx</span> and save to test HMR</p>
        <button on_click={() => set_count(count + 1)}>Count is {count}</button>
    </div>""")
'''
    transformed = transform_source(authored, filename="app.py")
    namespace = {"__name__": "inline_span_app"}
    exec(compile(transformed.source, "app.py", "exec"), namespace)
    seen = []
    root = namespace["render"](18, seen.append)
    paragraph, button = root.children
    def content(node):
        if node.type == "Text":
            return node.props["value"]
        return "".join(content(child) for child in node.children)
    assert content(paragraph) == "Edit src/App.tsx and save to test HMR"
    button.props["on_click"]()
    assert seen == [19]
    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(root), _constraints(800), generation=1,
    )
    styles = {
        origin.type: dict(node.style)
        for node in prepared.css_geometry_snapshot().nodes
        for node_id, origin in prepared.identities
        if node_id == node.node_id
    }
    assert styles["p"]["direction"] == "row"
    assert styles["p"]["wrap"] == "wrap"
