"""A01 complete interface RED gate derived from the shared alpha fixture.

The exact same tree and measurement data is consumed by the Rust adapter.
"""
import json
from pathlib import Path
import pytest
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.lengths import parse_length
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)

CORPUS = json.loads((Path(__file__).parent / "fixtures" / "f2_alpha_acceptance.json").read_text())


def test_A01_compute_full_orthogonal_text_parent_height_60px():
    case = next(c for c in CORPUS["cases"] if c["id"] == "A01")
    nodes = tuple(LayoutNode(
        node["node_id"], node["parent_id"], node["component"],
        tuple((name, parse_length(value) if isinstance(value,str) and (value.endswith("px") or value.endswith("%") or value=="auto") else value) for name,value in node["style"].items())
    ) for node in case["nodes"])
    measured = case["measurements"][0]
    metrics = IntrinsicSizes(20,80,20,60,80,60)
    measurements = (
        MeasuredBox(measured["node"], metrics,
            LayoutConstraints(AvailableSize(measured["at_width"], True),
                              AvailableSize(measured["height"], True)), 0),
    )
    request = LayoutInput(
        1, 27, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(case["viewport"]["width"], True),
                          AvailableSize(None,False)),
        nodes, measurements,
    )
    layout = PythonLayoutEngine().compute(request)
    assert tuple(id for id, _ in layout.boxes) == tuple(n["node_id"] for n in case["nodes"])
    by_id = dict(layout.boxes)
    for node_id in ("root", "column", "text"):
        assert by_id[node_id].content.height == pytest.approx(
            case["expected"][f"{node_id}.height"], abs=CORPUS["tolerance_px"]
        )
    assert by_id["column"].content.width == pytest.approx(80, abs=0.01)
    assert by_id["text"].content.width == pytest.approx(80, abs=0.01)
