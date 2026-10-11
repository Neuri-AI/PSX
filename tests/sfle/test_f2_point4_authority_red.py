"""F2 point 4: independent RED tests for SFLE-only geometry and Scroll boundaries.

This suite is intentionally introduced before any production contract changes.
No renderer, CSS capability or Rust/Python algorithm is modified.
"""
from dataclasses import replace
import threading

import pytest

from psx.sfle.adapter_contract import (
    SFLEAdapterPorts, ScrollViewport, derive_scroll_content_metrics,
    validate_adapter_commit,
)
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import LayoutNode
from psx.sfle.worker_lifecycle import start_native_worker_layout
from test_f2_adapter_authority_certification import _snapshot
from test_f2_native_worker_portable_red import _UIQueue


def _nested_snapshot():
    base = _snapshot()
    inner = LayoutNode("inner-content", "content", "Flex", (
        ("direction", "column"), ("width", "30px"), ("height", "20px"),
        ("flex_shrink", 0), ("align_items", "flex-start"),
    ))
    huge = LayoutNode("inner-overflow", "inner-content", "Box", (
        ("width", "300px"), ("height", "200px"), ("flex_basis", "200px"),
        ("flex_shrink", 0),
    ))
    return replace(base, nodes=(*base.nodes, inner, huge))


def _viewports():
    return (
        ScrollViewport("outer-scroll", "content", 80, 30, 17, 8),
        ScrollViewport("inner-scroll", "inner-content", 25, 15, 9, 7),
    )


def _ports(bindings=None, applied=None, observed=None):
    bindings = {"outer-scroll": "content", "inner-scroll": "inner-content"} if bindings is None else bindings
    return SFLEAdapterPorts(
        current_generation=lambda: 42,
        nodes_alive=lambda ids: True,
        apply_rectangles=(lambda result: applied.append(result)) if applied is not None else (lambda result: None),
        read_rectangles=(lambda: observed) if observed is not None else (lambda: {}),
        scroll_content_root=lambda host_id: bindings.get(host_id),
    )


def test_A_correct_independent_host_content_bindings_are_accepted():
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    assert validate_adapter_commit(
        snapshot, result, _ports(), scroll_viewports=_viewports(),
    ) == tuple(node.node_id for node in snapshot.nodes)


@pytest.mark.parametrize("bad_roots", [
    ("inner-content", "content"),
    ("inner-content", "inner-content"),
    ("content", "content"),
])
def test_A_crossed_or_forged_scroll_roots_fail_closed(bad_roots):
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    outer, inner = _viewports()
    forged = (replace(outer, content_root_id=bad_roots[0]),
              replace(inner, content_root_id=bad_roots[1]))
    with pytest.raises(SFLEError) as exc:
        validate_adapter_commit(snapshot, result, _ports(), scroll_viewports=forged)
    assert exc.value.code is DiagnosticCode.INVALID_SNAPSHOT


def test_B_offset_and_viewport_resize_change_only_scroll_metrics():
    snapshot = _snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    before = result.boxes
    for width, height, offset_x, offset_y in [
        (80, 30, 0, 0), (40, 20, 10, 12), (180, 110, 500, -10),
    ]:
        viewport = ScrollViewport("outer-scroll", "content", width, height, offset_x, offset_y)
        metrics = derive_scroll_content_metrics(snapshot, result, _ports(), viewport)
        assert 0 <= metrics.offset_x <= metrics.max_offset_x
        assert 0 <= metrics.offset_y <= metrics.max_offset_y
        assert metrics.max_offset_x == max(0, metrics.content_width-width)
        assert metrics.max_offset_y == max(0, metrics.content_height-height)
        assert result.boxes == before


def test_B_nested_scroll_overflow_must_not_expand_outer_viewport_content():
    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    before = result.boxes
    outer, inner = _viewports()
    metrics = derive_scroll_content_metrics(
        snapshot, result, _ports(), outer, scroll_viewports=(outer, inner),
    )
    # The inner 300x200 overflow belongs to inner-scroll, not outer-scroll.
    inner_metrics = derive_scroll_content_metrics(
        snapshot, result, _ports(), inner, scroll_viewports=(outer, inner),
    )
    assert inner_metrics.content_width >= 300
    assert inner_metrics.content_height >= 200
    assert metrics.content_width < inner_metrics.content_width
    assert metrics.content_height < inner_metrics.content_height
    assert result.boxes == before


