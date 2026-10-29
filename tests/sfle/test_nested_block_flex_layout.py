"""Regression coverage for a CSS Flex formatting context inside block flow."""

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _intrinsic(width: float, height: float) -> IntrinsicSizes:
    return IntrinsicSizes(width, width, height, height, width, height)


def test_nested_flex_uses_vertical_gap_without_overlapping_block_siblings():
    constraints = LayoutConstraints(
        AvailableSize(800, True), AvailableSize(200, True),
    )
    nodes = (
        LayoutNode("root", None, "div", (("display", "block"),)),
        LayoutNode("paragraph", "root", "p", (("display", "block"),)),
        LayoutNode("text", "paragraph", "Text", ()),
        LayoutNode("container", "root", "Flex", (
            ("direction", "column"), ("row_gap", "10px"),
            ("column_gap", "10px"),
        )),
        LayoutNode("input", "container", "Input", ()),
        LayoutNode("button", "container", "Button", ()),
    )
    measured = (
        MeasuredBox("text", _intrinsic(180, 30), constraints, 0),
        MeasuredBox("input", _intrinsic(170, 25), constraints, 0),
        MeasuredBox("button", _intrinsic(90, 25), constraints, 0),
    )
    snapshot = LayoutInput(1, 1, WritingDirection.LTR, constraints, nodes, measured)
    boxes = dict(PythonLayoutEngine().compute(snapshot).boxes)

    assert boxes["container"].border.y >= boxes["paragraph"].border.y + boxes["paragraph"].border.height
    assert boxes["input"].border.y >= boxes["container"].border.y
    assert abs(boxes["button"].border.y - (
        boxes["input"].border.y + boxes["input"].border.height + 10
    )) <= 1 / 64
    assert boxes["root"].border.height >= (
        boxes["button"].border.y + boxes["button"].border.height
    )


def test_mixed_flow_uses_the_selected_flex_engine():
    """Block composition must not silently switch from Rust to Python."""
    from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot

    class TrackingEngine:
        def __init__(self):
            self.calls = []

        def compute(self, request):
            self.calls.append(request)
            from psx.sfle.engine import PythonLayoutEngine
            return PythonLayoutEngine().compute(request)

    constraints = LayoutConstraints(AvailableSize(400, True), AvailableSize(200, True))
    nodes = (
        LayoutNode("root", None, "div", (("display", "block"),)),
        LayoutNode("flex", "root", "Flex", (("direction", "column"),)),
        LayoutNode("button", "flex", "Button", ()),
    )
    snapshot = LayoutInput(
        1, 0, WritingDirection.LTR, constraints, nodes,
        (MeasuredBox("button", _intrinsic(90, 25), constraints, 0),),
    )
    engine = TrackingEngine()
    result = compute_measured_block_snapshot(snapshot, flex_engine=engine)
    assert len(engine.calls) == 1
    assert engine.calls[0].nodes[0].component == "Flex"
    assert dict(result.boxes)["button"].border.height == 25


def test_nested_activity_flex_remeasures_wrapped_description_at_assigned_width():
    from psx.sfle.measured_block_snapshot import compute_measured_block_snapshot
    constraints = LayoutConstraints(AvailableSize(500, True), AvailableSize(None, False))
    nodes = (
        LayoutNode("root", None, "div", (("display", "block"),)),
        LayoutNode("row", "root", "Flex", (("direction", "row"), ("column_gap", "10px"))),
        LayoutNode("description", "row", "Text", (("flex_grow", 1), ("flex_shrink", 1))),
        LayoutNode("time", "row", "Text", (("layout_min_width", "120px"),)),
    )
    measurements = (
        MeasuredBox("description", IntrinsicSizes(0, 380, 14, 14, 380, 14), constraints, 1),
        MeasuredBox("time", IntrinsicSizes(120, 200, 20, 20, 200, 20), constraints, 1),
    )
    measured_widths = {}
    def measure(identifier, width):
        measured_widths[identifier] = width
        height = 42 if identifier == "description" and width < 380 else 20
        return _intrinsic(width, height)
    result = compute_measured_block_snapshot(
        LayoutInput(1, 1, WritingDirection.LTR, constraints, nodes, measurements),
        flex_engine=PythonLayoutEngine(), measure_width=measure,
    )
    boxes = dict(result.boxes)
    assert measured_widths["description"] < 380
    assert boxes["description"].border.height >= 42
    assert boxes["row"].border.height >= boxes["description"].border.height
