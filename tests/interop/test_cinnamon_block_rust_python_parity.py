"""Independent installed-wheel equivalence for Cinnamon Block/Inline.

Compares actual Rust flow_snapshot.rs against Python measured_block_snapshot.py
with identical immutable inputs and measured font/control dimensions.
No mocks and no tolerance in geometry assertions.
"""
from __future__ import annotations
import pytest

from psx.layout.engine.backend import RustLayoutEngine
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.contracts.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _measure(node_id, width, height, baseline=None):
    return MeasuredBox(
        node_id, IntrinsicSizes(width, width, height, height,
                                width, height, baseline),
        LayoutConstraints(AvailableSize(600, True),
                          AvailableSize(400, True)), 1,
    )


def _case(name):
    constraints = LayoutConstraints(AvailableSize(600, True),
                                    AvailableSize(400, True))
    basic = (
        LayoutNode("root", None, "div", ()),
        LayoutNode("button", "root", "Button", ()),
        LayoutNode("text", "root", "Text", ()),
    )
    measurements = (_measure("button", 90, 25, 18),
                    _measure("text", 180, 30, 23))
    if name == "basic":
        nodes = basic
    elif name == "padded":
        nodes = (
            LayoutNode("root", None, "div", (
                ("layout_padding_left", "16px"),
                ("layout_padding_right", "16px"),
                ("layout_padding_top", "7px"),
                ("layout_border_top", "1px"),
            )),
            *basic[1:],
        )
    elif name == "fractional":
        nodes = (
            LayoutNode("root", None, "div", (("layout_padding_left", "7.3px"),)),
            *basic[1:],
        )
    elif name == "inline":
        nodes = (
            LayoutNode("root", None, "div", (("display", "inline"),)),
            *basic[1:],
        )
    elif name == "wrap":
        constraints = LayoutConstraints(AvailableSize(160, True),
                                        AvailableSize(400, True))
        nodes = (
            LayoutNode("root", None, "div", (("display", "inline"),)),
            *basic[1:],
        )
    elif name == "nested_flex":
        nodes = (
            LayoutNode("root", None, "div", ()),
            LayoutNode("title", "root", "p", (("display", "block"),)),
            LayoutNode("text", "title", "Text", ()),
            LayoutNode("flex", "root", "Flex", (
                ("direction", "column"), ("row_gap", "10px"),
            )),
            LayoutNode("button", "flex", "Button", ()),
        )
    elif name == "explicit_dimensions":
        nodes = (
            LayoutNode("root", None, "div", (
                ("layout_height", "200px"), ("layout_width", "240px"),
            )),
            *basic[1:],
        )
    elif name == "centering":
        nodes = (
            LayoutNode("root", None, "div", ()),
            LayoutNode("section", "root", "div", (
                ("layout_width", "240px"),
                ("layout_margin_left", "auto"),
                ("layout_margin_right", "auto"),
            )),
            LayoutNode("button", "section", "Button", ()),
            LayoutNode("text", "section", "Text", ()),
        )
    else:
        raise AssertionError(name)
    return LayoutInput(1, 31, WritingDirection.LTR,
                       constraints, nodes, measurements)


@pytest.mark.parametrize("case", [
    "basic", "padded", "fractional", "inline", "wrap",
    "nested_flex", "explicit_dimensions", "centering",
])
def test_rust_python_block_inline_exact_geometry(case):
    import _sfle_native
    rust = RustLayoutEngine(_sfle_native)
    python = PythonLayoutEngine()
    snapshot = _case(case)
    expected = python.compute(snapshot)
    actual = rust.compute(snapshot)
    assert actual.schema_version == expected.schema_version
    assert actual.generation == expected.generation
    assert actual.boxes == expected.boxes, (
        case, actual.boxes, expected.boxes,
    )