def test_C_nested_viewport_projection_is_reversible_within_approved_precision():
    from psx.sfle.adapter_contract import scroll_to_sfle_point, scroll_to_viewport_point

    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    boxes = dict(result.boxes)
    outer, inner = _viewports()
    x, y = boxes["inner-overflow"].border.x, boxes["inner-overflow"].border.y
    inner_local = scroll_to_viewport_point(boxes["inner-content"].border, inner, x, y)
    assert scroll_to_sfle_point(boxes["inner-content"].border, inner, *inner_local) == pytest.approx((x, y), abs=0.01)
    outer_local = scroll_to_viewport_point(boxes["content"].border, outer, x, y)
    assert scroll_to_sfle_point(boxes["content"].border, outer, *outer_local) == pytest.approx((x, y), abs=0.01)
    # A reversed origin/offset may shift display pixels, never SFLE rectangles.
    assert result.boxes == PythonLayoutEngine().compute(snapshot).boxes


def test_C_foreign_scroll_transform_is_not_an_equivalent_coordinate_frame():
    from psx.sfle.adapter_contract import scroll_to_sfle_point, scroll_to_viewport_point

    snapshot = _nested_snapshot()
    result = PythonLayoutEngine().compute(snapshot)
    boxes = dict(result.boxes)
    outer, inner = _viewports()
    x, y = boxes["inner-overflow"].border.x, boxes["inner-overflow"].border.y
    projected = scroll_to_viewport_point(boxes["inner-content"].border, inner, x, y)
    wrong = scroll_to_sfle_point(boxes["content"].border, outer, *projected)
    assert max(abs(x-wrong[0]), abs(y-wrong[1])) > 1.0


@pytest.mark.parametrize("override", [False, True])
def test_D_instrumented_worker_ports_cannot_replace_SFLE_geometry_for_nested_scrolls(override):
    snapshot = _nested_snapshot()
    engine = PythonLayoutEngine()
    ui = _UIQueue()
    scrolls = _viewports()
    observed = {"content": {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
                "inner-content": {"x": 5.0, "y": 6.0, "width": 7.0, "height": 8.0}}
    original = {k: dict(v) for k, v in observed.items()}
    applied = []
    outcomes = []

    def apply(result):
        applied.append(result)
        for node_id in observed:
            rect = dict(result.boxes)[node_id].border
            observed[node_id] = {axis: getattr(rect, axis) for axis in ("x", "y", "width", "height")}
        if override:
            observed["inner-content"]["width"] += 5.0

    def restore(before):
        observed.clear()
        observed.update({name: dict(rect) for name, rect in before.items()})

    handle = start_native_worker_layout(
        snapshot, compute=engine.compute, provisional=engine.compute_provisional,
        measure_on_ui=lambda _id, _width: pytest.fail("No intrinsic measurement expected"),
        is_ui_thread=lambda: threading.get_ident() == ui.thread,
        current_generation=lambda: snapshot.generation,
        apply_geometry=apply,
        observed_geometry=lambda: {k: dict(v) for k, v in observed.items()},
        restore_geometry=restore,
        initial_widths={}, post_to_ui=ui.post,
        on_finished=lambda result, error: outcomes.append((result, error)),
        nodes_alive=lambda ids: set(ids) == set(node.node_id for node in snapshot.nodes),
        scroll_viewports=scrolls,
        scroll_content_root=lambda host_id: {"outer-scroll": "content", "inner-scroll": "inner-content"}.get(host_id),
    )
    ui.drain(handle)
    assert len(applied) == 1
    assert len(outcomes) == 1
    result, error = outcomes[0]
    if override:
        assert result is None
        assert isinstance(error, SFLEError)
        assert observed == original, "Unapproved native layout must roll back atomically"
    else:
        assert error is None
        assert result is not None
        assert applied[0].boxes == result.boxes
        assert result.geometry_commit_error <= 1.0
