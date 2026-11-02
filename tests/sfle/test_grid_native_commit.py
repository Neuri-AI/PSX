"""Grid native geometry write/readback and rollback contract."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Thread

import pytest

from psx.layout.contracts.errors import SFLEError
from psx.layout.fallback.grid_math import GridPackingError
from psx.layout.grid.grid_native_plan import GridNativePlacement
from psx.layout.adapters.grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from psx.layout.contracts.model import Rect


def placement(node_id, x, y, width=40, height=20):
    return GridNativePlacement(node_id, x, y, width, height, width, height, False, False)


@dataclass
class HeadlessWidget:
    geometry: Rect | None = None
    fail: bool = False


def commit(items, widgets, **kwargs):
    return commit_grid_native_geometry(
        items, backend=GridCommitBackend.HEADLESS, widgets=widgets,
        generation=3, current_generation=kwargs.get("current_generation", lambda: 3),
        is_ui_thread=kwargs.get("is_ui_thread", lambda: True),
    )


def test_headless_commits_cinnamon_geometry_and_reads_back():
    widgets = {"a": HeadlessWidget(), "b": HeadlessWidget()}
    receipt = commit((placement("a", 0, 0), placement("b", 40, 0)), widgets)
    assert receipt.node_ids == ("a", "b")
    assert receipt.max_readback_error == 0
    assert widgets["b"].geometry == Rect(40, 0, 40, 20)


def test_headless_rolls_back_on_generation_change_during_commit():
    state = {"generation": 3}
    class InvalidatingWidget:
        def __init__(self, trigger=False):
            self._geometry = Rect(1, 2, 3, 4)
            self.trigger = trigger

        @property
        def geometry(self):
            return self._geometry

        @geometry.setter
        def geometry(self, rect):
            self._geometry = rect
            if self.trigger:
                self.trigger = False
                state["generation"] = 4

    widgets = {"a": InvalidatingWidget(True), "b": InvalidatingWidget()}
    with pytest.raises(SFLEError):
        commit((placement("a", 0, 0), placement("b", 40, 0)),
               widgets, current_generation=lambda: state["generation"])
    assert all(w.geometry == Rect(1, 2, 3, 4) for w in widgets.values())


@pytest.mark.parametrize("mode", ["stale", "thread", "missing", "duplicate"])
def test_rejects_invalid_transaction_before_mutating_widgets(mode):
    widgets = {"a": HeadlessWidget(Rect(1, 2, 3, 4))}
    items = (placement("a", 0, 0),)
    options = {}
    if mode == "stale":
        options["current_generation"] = lambda: 4
    elif mode == "thread":
        options["is_ui_thread"] = lambda: False
    elif mode == "missing":
        widgets["b"] = HeadlessWidget()
    else:
        items = items * 2
    with pytest.raises((SFLEError, GridPackingError)):
        commit(items, widgets, **options)
    assert widgets["a"].geometry == Rect(1, 2, 3, 4)


def test_qt_real_widget_geometry_roundtrip():
    qt = pytest.importorskip("PySide6.QtWidgets")
    app = qt.QApplication.instance() or qt.QApplication([])
    parent = qt.QWidget()
    widgets = {"a": qt.QWidget(parent), "b": qt.QWidget(parent)}
    try:
        receipt = commit_grid_native_geometry(
            (placement("a", 1, 2), placement("b", 50, 2)),
            backend=GridCommitBackend.QT, widgets=widgets,
            generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        )
        assert receipt.max_readback_error == 0
        assert widgets["b"].geometry().x() == 50
    finally:
        parent.deleteLater()


def test_tk_real_widget_geometry_roundtrip():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("Tk requires X11")
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    widgets = {"a": tk.Label(root), "b": tk.Label(root)}
    try:
        receipt = commit_grid_native_geometry(
            (placement("a", 1, 2), placement("b", 50, 2)),
            backend=GridCommitBackend.TK, widgets=widgets,
            generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        )
        assert receipt.max_readback_error == 0
        assert round(float(widgets["b"].place_info()["x"])) == 50
    finally:
        root.destroy()


def test_tk_native_commit_reads_each_rectangle_once_after_writes():
    """Four-axis verification must not trigger four Tcl reads per widget."""
    class Widget:
        def __init__(self):
            self.rect = {}
            self.read_count = 0

        def place_info(self):
            self.read_count += 1
            return dict(self.rect)

        def place(self, **rect):
            self.rect = {name: str(value) for name, value in rect.items()}

        def place_forget(self):
            self.rect = {}

    widgets = {"a": Widget(), "b": Widget()}
    receipt = commit_grid_native_geometry(
        (placement("a", 1, 2), placement("b", 50, 2)),
        backend=GridCommitBackend.TK, widgets=widgets,
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
    )
    assert receipt.max_readback_error == 0
    # One initial snapshot (including unplaced status), one four-axis readback.
    assert [widgets[key].read_count for key in ("a", "b")] == [2, 2]


def test_tk_grid_reuses_prior_snapshot_but_still_reads_final_geometry():
    class Widget:
        def __init__(self):
            self.state = {}
            self.reads = 0

        def place_info(self):
            self.reads += 1
            return dict(self.state)

        def place(self, **values):
            self.state = {key: str(value) for key, value in values.items()}

        def place_forget(self):
            self.state = {}

    widgets = {"a": Widget(), "b": Widget()}
    receipt = commit_grid_native_geometry(
        (placement("a", 1, 2), placement("b", 50, 2)),
        backend=GridCommitBackend.TK, widgets=widgets,
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        prior_tk_placements={"a": {}, "b": {}},
    )
    assert receipt.max_readback_error == 0
    assert [widgets[key].reads for key in ("a", "b")] == [1, 1]
    assert widgets["a"].state["x"] == "1"
    with pytest.raises(GridPackingError, match="Tk backend"):
        commit_grid_native_geometry(
            (placement("a", 1, 2), ()),
            backend=GridCommitBackend.QT, widgets=widgets,
            generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
            prior_tk_placements={},
        )


def test_kivy_real_widget_geometry_projection_and_readback():
    pytest.importorskip("kivy")
    from kivy.uix.widget import Widget
    widgets = {"a": Widget(), "b": Widget()}
    receipt = commit_grid_native_geometry(
        (placement("a", 0, 0), placement("b", 40, 20)),
        backend=GridCommitBackend.KIVY, widgets=widgets,
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        parent_height=100,
    )
    assert receipt.max_readback_error == 0
    assert widgets["a"].pos == [0, 80]
    assert widgets["b"].pos == [40, 60]


def test_headless_readback_corruption_restores_all_previous_rectangles():
    class CorruptWidget:
        def __init__(self):
            self._geometry = Rect(1, 2, 3, 4)
            self.written = False

        @property
        def geometry(self):
            if self.written:
                return Rect(999, 999, 10, 10)
            return self._geometry

        @geometry.setter
        def geometry(self, value):
            self._geometry = value
            self.written = value != Rect(1, 2, 3, 4)

    widgets = {"a": HeadlessWidget(Rect(1, 2, 3, 4)), "b": CorruptWidget()}
    with pytest.raises(SFLEError, match="readback"):
        commit((placement("a", 0, 0), placement("b", 40, 0)), widgets)
    assert widgets["a"].geometry == Rect(1, 2, 3, 4)
    assert widgets["b"].geometry == Rect(1, 2, 3, 4)


def test_headless_uninitialized_geometry_is_restored_to_none_on_failure():
    state = {"generation": 3}
    class InvalidatingWidget:
        def __init__(self):
            self._geometry = None
            self.once = True

        @property
        def geometry(self):
            return self._geometry

        @geometry.setter
        def geometry(self, value):
            self._geometry = value
            if self.once:
                self.once = False
                state["generation"] = 4

    widgets = {"a": InvalidatingWidget(), "b": HeadlessWidget()}
    with pytest.raises(SFLEError):
        commit((placement("a", 0, 0), placement("b", 40, 0)), widgets,
               current_generation=lambda: state["generation"])
    assert widgets["a"].geometry is None
    assert widgets["b"].geometry is None


def test_kivy_nested_grid_coordinates_use_immediate_parent_height():
    pytest.importorskip("kivy")
    from kivy.uix.widget import Widget
    wrapper, leaf = Widget(), Widget()
    wrapper.add_widget(leaf)
    receipt = commit_grid_native_geometry(
        (placement("item", 5, 20, 100, 40), placement("item/leaf", 0, 0, 100, 15)),
        backend=GridCommitBackend.KIVY,
        widgets={"item": wrapper, "item/leaf": leaf},
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        parent_height=200, parent_heights={"item": 200, "item/leaf": 40},
    )
    assert receipt.max_readback_error == 0
    assert tuple(wrapper.pos) == (5, 140)
    assert tuple(leaf.pos) == (0, 25)


def test_kivy_nested_grid_uses_window_coordinates_after_vertical_resize():
    """Nested canvas positions follow the GridItem instead of staying local."""
    class Widget:
        def __init__(self, parent=None):
            self.parent = parent
            self.pos = (0.0, 0.0)
            self.size = (0.0, 0.0)

        @property
        def x(self):
            return self.pos[0]

        @property
        def y(self):
            return self.pos[1]

    root = Widget()
    wrapper = Widget(root)
    leaf = Widget(wrapper)
    placements = (
        placement("item", 10, 10, 100, 40),
        placement("item/leaf", 4, 10, 30, 20),
    )
    widgets = {"item": wrapper, "item/leaf": leaf}
    for generation, height in ((1, 200.0), (2, 300.0)):
        receipt = commit_grid_native_geometry(
            placements, backend=GridCommitBackend.KIVY,
            widgets=widgets, generation=generation,
            current_generation=lambda generation=generation: generation,
            is_ui_thread=lambda: True,
            parent_height=height,
            parent_heights={"item": height, "item/leaf": 40.0},
            kivy_window_coordinates=True,
        )
        assert receipt.max_readback_error == 0
        assert tuple(wrapper.pos) == (10, height - 50)
        assert tuple(leaf.pos) == (14, height - 40)
        assert leaf.y - wrapper.y == 10


def test_kivy_parent_height_mismatch_rejects_before_mutation():
    pytest.importorskip("kivy")
    from kivy.uix.widget import Widget
    child = Widget()
    previous = tuple(child.pos)
    with pytest.raises(GridPackingError):
        commit_grid_native_geometry(
            (placement("item", 0, 0),), backend=GridCommitBackend.KIVY,
            widgets={"item": child}, generation=1,
            current_generation=lambda: 1, is_ui_thread=lambda: True,
            parent_height=100, parent_heights={"wrong": 100},
        )
    assert tuple(child.pos) == previous


def test_unchanged_headless_grid_geometry_does_not_write_again():
    class CountingWidget:
        def __init__(self):
            self._geometry = None
            self.writes = 0

        @property
        def geometry(self):
            return self._geometry

        @geometry.setter
        def geometry(self, rect):
            self.writes += 1
            self._geometry = rect

    widgets = {"a": CountingWidget(), "b": CountingWidget()}
    placements = (placement("a", 0, 0), placement("b", 40, 0))
    commit(placements, widgets)
    assert [w.writes for w in widgets.values()] == [1, 1]
    commit(placements, widgets)
    assert [w.writes for w in widgets.values()] == [1, 1]
    commit((placement("a", 0, 0), placement("b", 44, 0)), widgets)
    assert [w.writes for w in widgets.values()] == [1, 2]


def test_unchanged_qt_grid_geometry_does_not_write_again():
    qt = pytest.importorskip("PySide6.QtWidgets")
    app = qt.QApplication.instance() or qt.QApplication([])

    class CountingWidget(qt.QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.writes = 0

        def setGeometry(self, *args):
            self.writes += 1
            return super().setGeometry(*args)

    parent = qt.QWidget()
    child = CountingWidget(parent)
    try:
        placements = (placement("a", 1, 2),)
        kwargs = dict(
            backend=GridCommitBackend.QT, widgets={"a": child},
            generation=3, current_generation=lambda: 3,
            is_ui_thread=lambda: True,
        )
        commit_grid_native_geometry(placements, **kwargs)
        first = child.writes
        assert first == 1
        commit_grid_native_geometry(placements, **kwargs)
        assert child.writes == first
        commit_grid_native_geometry((placement("a", 2, 2),), **kwargs)
        assert child.writes == first + 1
    finally:
        parent.deleteLater()


def test_kivy_grid_overflow_projects_negative_local_y_without_clamping():
    """Cinnamon can place a valid overflowing child below its Kivy parent."""
    class Widget:
        def __init__(self):
            self.pos = (2.0, 3.0)
            self.size = (4.0, 5.0)

    widget = Widget()
    receipt = commit_grid_native_geometry(
        (placement("overflow", 6, 85, 40, 30),),
        backend=GridCommitBackend.KIVY,
        widgets={"overflow": widget},
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        parent_height=100,
    )
    assert tuple(widget.pos) == (6, -15)
    assert tuple(widget.size) == (40, 30)
    assert receipt.max_readback_error == 0


def test_kivy_nested_overflow_uses_immediate_parent_without_moving_ancestor():
    """Do not use outer viewport height to flip a nested Grid child."""
    class Widget:
        def __init__(self):
            self.pos = (0.0, 0.0)
            self.size = (1.0, 1.0)

    container = Widget()
    child = Widget()
    receipt = commit_grid_native_geometry(
        (placement("container", 10, 5, 100, 40),
         placement("container/child", 4, 35, 30, 20)),
        backend=GridCommitBackend.KIVY,
        widgets={"container": container, "container/child": child},
        generation=1, current_generation=lambda: 1, is_ui_thread=lambda: True,
        parent_height=200,
        parent_heights={"container": 200, "container/child": 40},
    )
    assert tuple(container.pos) == (10, 155)
    assert tuple(child.pos) == (4, -15)
    assert receipt.max_readback_error == 0


def test_kivy_grid_overflow_rejects_invalid_parent_height_without_writes():
    """Malformed parent measurements must still fail closed before native updates."""
    class Widget:
        def __init__(self):
            self.pos = (2.0, 3.0)
            self.size = (4.0, 5.0)

    widget = Widget()
    for height in (-1.0, float("nan"), float("inf")):
        with pytest.raises(GridPackingError, match="parent height"):
            commit_grid_native_geometry(
                (placement("overflow", 6, 85, 40, 30),),
                backend=GridCommitBackend.KIVY,
                widgets={"overflow": widget},
                generation=1, current_generation=lambda: 1,
                is_ui_thread=lambda: True, parent_height=100,
                parent_heights={"overflow": height},
            )
        assert tuple(widget.pos) == (2, 3)
        assert tuple(widget.size) == (4, 5)


def test_kivy_real_widget_renders_overflow_outside_parent_box():
    """Real Kivy widgets retain the solver's unclamped bottom-left geometry."""
    pytest.importorskip("kivy")
    from kivy.uix.widget import Widget

    parent = Widget(size_hint=(None, None), size=(100, 100))
    child = Widget(size_hint=(None, None))
    parent.add_widget(child)
    receipt = commit_grid_native_geometry(
        (placement("child", 6, 85, 40, 30),),
        backend=GridCommitBackend.KIVY,
        widgets={"child": child},
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True, parent_height=100,
    )
    assert tuple(child.pos) == (6, -15)
    assert tuple(child.size) == (40, 30)
    assert receipt.max_readback_error == 0


