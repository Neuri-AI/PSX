"""Grid native geometry write/readback and rollback contract."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Thread

import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.grid_math import GridPackingError
from psx.sfle.grid_native_plan import GridNativePlacement
from psx.sfle.grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from psx.sfle.model import Rect


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
