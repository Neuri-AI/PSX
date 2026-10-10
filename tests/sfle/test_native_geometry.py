"""Native geometry coordinate and widget API tests."""
from types import SimpleNamespace

from psx.sfle.margin_tree import MarginTreeNode, compute_margin_tree
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.flex_math import FlexBasis
from psx.sfle.native_geometry import NativeGeometryCommitter, GeometryBackend
from psx.sfle.recursive_measurement import RecursiveMeasurementResult


def sample():
    nodes = (
        MarginTreeNode("root", None, 100, 80),
        MarginTreeNode("child", "root", 20, 10,
            MarginFlexItem("child", FlexBasis(20, 20, grow=0, shrink=0), 10)),
    )
    result = RecursiveMeasurementResult(compute_margin_tree(nodes, generation=4), (), ())
    return nodes, result


def test_qt_relative_top_left_geometry():
    nodes, result = sample()
    calls = []
    widget = SimpleNamespace(setGeometry=lambda *args: calls.append(args))
    NativeGeometryCommitter(GeometryBackend.QT, nodes, {"child": widget})(result)
    assert calls == [(0, 0, 20, 10)]


def test_tk_relative_top_left_geometry():
    nodes, result = sample()
    calls = []
    widget = SimpleNamespace(place=lambda **kwargs: calls.append(kwargs))
    NativeGeometryCommitter(GeometryBackend.TK, nodes, {"child": widget})(result)
    assert calls == [{"x": 0, "y": 0, "width": 20, "height": 10}]


def test_kivy_parent_relative_bottom_left_geometry():
    nodes, result = sample()
    widget = SimpleNamespace(pos=None, size=None)
    NativeGeometryCommitter(GeometryBackend.KIVY, nodes, {"child": widget})(result)
    assert widget.pos == (0, 70)
    assert widget.size == (20, 10)
