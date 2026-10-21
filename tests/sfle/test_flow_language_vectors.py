"""Shared executable geometry vectors for Python and Rust Cinnamon kernels."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from psx.sfle.flow_layout import (
    BlockItem, InlineAtom, layout_block_children, layout_inline_atoms,
)

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "flow_geometry_cases.json")
    .read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES["blocks"])
def test_block_geometry_matches_shared_language_vectors(case):
    placements = layout_block_children(
        case["available"], tuple(BlockItem(*items) for items in case["items"]),
    )
    assert [[item.x, item.y, item.width, item.height] for item in placements] == case["expected"]


@pytest.mark.parametrize("case", CASES["inline"])
def test_inline_geometry_matches_shared_language_vectors(case):
    placements = layout_inline_atoms(
        case["available"], tuple(InlineAtom(*items) for items in case["items"]),
    )
    assert [[item.x, item.y, item.width, item.height] for item in placements] == case["expected"]
