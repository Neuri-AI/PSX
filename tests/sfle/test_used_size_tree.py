"""F2.2.4 used content propagation remains CSS-definiteness aware."""
import pytest

from psx.sfle.constraint_propagation import ChildSizing
from psx.sfle.errors import SFLEError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection
from psx.sfle.percentage_box_sizing import BoxSizing
from psx.sfle.used_size_tree import NodeUsedSizing, propagate_definite_used_sizes


def pair(w, h):
    return LayoutConstraints(AvailableSize(w, w is not None), AvailableSize(h, h is not None))


def tree():
    return LayoutInput(1, 8, WritingDirection.LTR, pair(300, 200), (
        LayoutNode("root", None, "Flex", ()),
        LayoutNode("child", "root", "Flex", ()),
        LayoutNode("leaf", "child", "Text", ()),
    ), ())


def style(node_id, w, h, sizing=BoxSizing.CONTENT_BOX, edges=0):
    return NodeUsedSizing(node_id, ChildSizing(w, h), sizing, edges, edges)


def test_preorder_generates_parent_content_references():
    result = propagate_definite_used_sizes(
        tree(), root_content=pair(200, 80), children=(
            style("child", Length.percent(0.5), Length.percent(0.25)),
            style("leaf", Length.percent(0.5), Length.px(10)),
        ),
    )
    assert result.generation == 8
    assert dict(result.content)["child"] == pair(100, 20)
    assert dict(result.content)["leaf"] == pair(50, 10)
    assert result.deferred == ()


def test_border_box_content_propagates_not_border_box():
    result = propagate_definite_used_sizes(
        tree(), root_content=pair(200, 80), children=(
            style("child", Length.percent(0.5), Length.percent(0.5), BoxSizing.BORDER_BOX, 20),
            style("leaf", Length.percent(0.5), Length.px(10)),
        ),
    )
    assert dict(result.content)["child"] == pair(80, 20)
    assert dict(result.content)["leaf"] == pair(40, 10)


def test_auto_height_keeps_descendant_percent_unresolved():
    result = propagate_definite_used_sizes(
        tree(), root_content=pair(200, 80), children=(
            style("child", Length.px(100), Length(LengthKind.AUTO)),
            style("leaf", Length.percent(0.5), Length.percent(0.5)),
        ),
    )
    assert dict(result.content)["leaf"] == pair(50, None)
    assert result.deferred == ("child", "leaf")


def test_rejects_missing_or_duplicate_styles():
    child = style("child", Length.px(100), Length.px(20))
    with pytest.raises(SFLEError):
        propagate_definite_used_sizes(tree(), root_content=pair(200, 80), children=(child,))
    with pytest.raises(SFLEError):
        propagate_definite_used_sizes(
            tree(), root_content=pair(200, 80), children=(child, child),
        )
