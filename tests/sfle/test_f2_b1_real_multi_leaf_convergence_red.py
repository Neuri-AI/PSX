"""RED B1: genuine SFLE engines must remeasure until *all* sibling widths settle.

No mock solver: each Text's intrinsic preferred width depends on measured
available width. The second round reallocates BOTH siblings. It is unsafe
to invoke strict final computation before the third UI measurement round.
"""

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.lengths import parse_length
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    WritingDirection,
)
from psx.sfle.remeasure_session import compute_with_width_measurements


def _style(props):
    return tuple(
        (name, parse_length(value) if isinstance(value, str) and (
            value == "auto" or value.endswith("px") or value.endswith("%")
        ) else value)
        for name, value in props.items()
    )


def test_snapshot():
    return LayoutInput(
        1, 27, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(200, True), AvailableSize(60, True)),
        (
            LayoutNode("root", None, "Flex", _style({
                "direction": "row", "width": "200px", "height": "60px",
                "align_items": "flex-start",
            })),
            LayoutNode("a", "root", "Text", _style({
                "width": "auto", "height": "auto", "flex_basis": "auto",
                "flex_grow": 1, "flex_shrink": 0, "min_width": "0px",
            })),
            LayoutNode("b", "root", "Text", _style({
                "width": "auto", "height": "auto", "flex_basis": "auto",
                "flex_grow": 1, "flex_shrink": 0, "min_width": "0px",
            })),
        ),
        (),
    )


def assert_real_engine_remeasurement_converges(engine):
    calls = []

    def measure(node_id, allocated_width):
        calls.append((node_id, allocated_width))
        preferred = (50 if allocated_width >= 100 else 90) if node_id == "a" else 100
        return IntrinsicSizes(0, preferred, 20, 20, preferred, 20)

    result = compute_with_width_measurements(
        test_snapshot(),
        engine.compute,
        measure,
        compute_provisional=engine.compute_provisional,
        initial_widths={"a": 100, "b": 100},
    )
    assert calls == [
        ("a", 100), ("b", 100),
        ("a", 75), ("b", 125),
        ("a", 95), ("b", 105),
    ]
    assert {key: box.content.width for key, box in result.boxes if key in ("a", "b")} == {
        "a": 95, "b": 105,
    }
    assert result.generation == 27


def test_B1_python_real_engine_multileaf_convergence():
    assert_real_engine_remeasurement_converges(PythonLayoutEngine())
