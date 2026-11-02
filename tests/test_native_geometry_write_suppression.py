"""C5 native commit avoids writes when SFLE geometry is unchanged."""
from __future__ import annotations

import pytest

from psx.layout.fallback.margin_tree import MarginTreeNode
from psx.layout.contracts.model import BoxRect, LayoutResult, Rect
from psx.layout.adapters.native_geometry import GeometryBackend, NativeGeometryCommitter


def snapshot(width: float) -> LayoutResult:
    def box(rect):
        return BoxRect(rect, rect, rect, rect)
    return LayoutResult(
        schema_version=1, generation=1,
        boxes=(("root", box(Rect(0, 0, 200, 100))),
               ("child", box(Rect(10, 15, width, 30)))),
    )


class QtRect:
    def __init__(self, state):
        self.state = state

    def x(self): return self.state[0]
    def y(self): return self.state[1]
    def width(self): return self.state[2]
    def height(self): return self.state[3]


class QtWidget:
    def __init__(self):
        self.state = (0, 0, 0, 0)
        self.writes = 0

    def geometry(self):
        return QtRect(self.state)

    def setGeometry(self, *values):
        self.state = values
        self.writes += 1


class TkWidget:
    def __init__(self):
        self.state = {}
        self.writes = 0

    def place_info(self):
        return self.state

    def place(self, **values):
        self.state = {key: str(value) for key, value in values.items()}
        self.writes += 1


class KivyWidget:
    def __init__(self):
        self._pos = (0, 0)
        self._size = (0, 0)
        self.writes = 0

    @property
    def pos(self): return self._pos

    @pos.setter
    def pos(self, value):
        self._pos = tuple(value)
        self.writes += 1

    @property
    def size(self): return self._size

    @size.setter
    def size(self, value):
        self._size = tuple(value)
        self.writes += 1


@pytest.mark.parametrize(
    "backend,widget_type",
    ((GeometryBackend.QT, QtWidget), (GeometryBackend.TK, TkWidget),
     (GeometryBackend.KIVY, KivyWidget)),
)
def test_geometry_commit_skips_unchanged_native_widget(backend, widget_type):
    widget = widget_type()
    committer = NativeGeometryCommitter(
        backend, (MarginTreeNode("root", None, 0, 0),
                  MarginTreeNode("child", "root", 0, 0)),
        {"root": object(), "child": widget}, skip_unchanged=True,
    )
    committer(snapshot(40))
    first = widget.writes
    assert first > 0
    committer(snapshot(40))
    assert widget.writes == first, "Unchanged geometry must not mutate native widget"
    committer(snapshot(60))
    assert widget.writes > first, "Changed geometry must still be applied"


def test_tk_unchanged_check_uses_same_rollback_snapshot_without_native_reread():
    widget = TkWidget()
    widget.state = {"x": "10", "y": "15", "width": "40", "height": "30"}
    reads = []

    def tracked_place_info():
        reads.append(True)
        return dict(widget.state)

    widget.place_info = tracked_place_info
    nodes = (MarginTreeNode("root", None, 0, 0),
             MarginTreeNode("child", "root", 0, 0))
    committer = NativeGeometryCommitter(
        GeometryBackend.TK, nodes, {"root": object(), "child": widget},
        skip_unchanged=True, prior_tk_placements={"child": dict(widget.state)},
    )
    committer(snapshot(40))
    assert widget.writes == 0
    assert reads == []
    committer(snapshot(60))
    assert widget.writes == 1
    assert reads == []


def test_tk_prior_placements_are_detached_and_backend_scoped():
    widget = TkWidget()
    before = {"child": {"x": "10", "y": "15", "width": "40", "height": "30"}}
    nodes = (MarginTreeNode("root", None, 0, 0),
             MarginTreeNode("child", "root", 0, 0))
    committer = NativeGeometryCommitter(
        GeometryBackend.TK, nodes, {"root": object(), "child": widget},
        skip_unchanged=True, prior_tk_placements=before,
    )
    before["child"]["width"] = "60"
    committer(snapshot(40))
    assert widget.writes == 0
    with pytest.raises(TypeError, match="Tk backend"):
        NativeGeometryCommitter(
            GeometryBackend.QT, nodes, {"root": object(), "child": QtWidget()},
            prior_tk_placements=before,
        )