def test_kivy_scrolled_grid_item_content_starts_at_content_origin():
    """A viewport shorter than its content must not offset the GridItem."""
    from types import SimpleNamespace
    from psx.layout.grid.grid_native_composition import (
        ComposedGrid, compose_geometry_batch,
    )
    from psx.layout.projection.native_layout_snapshot import path_identity

    item_source, scroll_source, root_source = object(), object(), object()
    identifier = path_identity(("dashboard", "main"))
    content = SimpleNamespace(source=root_source)
    scroll = SimpleNamespace(source=scroll_source, effective_children=(content,))
    item = SimpleNamespace(
        source=item_source, path=("dashboard", "main"),
        effective_children=(scroll,),
    )
    flow = SimpleNamespace(
        prepared=SimpleNamespace(
            identities=(),
            snapshot=SimpleNamespace(nodes=(SimpleNamespace(node_id="flow-root"),)),
        ),
        result=SimpleNamespace(boxes=()),
        nested_grids={},
    )
    composed = ComposedGrid(
        grid=SimpleNamespace(effective_children=(item,)),
        prepared=SimpleNamespace(placements=(
            placement(identifier, 0, 0, 400, 600),
        )),
        nested={}, nested_flex={}, nested_flow={},
        nested_scroll={identifier: (flow, 400.0, 600.0, 1100.0)},
        content_height=600.0,
    )
    batch, widgets, heights = compose_geometry_batch(
        composed, handles={
            id(item_source): "item",
            id(scroll_source): "scroll",
            id(root_source): "content",
        },
        root_height=800.0,
    )
    content_id = identifier + "/scroll/content"
    assert widgets[content_id] == "content"
    assert heights[content_id] == 1100.0
    content_placement = next(p for p in batch if p.node_id == content_id)
    assert content_placement.height == 1100.0
    # The native projection is measured from the full Scroll content, not
    # its 600-pixel visible viewport: top-level content starts at local y=0.
    assert heights[content_id] - content_placement.y - content_placement.height == 0.0




