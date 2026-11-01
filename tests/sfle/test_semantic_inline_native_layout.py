"""Cinnamon can lay out multiple text-line fragments without new VNodes."""
from __future__ import annotations

from types import SimpleNamespace

from psx.sfle.model import (
    AvailableSize, BoxRect, LayoutConstraints, LayoutInput, LayoutNode,
    LayoutResult, Rect, WritingDirection,
)
from psx.sfle.semantic_inline_native_layout import compute_semantic_inline_native
from psx.sfle.semantic_inline_text import InlineTextMetrics


def box(x, y, width, height):
    rect = Rect(x, y, width, height)
    return BoxRect(rect, rect, rect, rect)


def vnode(tag, value=None):
    return SimpleNamespace(
        type=tag,
        props={} if value is None else {"value": value},
        css_computed=None,
    )


def test_original_three_text_nodes_survive_native_fragment_projection():
    nodes = (
        LayoutNode("root", None, "Flex", (("direction", "column"),)),
        LayoutNode("p", "root", "Flex", (("direction", "row"), ("wrap", "wrap"))),
        LayoutNode("before", "p", "Text", ()),
        LayoutNode("span", "p", "Flex", (("direction", "row"),)),
        LayoutNode("inside", "span", "Text", ()),
        LayoutNode("after", "p", "Text", ()),
        LayoutNode("button", "root", "Button", ()),
    )
    snapshot = LayoutInput(
        1, 1, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(190, True), AvailableSize(400, True)),
        nodes, (),
    )
    sources = (
        ("root", vnode("div")),
        ("p", vnode("p")),
        ("before", vnode("Text", "Edit ")),
        ("span", vnode("span")),
        ("inside", vnode("Text", "main.py")),
        ("after", vnode("Text", " and save to test HMR")),
        ("button", vnode("Button")),
    )

    def initial(height):
        boxes = (
            ("root", box(0, 0, 190, height + 32)),
            ("p", box(0, 0, 190, height)),
            ("before", box(0, 0, 50, 20)),
            ("span", box(50, 0, 70, 20)),
            ("inside", box(50, 0, 70, 20)),
            ("after", box(120, 0, 210, 20)),
            ("button", box(0, height, 110, 32)),
        )
        return LayoutResult(1, 1, boxes)

    seen_heights = []

    def recompute(adjusted):
        node = next(item for item in adjusted.nodes if item.node_id == "p")
        height = dict(node.style)["layout_height"]
        seen_heights.append(height)
        return initial(height)

    result, paint = compute_semantic_inline_native(
        snapshot, sources, initial(20),
        measure=lambda node_id, text: InlineTextMetrics(len(text)*10, 20, 15),
        recompute=recompute,
    )

    assert len(snapshot.nodes) == 7
    assert [identifier for identifier, _ in result.boxes] == [
        node.node_id for node in snapshot.nodes
    ]
    assert list(paint) == ["before", "inside", "after"]
    assert seen_heights and seen_heights[0] > 20
    paragraph = dict(result.boxes)["p"].content
    button = dict(result.boxes)["button"].content
    assert button.y >= paragraph.y + paragraph.height
    assert len(set(f.line_index for source in paint.values() for f in source)) > 1
    assert "".join(s[1].props.get("value", "")
                   for s in sources if s[1].type == "Text") == (
                       "Edit main.py and save to test HMR"
                   )
