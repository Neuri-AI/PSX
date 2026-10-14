"""Executable Grid native source measurement integration and fail-closed rules."""
from __future__ import annotations

from threading import Thread

import pytest

from psx import Grid, GridItem, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.grid_math import GridPackingError
from psx.sfle.grid_native_measurement import (
    HeadlessGridMeasurementSource, measure_grid_native,
)
from psx.sfle.model import IntrinsicSizes
from psx.sfle.native_layout_snapshot import path_identity
from psx.sfle.errors import SFLEError


def tree():
    return normalize_flex_tree(Grid(
        GridItem(Text("alpha"), span={"base": 12, "md": 6}, key="alpha"),
        GridItem(Text("beta"), span={"base": 12, "md": 6}, key="beta"),
        gap=4,
    ))


def setup():
    grid = tree()
    children = grid.effective_children
    ids = tuple(path_identity(child.path) for child in children)
    widgets = {identifier: child.effective_children[0].source
               for identifier, child in zip(ids, children)}
    seen = []

    def intrinsic(node, width):
        seen.append((node, width))
        height = 30 if width < 390 else 10
        return IntrinsicSizes(0, width, 0, height, width, height)

    return grid, ids, HeadlessGridMeasurementSource(widgets, intrinsic), seen


def run(grid, ids, source, **options):
    return measure_grid_native(
        grid, content_width=800, source=source, mounted_ids=ids,
        revisions={identifier: 1 for identifier in ids},
        generation=4, current_generation=4, **options,
    )


def test_real_native_source_receipts_use_projected_grid_width_and_revision():
    grid, ids, source, seen = setup()
    result = run(grid, ids, source)
    assert len(seen) == 2
    assert [width for _, width in seen] == [398, 398]
    assert result.measurement_revisions == tuple((identifier, 1) for identifier in ids)
    assert result.placements[1].x == 402
    assert result.placements[0].height == 10


def test_responsive_reflow_uses_actual_native_width_for_height():
    grid, ids, source, seen = setup()
    result = measure_grid_native(
        grid, content_width=767, source=source, mounted_ids=ids,
        revisions={identifier: 3 for identifier in ids},
        generation=4, current_generation=4,
    )
    assert len(result.rows) == 2
    assert [width for _, width in seen] == [767, 767]
    assert result.placements[1].y == 14


def test_native_source_receipts_change_height_at_breakpoint():
    grid, ids, source, seen = setup()
    result = measure_grid_native(
        grid, content_width=768, source=source, mounted_ids=ids,
        revisions={identifier: 4 for identifier in ids},
        generation=4, current_generation=4,
    )
    assert len(result.rows) == 1
    assert [width for _, width in seen] == [382, 382]
    assert result.placements[0].height == 30


@pytest.mark.parametrize("case", ("stale", "missing", "invalid_revision", "unknown_widget"))
def test_native_measurement_rejects_incomplete_or_stale_evidence_before_commit(case):
    grid, ids, source, seen = setup()
    revisions = {identifier: 1 for identifier in ids}
    kwargs = {}
    if case == "stale":
        kwargs["current_generation"] = 5
    elif case == "missing":
        revisions.pop(ids[0])
    elif case == "invalid_revision":
        revisions[ids[0]] = True
    else:
        source._nodes.pop(ids[0])
    with pytest.raises((GridPackingError, SFLEError)):
        measure_grid_native(
            grid, content_width=800, source=source, mounted_ids=ids,
            revisions=revisions, generation=4,
            current_generation=kwargs.get("current_generation", 4),
        )


def test_native_source_refuses_non_ui_thread_measurement():
    grid, ids, source, seen = setup()
    failures = []

    def worker():
        try:
            run(grid, ids, source)
        except SFLEError as exc:
            failures.append(exc)

    thread = Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert len(failures) == 1
    assert not seen


def test_headless_native_source_never_fabricates_missing_intrinsic_metrics():
    grid, ids, source, seen = setup()
    source._measure_intrinsic = lambda node, width: None
    with pytest.raises(SFLEError):
        run(grid, ids, source)


def test_qt_measurement_uses_actual_qwidget_intrinsics():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    qtcore = pytest.importorskip("PySide6.QtCore")
    from psx.sfle.qt_measurement import QtMeasurementSource

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    grid, ids, _, _ = setup()
    widgets = {identifier: qtwidgets.QLabel("Native Qt label " + str(index))
               for index, identifier in enumerate(ids)}
    try:
        source = QtMeasurementSource(widgets, qtcore=qtcore)
        result = run(grid, ids, source)
        assert len(result.placements) == 2
        assert all(item.height > 0 for item in result.placements)
        assert result.placements[1].x == 402
    finally:
        for widget in widgets.values():
            widget.deleteLater()


def test_tk_measurement_uses_actual_tcl_widget_requested_size():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("Native Tk widget requires X11 display")
    import tkinter as tk
    from psx.sfle.tk_measurement import TkMeasurementSource

    root = tk.Tk()
    root.withdraw()
    grid, ids, _, _ = setup()
    widgets = {identifier: tk.Label(root, text="Native Tk label " + str(index))
               for index, identifier in enumerate(ids)}
    try:
        result = run(grid, ids, TkMeasurementSource(widgets))
        assert len(result.placements) == 2
        assert all(item.height > 0 for item in result.placements)
    finally:
        root.destroy()


def test_kivy_measurement_uses_real_label_texture():
    pytest.importorskip("kivy")
    from kivy.uix.label import Label
    from psx.sfle.kivy_measurement import KivyMeasurementSource

    grid, ids, _, _ = setup()
    widgets = {identifier: Label(text="Native Kivy label " + str(index))
               for index, identifier in enumerate(ids)}
    for widget in widgets.values():
        widget.texture_update()
    result = run(grid, ids, KivyMeasurementSource(widgets))
    assert len(result.placements) == 2
    assert all(item.height > 0 for item in result.placements)
