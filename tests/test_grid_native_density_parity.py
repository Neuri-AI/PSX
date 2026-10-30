"""Retina native Grid geometry must use the same pixel units as CSS boxes."""
from __future__ import annotations

import pytest

from psx import Grid, GridItem, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.grid_tree_measurement import prepare_grid_measurement
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from psx.sfle.native_layout_snapshot import path_identity


def _grid_and_receipts():
    tree = Grid(
        GridItem(Text("Users"), span=6, key="users"),
        GridItem(Text("Sales"), span=6, key="sales"),
        gap="16px",
    )
    root = normalize_flex_tree(tree)._participating_roots()[0]
    identities = tuple(path_identity(child.path) for child in root.effective_children)
    receipts = tuple(
        MeasuredBox(
            identifier,
            IntrinsicSizes(10, 100, 10, 30, 100, 30),
            LayoutConstraints(
                AvailableSize(100, True), AvailableSize(None, False),
            ),
            1,
        ) for identifier in identities
    )
    return root, identities, receipts


@pytest.mark.parametrize("scale", (1.0, 1.5, 2.0, 3.0))
def test_grid_css_gap_is_scaled_once_for_native_drawable(scale):
    root, identifiers, receipts = _grid_and_receipts()
    result = prepare_grid_measurement(
        root, content_width=800, measurements=receipts, mounted_ids=identifiers,
        generation=1, current_generation=1, pixel_scale=scale,
    )
    first, second = result.placements
    assert second.x - (first.x + first.width) == pytest.approx(16 * scale, abs=1 / 64)
    assert first.width == pytest.approx((800 - 16 * scale) / 2, abs=1 / 64)
    assert second.width == pytest.approx(first.width, abs=1 / 64)


def test_grid_scale_rejects_invalid_and_bool_values():
    root, identifiers, receipts = _grid_and_receipts()
    for scale in (True, 0, -2, float("nan"), float("inf")):
        with pytest.raises(Exception, match="pixel scale"):
            prepare_grid_measurement(
                root, content_width=800, measurements=receipts,
                mounted_ids=identifiers, generation=1, current_generation=1,
                pixel_scale=scale,
            )
