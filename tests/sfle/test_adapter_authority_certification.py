"""F2.4 executable single-authority boundary: Scroll never recomputes Flex.

Pure ports use genuine SFLE rectangles. F3 will connect these contracts to
production Qt/Kivy/Tkinter/Headless renderer adapters; this test does not
pretend those production migrations are implemented.
"""
from dataclasses import replace

import pytest

from psx.sfle.adapter_contract import (
    SFLEAdapterPorts, ScrollViewport, derive_scroll_content_metrics,
    validate_adapter_commit,
)
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)


def _snapshot():
    return LayoutInput(
        1, 42, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(100, True), AvailableSize(60, True)),
        (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", "100px"), ("height", "60px"),
                ("align_items", "flex-start"),
            )),
            LayoutNode("outside", "root", "Box", (
                ("width", "10px"), ("height", "10px"), ("flex_basis", "10px"),
                ("flex_shrink", 0),
            )),
            LayoutNode("content", "root", "Flex", (
                ("direction", "row"), ("width", "120px"), ("height", "40px"),
                ("flex_basis", "120px"), ("flex_shrink", 0),
                ("align_items", "flex-start"),
            )),
            LayoutNode("child", "content", "Box", (
                ("width", "150px"), ("height", "50px"), ("flex_basis", "150px"),
                ("flex_shrink", 0), ("min_width", "0px"),
            )),
        ),
        (),
    )


def _ports(generation=42, alive=True):
    return SFLEAdapterPorts(
        current_generation=lambda: generation,
        nodes_alive=lambda _ids: alive,
        apply_rectangles=lambda _result: None,
        read_rectangles=lambda: {},
        scroll_content_root=lambda host_id: {
            "native-scroll": "content", "other-native-scroll": "content",
        }.get(host_id),
    )


def _viewport(**changes):
    return replace(ScrollViewport("native-scroll", "content", 80, 30, 999, -10), **changes)


def test_scroll_content_extent_comes_only_from_actual_sfle_subtree_rectangles():
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    before = result.boxes
    metrics = derive_scroll_content_metrics(snapshot, result, _ports(), _viewport())
    root = dict(result.boxes)["content"].border
    child = dict(result.boxes)["child"].border
    assert metrics.content_width == max(root.width, child.x + child.width - root.x)
    assert metrics.content_height == max(root.height, child.y + child.height - root.y)
    assert metrics.max_offset_x == metrics.content_width - 80
    assert metrics.max_offset_y == metrics.content_height - 30
    assert metrics.offset_x == metrics.max_offset_x
    assert metrics.offset_y == 0
    assert result.boxes == before, "Scroll projection must not mutate computed SFLE rectangles."


@pytest.mark.parametrize("generation,alive", [(41,True), (42,False)])
def test_scroll_commit_refuses_stale_or_disposed_nodes(generation, alive):
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    with pytest.raises(SFLEError) as exc:
        validate_adapter_commit(snapshot, result, _ports(generation, alive),
                                scroll_viewports=(_viewport(),))
    assert exc.value.code == DiagnosticCode.INVALID_SNAPSHOT


def test_scroll_host_must_not_be_in_sfle_geometry_or_duplicate_content_root():
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    with pytest.raises(SFLEError, match="must not receive"):
        validate_adapter_commit(snapshot, result, _ports(),
            scroll_viewports=(_viewport(host_id="root"),))
    with pytest.raises(SFLEError, match="multiple Scroll hosts"):
        validate_adapter_commit(snapshot, result, _ports(),
            scroll_viewports=(_viewport(), _viewport(host_id="other-native-scroll")))


def test_scroll_non_flex_content_is_explicitly_rejected_not_native_reflowed():
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    with pytest.raises(SFLEError) as exc:
        validate_adapter_commit(snapshot, result, _ports(),
            scroll_viewports=(_viewport(content_root_id="child"),))
    assert exc.value.code == DiagnosticCode.UNSUPPORTED_FEATURE
    assert exc.value.node_id == "child"


def test_scroll_extent_does_not_consider_unrelated_sibling_or_disposed_geometry():
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    # The root's geometry is irrelevant to content extent; sibling is not
    # inside the content Flex subtree even when its screen x is larger.
    metrics = derive_scroll_content_metrics(
        snapshot, result, _ports(), _viewport(viewport_width=200, viewport_height=100),
    )
    assert metrics.max_offset_x == metrics.max_offset_y == 0
    assert metrics.offset_x == metrics.offset_y == 0


def test_bad_scroll_identity_or_negative_viewport_fails_before_geometry():
    with pytest.raises(ValueError):
        ScrollViewport("scroll", "scroll", 80, 30)
    with pytest.raises(ValueError):
        ScrollViewport("scroll", "content", -1, 30)