def test_kivy_grid_width_only_resize_skips_position_notifications():
    """Keep Kivy property/canvas observers quiet for unchanged axes."""
    class Observed:
        def __init__(self):
            self._pos = (0.0, 0.0)
            self._size = (0.0, 0.0)
            self.pos_writes = 0
            self.size_writes = 0

        @property
        def pos(self):
            return self._pos

        @pos.setter
        def pos(self, value):
            self._pos = tuple(value)
            self.pos_writes += 1

        @property
        def size(self):
            return self._size

        @size.setter
        def size(self, value):
            self._size = tuple(value)
            self.size_writes += 1

    child = Observed()

    def apply(width, generation):
        return commit_grid_native_geometry(
            (placement("child", 10, 5, width, 20),),
            backend=GridCommitBackend.KIVY, widgets={"child": child},
            generation=generation,
            current_generation=lambda: generation,
            is_ui_thread=lambda: True, parent_height=100,
        )

    apply(40, 1)
    assert (child.pos_writes, child.size_writes) == (1, 1)
    apply(60, 2)
    assert (child.pos_writes, child.size_writes) == (1, 2)
    apply(60, 3)
    assert (child.pos_writes, child.size_writes) == (1, 2)
    assert tuple(child.pos) == (10, 75)
    assert tuple(child.size) == (60, 20)


