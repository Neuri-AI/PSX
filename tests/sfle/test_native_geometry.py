"""Native geometry coordinate and widget API tests."""
from types import SimpleNamespace

from psx.layout.fallback.margin_tree import MarginTreeNode, compute_margin_tree
from psx.layout.fallback.margin_flex_pipeline import MarginFlexItem
from psx.layout.fallback.flex_math import FlexBasis
from psx.layout.adapters.native_geometry import NativeGeometryCommitter, GeometryBackend
from psx.layout.runtime.recursive_measurement import RecursiveMeasurementResult


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


def test_kivy_prior_snapshot_avoids_duplicate_reads_for_changed_size():
    """One prior read is sufficient for unchanged axes in a Kivy resize."""
    class Observed:
        def __init__(self):
            self._pos = (10.0, 55.0)
            self._size = (40.0, 30.0)
            self.reads = 0
            self.writes = 0
        @property
        def pos(self):
            self.reads += 1
            return self._pos
        @pos.setter
        def pos(self, value):
            self.writes += 1
            self._pos = tuple(value)
        @property
        def size(self):
            self.reads += 1
            return self._size
        @size.setter
        def size(self, value):
            self.writes += 1
            self._size = tuple(value)

    widget = Observed()
    nodes = (
        MarginTreeNode("root", None, 0, 0),
        MarginTreeNode("child", "root", 0, 0),
    )
    committer = NativeGeometryCommitter(
        GeometryBackend.KIVY, nodes, {"root": object(), "child": widget},
        skip_unchanged=True,
        prior_kivy_rectangles={
            "child": ((10.0, 55.0), (40.0, 30.0)),
        },
    )
    committer(snapshot(60))
    assert widget.reads == 0
    assert widget.writes == 1
    assert widget._pos == (10, 55)
    assert widget._size == (60, 30)
