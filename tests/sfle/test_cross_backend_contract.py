"""P4.6: four-backend certification of the F2 single-SFLE-authority port.

Qt, Kivy and Tkinter use the actual SFLE NativeGeometryCommitter with
instrumented widget doubles; Headless uses the immutable SFLE rectangles
directly. Native UI widgets and production renderers are intentionally
*not* wired in F2: that is F3's responsibility.
"""
from dataclasses import replace
from types import SimpleNamespace
import threading

import pytest

from psx.sfle.adapter_contract import (
    SFLEAdapterPorts, derive_scroll_content_metrics, scroll_to_sfle_point,
    scroll_to_viewport_point, validate_adapter_commit,
)
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import IntrinsicSizes
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.worker_lifecycle import start_native_worker_layout
from test_native_worker_portable_regression import _UIQueue
from test_authority_regression import _nested_snapshot, _viewports


BACKENDS = ("qt", "kivy", "tkinter", "headless")
AXES = ("x", "y", "width", "height")
BINDINGS = {"outer-scroll": "content", "inner-scroll": "inner-content"}


class _QtWidget:
    def __init__(self):
        self.rect = None

    def setGeometry(self, x, y, width, height):
        self.rect = (x, y, width, height)


class _TkWidget:
    def __init__(self):
        self.rect = None

    def place(self, *, x, y, width, height):
        self.rect = (x, y, width, height)


class _KivyWidget:
    def __init__(self):
        self.pos = None
        self.size = None


def _ports(generation, *, calls, alive=True, bindings=BINDINGS):
    return SFLEAdapterPorts(
        current_generation=lambda: generation,
        nodes_alive=lambda _ids: alive,
        apply_rectangles=lambda result: calls.append(result),
        read_rectangles=lambda: {},
        scroll_content_root=lambda host: bindings.get(host),
    )


def _project_backend(backend, snapshot, result):
    """Project actual SFLE output, not a second layout calculation."""
    if backend == "headless":
        return {name: tuple(getattr(box.border, axis) for axis in AXES)
                for name, box in result.boxes}, "absolute"

    parents = {node.node_id: node.parent_id for node in snapshot.nodes}
    factory, geometry_backend = {
        "qt": (_QtWidget, GeometryBackend.QT),
        "kivy": (_KivyWidget, GeometryBackend.KIVY),
        "tkinter": (_TkWidget, GeometryBackend.TK),
    }[backend]
    widgets = {node_id: factory() for node_id, parent in parents.items()
               if parent is not None}
    nodes = tuple(SimpleNamespace(node_id=node.node_id, parent_id=node.parent_id)
                  for node in snapshot.nodes)
    NativeGeometryCommitter(geometry_backend, nodes, widgets)(result)
    output = {}
    for node_id, widget in widgets.items():
        if backend == "kivy":
            output[node_id] = (*widget.pos, *widget.size)
        else:
            output[node_id] = widget.rect
    return output, "parent-relative"


@pytest.mark.parametrize("backend", BACKENDS)
def test_P46_nested_scroll_uses_one_sfle_geometry_source_on_all_backends(backend):
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    original = result.boxes
    scrolls = _viewports()
    calls = []
    ports = _ports(snapshot.generation, calls=calls)

    assert validate_adapter_commit(snapshot, result, ports, scroll_viewports=scrolls) == (
        tuple(node.node_id for node in snapshot.nodes)
    )
    ports.apply_rectangles(result)
    assert calls == [result]
    applied, coordinate_space = _project_backend(backend, snapshot, result)
    borders = {name: box.border for name, box in result.boxes}

    if coordinate_space == "absolute":
        assert set(applied) == set(borders)
        for node_id, bounds in applied.items():
            assert bounds == tuple(getattr(borders[node_id], axis) for axis in AXES)
    else:
        assert set(applied) == set(borders) - {"root"}
        for node in snapshot.nodes:
            if node.parent_id is None:
                continue
            rect, parent = borders[node.node_id], borders[node.parent_id]
            expected_y = rect.y - parent.y
            if backend == "kivy":
                expected_y = parent.height - expected_y - rect.height
            expected = (rect.x-parent.x, expected_y, rect.width, rect.height)
            assert all(abs(actual-reference) <= 1.0
                       for actual, reference in zip(applied[node.node_id], expected)), (
                           backend, node.node_id, applied[node.node_id], expected
                       )

    outer, inner = scrolls
    outer_metrics = derive_scroll_content_metrics(
        snapshot, result, ports, outer, scroll_viewports=scrolls)
    inner_metrics = derive_scroll_content_metrics(
        snapshot, result, ports, inner, scroll_viewports=scrolls)
    assert inner_metrics.content_width >= 300
    assert inner_metrics.content_height >= 200
    assert outer_metrics.content_width < inner_metrics.content_width
    assert outer_metrics.content_height < inner_metrics.content_height

    for viewport in scrolls:
        root = borders[viewport.content_root_id]
        point = (borders["inner-overflow"].x, borders["inner-overflow"].y)
        projected = scroll_to_viewport_point(root, viewport, *point)
        assert scroll_to_sfle_point(root, viewport, *projected) == pytest.approx(
            point, abs=0.01)
    assert result.boxes == original