def test_mixed_grid_commit_reuses_outer_rollback_snapshot():
    """Qt/Kivy outer bridge must not snapshot thousands of Grid leaves twice."""
    from types import SimpleNamespace
    from threading import get_ident
    from psx.layout.grid.mixed_grid_native import MountedMixedGrid

    class Native:
        pos = (0, 0)
        size = (0, 0)

    native = Native()
    mixed = object.__new__(MountedMixedGrid)
    mixed.backend = GridCommitBackend.KIVY
    mixed.renderer = SimpleNamespace(
        _sfle_generation=3, _sfle_owner_thread=get_ident(),
    )
    mixed.handles = {}
    mixed.generation = 3
    mixed.snapshot = lambda: (_ for _ in ()).throw(
        AssertionError("Duplicate native Grid snapshot"),
    )
    mixed._bind_nested_scrolls = lambda *args: None
    mixed.restore = lambda *args: None
    plan = (
        SimpleNamespace(prepared=SimpleNamespace()),
        (placement("a", 0, 0),),
        {"a": native},
        {"a": 100},
        100,
    )
    outer_before = ((native, ((0, 0), (0, 0))),)
    receipts = mixed.commit((plan,), prior_snapshot=outer_before)
    assert len(receipts) == 1
    assert tuple(native.size) == (40, 20)


