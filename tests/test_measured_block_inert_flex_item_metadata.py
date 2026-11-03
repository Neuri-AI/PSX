"""Regression: Flex item metadata must not break semantic Block/Inline flow."""

import pytest

from psx.layout.contracts.errors import SFLECapabilityError
from psx.layout.fallback.measured_block_snapshot import compute_measured_block_snapshot
from psx.layout.contracts.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def _snapshot(leaf_style):
    constraints = LayoutConstraints(
        AvailableSize(320.0, True), AvailableSize(None, False)
    )
    intrinsic = IntrinsicSizes(50, 50, 20, 20, 50, 20, baseline=15)
    return LayoutInput(
        1, 1, WritingDirection.LTR, constraints,
        (
            LayoutNode("root", None, "div", (("display", "block"),)),
            LayoutNode("form", "root", "form", (("display", "block"),)),
            LayoutNode("field", "form", "Input", tuple(leaf_style)),
        ),
        (MeasuredBox("field", intrinsic, constraints, 1),),
    )


def test_native_form_control_ignores_flex_item_metadata_in_block_flow():
    reference = compute_measured_block_snapshot(_snapshot(()))
    decorated = compute_measured_block_snapshot(_snapshot((
        ("flex_grow", 1),
        ("flex_shrink", 0),
        ("flex_basis", "50%"),
        ("align_self", "center"),
        ("order", 7),
    )))
    assert dict(reference.boxes) == dict(decorated.boxes)


def test_unresolved_nonflex_layout_style_remains_rejected():
    with pytest.raises(SFLECapabilityError, match="unresolved layout styles"):
        compute_measured_block_snapshot(_snapshot((("position", "absolute"),)))
