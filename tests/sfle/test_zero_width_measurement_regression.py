"""RED B1: an exact zero-size CSS constraint is valid, nonfinite is not.

The immutable used width can be numerically zero and still definite. This
must not be conflated with a missing or nonfinite measurement constraint.
"""

import math

import pytest

from psx.sfle.model import (
    AvailableSize, BoxRect, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, LayoutResult, Rect, WritingDirection,
)
from psx.sfle.remeasure_session import compute_with_width_measurements


def _snapshot():
    return LayoutInput(
        1, 29, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(0, True), AvailableSize(20, True)),
        (LayoutNode("root", None, "Flex", ()),
         LayoutNode("leaf", "root", "Text", ())), (),
    )


def _zero_layout(snapshot):
    zero = Rect(0, 0, 0, 0)
    box = BoxRect(zero, zero, zero, zero)
    return LayoutResult(1, snapshot.generation, (("root", box), ("leaf", box)))


def test_zero_width_measurement_is_definite_and_can_converge():
    calls = []

    def measure(node, width):
        calls.append((node, width))
        return IntrinsicSizes(0, 0, 0, 0, 0, 0)

    result = compute_with_width_measurements(
        _snapshot(), _zero_layout, measure, compute_provisional=_zero_layout,
        initial_widths={"leaf": 0},
    )
    assert calls == [("leaf", 0)]
    assert dict(result.boxes)["leaf"].content.width == 0


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_initial_width_rejected_before_any_measurement(invalid):
    calls = []

    def measure(node, width):
        calls.append((node, width))
        return IntrinsicSizes(0, 0, 0, 0, 0, 0)

    with pytest.raises(ValueError, match="finite"):
        compute_with_width_measurements(
            _snapshot(), _zero_layout, measure, compute_provisional=_zero_layout,
            initial_widths={"leaf": invalid},
        )
    assert calls == []
