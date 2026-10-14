"""Cinnamon Grid tree and native measurement handoff contracts."""
from __future__ import annotations

from dataclasses import replace
import pytest

from psx import Grid, GridItem, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.grid_math import GridPackingError, GridItemConstraints
from psx.sfle.grid_tree_measurement import prepare_grid_measurement
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from psx.sfle.native_layout_snapshot import path_identity


def tree():
    return normalize_flex_tree(Grid(
        GridItem(Text("one"), key="a", span={"base": 12, "md": 6}),
        GridItem(Text("two"), key="b", span={"base": 12, "md": 6}),
        gap=4,
    ))


def receipts(node, *, height_a=12, height_b=20):
    ids = tuple(path_identity(child.path) for child in node.effective_children)
    constraints = LayoutConstraints(AvailableSize(100, True), AvailableSize(None, False))
    measurements = tuple(
        MeasuredBox(identifier, IntrinsicSizes(0, 100, 0, height, 100, height),
                    constraints, index + 2)
        for index, (identifier, height) in enumerate(zip(ids, (height_a, height_b)))
    )
    return ids, measurements


def prepare(node=None, *, width=800, measurements=None, mounted=None, **kwargs):
    node = tree() if node is None else node
    ids, actual = receipts(node)
    return prepare_grid_measurement(
        node, content_width=width,
        measurements=actual if measurements is None else measurements,
        mounted_ids=ids if mounted is None else mounted,
        generation=7, current_generation=7, **kwargs,
    )


def test_native_measured_grid_tracks_keyed_identity_revision_and_row_height():
    result = prepare()
    assert result.child_ids == tuple(id for id, _ in result.measurement_revisions)
    assert tuple(revision for _, revision in result.measurement_revisions) == (2, 3)
    assert len(result.rows) == 1
    assert result.placements[0].width == 398
    assert result.placements[1].x == 402
    assert (result.placements[0].height, result.placements[1].height) == (12, 20)


def test_responsive_span_uses_grid_content_width_not_window_width():
    narrow = prepare(width=767)
    wide = prepare(width=768)
    assert len(narrow.rows) == 2
    assert len(wide.rows) == 1
    assert wide.placements[0].width == 382
    assert wide.placements[1].x == 386


def test_measurement_revision_and_height_changes_reflow_vertical_axis():
    node = tree()
    ids, actual = receipts(node, height_a=25, height_b=20)
    changed = replace(actual[0], revision=9)
    result = prepare(node, width=500, measurements=(changed, actual[1]))
    assert len(result.rows) == 2
    assert result.placements[1].y == 29
    assert result.measurement_revisions[0] == (ids[0], 9)


def test_grid_minimum_size_preserves_sibling_allocations():
    node = tree()
    ids, _ = receipts(node)
    result = prepare(node, constraints={ids[0]: GridItemConstraints(min_width=500)})
    assert result.placements[0].width == 398
    assert result.placements[0].used_width == 500
    assert result.placements[0].overflow_x
    assert result.placements[1].x == 402


@pytest.mark.parametrize("problem", ("missing", "duplicate", "foreign", "stale", "unmounted"))
def test_grid_handoff_fails_closed_on_incomplete_native_evidence(problem):
    node = tree()
    ids, measured = receipts(node)
    kwargs = dict(content_width=800, measurements=measured,
                  mounted_ids=ids, generation=7, current_generation=7)
    if problem == "missing":
        kwargs["measurements"] = measured[:1]
    elif problem == "duplicate":
        kwargs["measurements"] = (measured[0], measured[0])
    elif problem == "foreign":
        kwargs["measurements"] = (measured[0], replace(measured[1], node_id="foreign"))
    elif problem == "stale":
        kwargs["current_generation"] = 8
    else:
        kwargs["mounted_ids"] = ids[:1]
    with pytest.raises(GridPackingError):
        prepare_grid_measurement(node, **kwargs)


def test_empty_grid_requires_no_fabricated_measurements():
    node = normalize_flex_tree(Grid())
    result = prepare_grid_measurement(
        node, content_width=100, measurements=(), mounted_ids=(),
        generation=0, current_generation=0,
    )
    assert result.rows == () and result.placements == ()


def test_grid_handoff_rejects_unsupported_direct_child():
    node = normalize_flex_tree(Grid(GridItem(Text("one"))))
    child = node.effective_children[0]
    wrong = replace(child, source=Text("wrong"))
    with pytest.raises(GridPackingError):
        prepare_grid_measurement(
            replace(node, children=(wrong,)), content_width=100,
            measurements=(), mounted_ids=(), generation=0, current_generation=0,
        )