@pytest.mark.parametrize("backend", BACKENDS)
def test_P46_crossed_scroll_root_is_rejected_before_backend_commit(backend):
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    calls = []
    ports = _ports(snapshot.generation, calls=calls)
    outer, inner = _viewports()
    crossed = (replace(outer, content_root_id=inner.content_root_id),
               replace(inner, content_root_id=outer.content_root_id))
    with pytest.raises(SFLEError) as caught:
        validate_adapter_commit(snapshot, result, ports, scroll_viewports=crossed)
    assert caught.value.code is DiagnosticCode.INVALID_SNAPSHOT
    assert not calls, (backend, "backend received a forged geometry commit")


@pytest.mark.parametrize("backend", BACKENDS)
def test_P46_native_viewport_resize_only_changes_scroll_metrics(backend):
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    original = result.boxes
    outer, inner = _viewports()
    ports = _ports(snapshot.generation, calls=[])

    for width, height, dx, dy in ((80, 30, 17, 8),
                                  (40, 20, 1000, 1000),
                                  (400, 500, -20, -10)):
        changed_outer = replace(outer, viewport_width=width,
                                viewport_height=height, offset_x=dx, offset_y=dy)
        scope = (changed_outer, inner)
        outer_metrics = derive_scroll_content_metrics(
            snapshot, result, ports, changed_outer, scroll_viewports=scope)
        inner_metrics = derive_scroll_content_metrics(
            snapshot, result, ports, inner, scroll_viewports=scope)
        assert outer_metrics.max_offset_x == max(0, outer_metrics.content_width-width)
        assert outer_metrics.max_offset_y == max(0, outer_metrics.content_height-height)
        assert 0 <= outer_metrics.offset_x <= outer_metrics.max_offset_x
        assert 0 <= outer_metrics.offset_y <= outer_metrics.max_offset_y
        assert inner_metrics.content_width >= 300
        assert inner_metrics.content_height >= 200
        assert result.boxes == original, backend


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("native_override", (False, True), ids=("correct", "native-override"))
def test_P46_instrumented_worker_rejects_second_native_layout_for_every_backend(
    backend, native_override,
):
    snapshot = _nested_snapshot()
    original = PythonLayoutEngine().compute(snapshot).boxes
    engine = PythonLayoutEngine()
    ui = _UIQueue()
    scrolls = _viewports()
    observed = {
        "content": {"x": 10.0, "y": 5.0, "width": 15.0, "height": 10.0},
        "inner-content": {"x": 3.0, "y": 4.0, "width": 7.0, "height": 8.0},
    }
    before = {name: dict(rect) for name, rect in observed.items()}
    applications = []
    outcomes = []

    def apply(result):
        applications.append(result)
        for name in observed:
            rect = dict(result.boxes)[name].border
            if backend in ("qt", "tkinter"):
                observed[name] = {axis: round(getattr(rect, axis)) for axis in AXES}
            else:
                observed[name] = {axis: getattr(rect, axis) for axis in AXES}
        if native_override:
            observed["inner-content"]["width"] += 5.0

    def restore(saved):
        observed.clear()
        observed.update({name: dict(rect) for name, rect in saved.items()})

    handle = start_native_worker_layout(
        snapshot,
        compute=engine.compute, provisional=engine.compute_provisional,
        measure_on_ui=lambda _id, _width: IntrinsicSizes(0, 300, 20, 200, 300, 200),
        is_ui_thread=lambda: threading.get_ident() == ui.thread,
        current_generation=lambda: snapshot.generation,
        apply_geometry=apply,
        observed_geometry=lambda: {name: dict(rect) for name, rect in observed.items()},
        restore_geometry=restore,
        initial_widths={"inner-overflow": 300.0},
        post_to_ui=ui.post, on_finished=lambda result, err: outcomes.append((result, err)),
        nodes_alive=lambda ids: set(ids) == {node.node_id for node in snapshot.nodes},
        scroll_viewports=scrolls,
        scroll_content_root=lambda host: BINDINGS.get(host),
    )
    ui.drain(handle)
    assert len(applications) == len(outcomes) == 1
    assert applications[0].boxes == original
    returned, error = outcomes[0]
    if native_override:
        assert returned is None
        assert isinstance(error, SFLEError)
        assert error.code is DiagnosticCode.UNSUPPORTED_MEASUREMENT
        assert observed == before
    else:
        assert error is None
        assert returned is not None
        assert returned.boxes == original
        assert returned.geometry_commit_error is not None
        assert returned.geometry_commit_error <= 1.0
