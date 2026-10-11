"""RED B1: remeasure cascades across sibling leaves until *all* widths stabilize.

The initial first-pass flex result shifts A. A's remeasurement then shifts B.
A coordinator must not falsely report convergence before remeasuring B.
"""

from psx.sfle.model import (
    AvailableSize, BoxRect, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, LayoutResult, Rect, WritingDirection,
)
from psx.sfle.remeasure_session import compute_with_width_measurements


def test_a_change_that_reallocates_b_requires_a_third_ui_measurement():
    snapshot = LayoutInput(
        schema_version=1, generation=27, direction=WritingDirection.LTR,
        constraints=LayoutConstraints(AvailableSize(300, True), AvailableSize(100, True)),
        nodes=(
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("a", "root", "Text", ()),
            LayoutNode("b", "root", "Text", ()),
        ),
        measurements=(),
    )
    measurements = []

    def measure(node_id, width):
        measurements.append((node_id, width))
        return IntrinsicSizes(0, width, 20, 20, width, 20)

    def layout(input_snapshot):
        current = {m.node_id: m.constraints.width.value for m in input_snapshot.measurements}
        # A's changed intrinsic can force a new B allocation on the next pass.
        target_b = 130 if current["a"] == 150 else 100
        sizes = {"root": 300, "a": 150, "b": target_b}
        boxes = []
        for node_id, width in sizes.items():
            rect = Rect(0, 0, width, 20)
            boxes.append((node_id, BoxRect(rect, rect, rect, rect)))
        return LayoutResult(1, input_snapshot.generation, tuple(boxes))

    result = compute_with_width_measurements(
        snapshot, layout, measure,
        compute_provisional=layout, initial_widths={"a": 100, "b": 100},
    )
    assert measurements == [("a", 100), ("b", 100), ("a", 150), ("b", 130)]
    assert dict(result.boxes)["b"].content.width == 130
