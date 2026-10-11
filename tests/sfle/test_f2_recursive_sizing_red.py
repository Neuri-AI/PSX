"""Independent content/minimum and per-line sizing regressions.

Expected rectangles follow CSS Flexbox sections 4.5, 9.3 and 9.7. Tests use
fixed empty boxes or immutable intrinsic metrics, without native font guesses.
The same specifications are consumed by the Rust integration test.
"""
import json
from pathlib import Path

import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)

CASES = json.loads((Path(__file__).parent / "fixtures/f2_recursive_sizing.json").read_text())


def make_snapshot(case):
    def constraints(width, height):
        return LayoutConstraints(AvailableSize(width, width is not None),
                                 AvailableSize(height, height is not None))
    return LayoutInput(
        1, 23, WritingDirection(case.get("direction", "ltr")),
        constraints(None, None),
        tuple(LayoutNode(n["node_id"], n["parent_id"], "Flex", tuple(n["style"].items()))
              for n in case["nodes"]),
        tuple(MeasuredBox(m["node_id"], IntrinsicSizes(**m["intrinsic"]),
                          constraints(None, None), 0) for m in case.get("measurements", [])),
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_recursive_and_line_sizing(case):
    result = PythonLayoutEngine().compute(make_snapshot(case))
    assert result.generation == 23
    assert tuple(node_id for node_id, _ in result.boxes) == tuple(n["node_id"] for n in case["nodes"])
    boxes = dict(result.boxes)
    for node_id, expected in case["expected"].items():
        for axis, wanted in expected.items():
            assert getattr(boxes[node_id].content, axis) == wanted, (case["id"], node_id, axis)
