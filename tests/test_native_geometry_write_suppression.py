"""C5 native commit avoids writes when SFLE geometry is unchanged."""
from __future__ import annotations

import pytest

from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.model import BoxRect, LayoutResult, Rect
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter


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