def test_qt_unchanged_uses_rollback_rectangles_without_redundant_qt_reads():
    widget = QtWidget()
    widget.state = (10, 15, 40, 30)
    reads = []
    original = widget.geometry

    def read():
        reads.append(1)
        return original()

    widget.geometry = read
    nodes = (
        MarginTreeNode("root", None, 0, 0),
        MarginTreeNode("child", "root", 0, 0),
    )
    baseline = {"child": (10, 15, 40, 30)}
    committer = NativeGeometryCommitter(
        GeometryBackend.QT, nodes, {"root": object(), "child": widget},
        skip_unchanged=True, prior_qt_rectangles=baseline,
    )
    baseline["child"] = (50, 20, 60, 30)
    committer(snapshot(40))
    assert widget.writes == 0 and reads == []
    committer(snapshot(60))
    assert widget.writes == 1 and reads == []
    assert widget.state == (10, 15, 60, 30)
    with pytest.raises(TypeError, match="Qt backend"):
        NativeGeometryCommitter(
            GeometryBackend.TK, nodes, {"root": object(), "child": TkWidget()},
            prior_qt_rectangles=baseline,
        )


def test_kivy_width_only_resize_does_not_dispatch_unchanged_position():
    widget = KivyWidget()
    committer = NativeGeometryCommitter(
        GeometryBackend.KIVY,
        (MarginTreeNode("root", None, 0, 0),
         MarginTreeNode("child", "root", 0, 0)),
        {"root": object(), "child": widget}, skip_unchanged=True,
    )
    committer(snapshot(40))
    assert widget.writes == 2
    committer(snapshot(60))
    assert widget.writes == 3, "Width-only resize must update size, not pos"
    assert widget.pos == (10, 55)
    assert widget.size == (60, 30)


def test_kivy_no_skip_mode_preserves_unconditional_writes():
    widget = KivyWidget()
    committer = NativeGeometryCommitter(
        GeometryBackend.KIVY,
        (MarginTreeNode("root", None, 0, 0),
         MarginTreeNode("child", "root", 0, 0)),
        {"root": object(), "child": widget},
    )
    committer(snapshot(40))
    committer(snapshot(40))
    assert widget.writes == 4


def test_kivy_prior_geometry_avoids_redundant_properties_on_unchanged_commit():
    class ObservedKivy(KivyWidget):
        def __init__(self):
            super().__init__()
            self.pos_reads = 0
            self.size_reads = 0

        @property
        def pos(self):
            self.pos_reads += 1
            return self._pos

        @pos.setter
        def pos(self, value):
            self._pos = tuple(value)
            self.writes += 1

        @property
        def size(self):
            self.size_reads += 1
            return self._size

        @size.setter
        def size(self, value):
            self._size = tuple(value)
            self.writes += 1

    widget = ObservedKivy()
    widget._pos, widget._size = (10, 55), (40, 30)
    prior = {"child": ((10, 55), (40, 30))}
    nodes = (
        MarginTreeNode("root", None, 0, 0),
        MarginTreeNode("child", "root", 0, 0),
    )
    committer = NativeGeometryCommitter(
        GeometryBackend.KIVY, nodes, {"root": object(), "child": widget},
        skip_unchanged=True, prior_kivy_rectangles=prior,
    )
    # The outer bridge already read pos and size for rollback.
    committer(snapshot(40))
    assert widget.writes == 0
    assert widget.pos_reads == 0
    assert widget.size_reads == 0

    # Defensive copy: callers may recycle their rollback dictionaries.
    prior["child"] = ((99, 99), (99, 99))
    committer(snapshot(60))
    assert widget.writes == 1
    assert widget.size == (60, 30)
    with pytest.raises(TypeError, match="Kivy backend"):
        NativeGeometryCommitter(
            GeometryBackend.QT, nodes, {"root": object(), "child": QtWidget()},
            prior_kivy_rectangles=prior,
        )
