"""Point 3: signed i32 LayoutUnit saturation and native roundtrip certification.

These tests are deliberately orthogonal to Chromium's normal-range
0.01 px oracle: browser fuzz covers visual precision, while values near
signed i32 representability verify overflow behavior and Rust/Python parity.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from psx.sfle.fixed_point import I32_MAX, I32_MIN, SCALE, LayoutUnit
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
    WritingDirection,
)
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from test_sfle_f2_differential import _python_compute, _rust_compute, _rects, rust_binary


MAX_PX = I32_MAX / SCALE
MIN_PX = I32_MIN / SCALE


def _snapshot(width: float, child_basis: float, *, gap: float = 0.0) -> LayoutInput:
    return LayoutInput(
        1, 150_300, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(width, True), AvailableSize(90, True)),
        (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", f"{width}px"),
                ("height", "90px"), ("column_gap", f"{gap}px"),
                ("align_items", "flex-start"),
            )),
            LayoutNode("left", "root", "Box", (
                ("width", f"{child_basis}px"), ("height", "21.25px"),
                ("flex_basis", f"{child_basis}px"), ("flex_grow", 0.0),
                ("flex_shrink", 0.25), ("min_width", "0px"),
                ("layout_padding_left", "0.015625px"),
            )),
            LayoutNode("right", "root", "Box", (
                ("width", f"{child_basis}px"), ("height", "32.75px"),
                ("flex_basis", f"{child_basis}px"), ("flex_grow", 0.0),
                ("flex_shrink", 0.25), ("min_width", "0px"),
                ("layout_border_left", "0.015625px"),
            )),
        ), (),
    )


@pytest.mark.parametrize("width,basis,gap", (
    (0.0, MAX_PX, 0.0),
    (1.0, MAX_PX, 0.0),
    (128.0, MAX_PX, 1.0),
    (MAX_PX, MAX_PX, 0.0),
    (MAX_PX, MAX_PX, 0.015625),
    (MAX_PX - 1 / SCALE, MAX_PX, 19.0),
    (128.0, MAX_PX - 1 / SCALE, 0.0),
    (320.125, 100.5, 1 / SCALE),
))
def test_extreme_flex_freezing_is_bit_identical_and_i32_saturated(
    width, basis, gap, rust_binary,
):
    snapshot = _snapshot(width, basis, gap=gap)
    py = _python_compute(snapshot)
    rs = _rust_compute(rust_binary, snapshot)
    assert py["ok"] and rs["ok"], (
        "All finite explicit pixel sizes inside the signed LayoutUnit CSS",
        width, basis, gap, py.get("error"), rs.get("error"),
    )
    pb, rb = _rects(py["result"]), _rects(rs["result"])
    assert pb == rb, ("Signed i32 geometry parity", width, basis, gap, pb, rb)
    assert list(pb) == ["root", "left", "right"]
    for node, boxes in pb.items():
        for box in ("content", "padding", "border", "margin"):
            for axis in ("x", "y", "width", "height"):
                value = boxes[box][axis]
                assert MIN_PX <= value <= MAX_PX, (
                    "LayoutUnit escaped signed i32 range", node, box, axis, value,
                )
                assert value * SCALE == int(value * SCALE), (
                    "LayoutUnit lost 1/64 grid", node, box, axis, value,
                )


@pytest.mark.parametrize("backend", tuple(GeometryBackend))
@pytest.mark.parametrize("width,basis,gap", (
    (320.125, 100.5, 1 / SCALE),
    (301.625, 47.875, 5.1875),
    (510.0, 129.875, 0.25),
))
def test_native_adapters_roundtrip_fractional_sfle_geometry_within_one_pixel(
    width, basis, gap, backend,
):
    snapshot = _snapshot(width, basis, gap=gap)
    py = _python_compute(snapshot)
    assert py["ok"], py.get("error")
    boxes = {name: box["border"] for name, box in _rects(py["result"]).items()}
    calls: dict[str, tuple[float, float, float, float]] = {}

    class Widget:
        def __init__(self, key: str):
            self.key = key
            self._pos = (0.0, 0.0)
            self._size = (0.0, 0.0)

        def setGeometry(self, x: int, y: int, w: int, h: int) -> None:
            calls[self.key] = (x, y, w, h)

        def place(self, *, x: int, y: int, width: int, height: int) -> None:
            calls[self.key] = (x, y, width, height)

        @property
        def pos(self):
            return self._pos

        @pos.setter
        def pos(self, value):
            self._pos = tuple(value)
            calls[self.key] = (*self._pos, *self._size)

        @property
        def size(self):
            return self._size

        @size.setter
        def size(self, value):
            self._size = tuple(value)
            calls[self.key] = (*self._pos, *self._size)

    widgets = {name: Widget(name) for name in ("left", "right")}
    nodes = tuple(SimpleNamespace(node_id=n.node_id, parent_id=n.parent_id)
                  for n in snapshot.nodes)
    NativeGeometryCommitter(backend, nodes, widgets)(py["result"])
    assert set(calls) == {"left", "right"}
    for node_id, actual in calls.items():
        child, parent = boxes[node_id], boxes["root"]
        x = child["x"] - parent["x"]
        y = child["y"] - parent["y"]
        if backend == GeometryBackend.KIVY:
            y = parent["height"] - y - child["height"]
        expected = (x, y, child["width"], child["height"])
        for wanted, received in zip(expected, actual):
            assert abs(wanted - received) <= 1.0, (
                "native adapter >1px projection error", backend,
                width, node_id, wanted, received,
            )


@pytest.mark.parametrize("raw", (I32_MIN, I32_MIN + 1, -1, 0, 1, I32_MAX - 1, I32_MAX))
def test_fixed_point_signed_boundaries_never_wrap_or_lose_grid(raw):
    value = LayoutUnit.from_raw(raw)
    assert value.raw == raw
    assert value.to_px() * SCALE == raw
    assert (value + LayoutUnit.from_raw(99)).raw == min(I32_MAX, raw + 99)
    assert (value - LayoutUnit.from_raw(99)).raw == max(I32_MIN, raw - 99)


@pytest.mark.parametrize("fraction",(1e308,-1e308))
def test_huge_finite_percentage_margins_saturate_without_backend_exceptions(
    fraction,rust_binary,
):
    """Finite normalized CSS percentages must not create infinite raw geometry."""
    from dataclasses import replace
    from psx.sfle.lengths import Length
    snapshot=_snapshot(MAX_PX, 25.0)
    child=snapshot.nodes[1]
    modified=replace(child,style=child.style+(("layout_margin_left",Length.percent(fraction)),))
    snapshot=replace(snapshot,nodes=(snapshot.nodes[0],modified,snapshot.nodes[2]))
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    assert py["ok"]==rs["ok"],(fraction,py.get("error"),rs.get("error"))
    assert py["ok"],(fraction,py.get("error"),rs.get("error"))
    assert _rects(py["result"])==_rects(rs["result"])
    for box in _rects(py["result"]).values():
        for rect in ("content","padding","border","margin"):
            for axis in ("x","y","width","height"):
                raw=box[rect][axis]*SCALE
                assert I32_MIN<=raw<=I32_MAX
                assert raw==int(raw)
