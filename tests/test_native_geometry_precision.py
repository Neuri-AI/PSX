"""C6-I1 numerical geometry acceptance: signed saturation, DPI edges and native parents.

These deterministic geometry tests complement the executable Chromium oracle
and toolkit-native readback suites. Do not confuse QWidget DIPs with physical px.
"""
from __future__ import annotations

import math

import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.fixed_point import I32_MAX, I32_MIN, LayoutUnit
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.model import BoxRect, LayoutResult, Rect
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.native_pixel_space import DevicePixelSpace


def box(x: float, y: float, width: float, height: float) -> BoxRect:
    rect = Rect(x, y, width, height)
    return BoxRect(rect, rect, rect, rect)


@pytest.mark.parametrize("raw", (I32_MIN, I32_MIN + 1, -65, -64, -1,
                                  0, 1, 64, 65, I32_MAX - 1, I32_MAX))
def test_native_acceptance_signed_fixed_point_raw_boundaries_roundtrip(raw):
    unit = LayoutUnit.from_raw(raw)
    assert unit.raw == raw
    assert LayoutUnit.from_nearest(unit.to_px()).raw == raw


@pytest.mark.parametrize("value, expected", (
    (2**40, I32_MAX), (-2**40, I32_MIN),
    (I32_MAX / 64 + 1, I32_MAX), (I32_MIN / 64 - 1, I32_MIN),
))
def test_native_acceptance_layoutunit_saturates_before_native_application(value, expected):
    assert LayoutUnit.from_nearest(value).raw == expected


@pytest.mark.parametrize("dpr", (1, 1.25, 1.5, 2, 2.5, 3))
def test_native_acceptance_adjacent_edge_projection_has_zero_seam_error(dpr):
    projection = DevicePixelSpace(dpr, "qt")
    for raw in (-131, -65, -32, -1, 0, 1, 32, 65, 131):
        boundary = LayoutUnit.from_raw(raw).to_px()
        left = projection.to_physical(Rect(boundary - 2.5, 0, 2.5, 8))
        right = projection.to_physical(Rect(boundary, 0, 3.5, 8))
        assert left.x + left.width == right.x
        assert abs(left.x - (boundary - 2.5) * dpr) <= 0.5


@pytest.mark.parametrize("backend", (GeometryBackend.QT, GeometryBackend.TK,
                                      GeometryBackend.KIVY))
def test_native_acceptance_nested_parent_relative_native_readback_with_negative_coordinates(backend):
    class Native:
        def __init__(self):
            self.state = (0, 0, 0, 0)
        def geometry(self):
            coordinates = self.state
            class QtRectangle:
                def x(self): return coordinates[0]
                def y(self): return coordinates[1]
                def width(self): return coordinates[2]
                def height(self): return coordinates[3]
            return QtRectangle()
        def setGeometry(self, *values):
            self.state = tuple(values)
        def place(self, **values):
            self.state = tuple(values[key] for key in ("x", "y", "width", "height"))
        def place_info(self):
            return dict(zip(("x", "y", "width", "height"), map(str, self.state)))
        @property
        def pos(self):
            return self.state[:2]
        @pos.setter
        def pos(self, pair):
            self.state = (*pair, *self.state[2:])
        @property
        def size(self):
            return self.state[2:]
        @size.setter
        def size(self, pair):
            self.state = (*self.state[:2], *pair)

    nodes = (
        MarginTreeNode("root", None, 0, 0),
        MarginTreeNode("parent", "root", 0, 0),
        MarginTreeNode("child", "parent", 0, 0),
    )
    widgets = {key: Native() for key in ("root", "parent", "child")}
    result = LayoutResult(
        schema_version=1, generation=1,
        boxes=(
            ("root", box(0, 0, 200, 100)),
            ("parent", box(10, 12, 90, 50)),
            ("child", box(5, 18, 25, 12)),
        ),
    )
    NativeGeometryCommitter(backend, nodes, widgets)(result)
    parent_y = 100 - 12 - 50 if backend == GeometryBackend.KIVY else 12
    child_y = 50 - (18 - 12) - 12 if backend == GeometryBackend.KIVY else 6
    assert widgets["parent"].state == (10, parent_y, 90, 50)
    assert widgets["child"].state == (-5, child_y, 25, 12)
    assert widgets["root"].state == (0, 0, 0, 0)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -float("inf")))
def test_native_acceptance_nonfinite_native_projection_fails_closed(value):
    with pytest.raises(ValueError, match="Rect.x must be finite"):
        DevicePixelSpace(1.5, "qt").to_physical(Rect(value, 0, 10, 10))