def test_qt_grid_prior_snapshot_eliminates_duplicate_widget_geometry_read():
    class FakeRect:
        def __init__(self, value):
            self.value = value
        def x(self): return self.value[0]
        def y(self): return self.value[1]
        def width(self): return self.value[2]
        def height(self): return self.value[3]

    class Widget:
        def __init__(self):
            self.rect = (0, 0, 0, 0)
            self.reads = 0
        def geometry(self):
            self.reads += 1
            return FakeRect(self.rect)
        def setGeometry(self, *args):
            self.rect = args

    widget = Widget()
    receipt = commit_grid_native_geometry(
        (placement("child", 10, 15, 40, 20),),
        backend=GridCommitBackend.QT, widgets={"child": widget},
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True,
        prior_native_rectangles={"child": Rect(0, 0, 0, 0)},
    )
    assert receipt.max_readback_error == 0
    assert widget.rect == (10, 15, 40, 20)
    assert widget.reads == 1, "Only postcommit verification may read QWidget.geometry"


def test_kivy_grid_prior_snapshot_preserves_readback_and_rollback():
    class Widget:
        def __init__(self):
            self._pos = (0.0, 0.0)
            self._size = (0.0, 0.0)
            self.reads = 0
        @property
        def pos(self):
            self.reads += 1
            return self._pos
        @pos.setter
        def pos(self, value):
            self._pos = tuple(value)
        @property
        def size(self):
            self.reads += 1
            return self._size
        @size.setter
        def size(self, value):
            self._size = tuple(value)

    widget = Widget()
    receipt = commit_grid_native_geometry(
        (placement("child", 10, 5, 40, 20),),
        backend=GridCommitBackend.KIVY, widgets={"child": widget},
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True, parent_height=100,
        prior_native_rectangles={"child": Rect(0, 0, 0, 0)},
    )
    assert receipt.max_readback_error == 0
    assert widget._pos == (10, 75)
    assert widget._size == (40, 20)
    # The captured rollback rectangle supplies the write-time comparison.
    # Only 4 final live getters remain (2 x pos, 2 x size).
    assert widget.reads == 4
    with pytest.raises(GridPackingError, match="Qt or Kivy"):
        commit_grid_native_geometry(
            (placement("child", 10, 5, 40, 20),),
            backend=GridCommitBackend.TK, widgets={"child": widget},
            generation=1, current_generation=lambda: 1,
            is_ui_thread=lambda: True,
            prior_native_rectangles={"child": Rect(0, 0, 0, 0)},
        )


def test_grid_unchanged_qt_child_reuses_owner_thread_rollback_readback():
    """Grid must read changed Qt widgets, not thousands of inert siblings."""
    class FakeRect:
        def __init__(self, axes):
            self.axes = axes
        def x(self): return self.axes[0]
        def y(self): return self.axes[1]
        def width(self): return self.axes[2]
        def height(self): return self.axes[3]

    class Widget:
        def __init__(self, axes):
            self.axes = axes
            self.reads = 0
        def geometry(self):
            self.reads += 1
            return FakeRect(self.axes)
        def setGeometry(self, *axes):
            self.axes = axes

    unchanged = Widget((10, 5, 40, 20))
    changed = Widget((70, 5, 40, 20))
    receipt = commit_grid_native_geometry(
        (placement("same", 10, 5), placement("changed", 75, 5)),
        backend=GridCommitBackend.QT,
        widgets={"same": unchanged, "changed": changed},
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True,
        prior_native_rectangles={
            "same": Rect(10, 5, 40, 20),
            "changed": Rect(70, 5, 40, 20),
        },
    )
    assert receipt.max_readback_error == 0
    assert unchanged.reads == 0
    assert changed.reads == 1
    assert changed.axes == (75, 5, 40, 20)


def test_grid_tk_explicit_unchanged_receipt_skips_tcl_readback():
    class Widget:
        def __init__(self, axes):
            self.axes = axes
            self.reads = 0
        def place_info(self):
            self.reads += 1
            return dict(self.axes)
        def place(self, **axes):
            self.axes = {k: str(v) for k, v in axes.items()}
        def place_forget(self):
            self.axes = {}

    fixed = {"x": "10", "y": "5", "width": "40", "height": "20"}
    widgets = {"same": Widget(fixed), "changed": Widget({
        "x": "70", "y": "5", "width": "40", "height": "20",
    })}
    receipt = commit_grid_native_geometry(
        (placement("same", 10, 5), placement("changed", 75, 5)),
        backend=GridCommitBackend.TK, widgets=widgets,
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True,
        prior_tk_placements={
            name: dict(widget.axes) for name, widget in widgets.items()
        },
    )
    assert receipt.max_readback_error == 0
    assert widgets["same"].reads == 0
    assert widgets["changed"].reads == 1


def test_grid_tk_relative_placement_keeps_live_readback():
    class Widget:
        def __init__(self):
            self.reads = 0
        def place_info(self):
            self.reads += 1
            return dict(x="10", y="5", width="40", height="20",
                        relx="0.5")
        def place(self, **axes):
            raise AssertionError("Matching explicit axes should not be rewritten")
    widget = Widget()
    receipt = commit_grid_native_geometry(
        (placement("child", 10, 5),),
        backend=GridCommitBackend.TK, widgets={"child": widget},
        generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True,
        prior_tk_placements={
            "child": dict(x="10", y="5", width="40", height="20",
                          relx="0.5"),
        },
    )
    assert receipt.max_readback_error == 0
    assert widget.reads == 1
