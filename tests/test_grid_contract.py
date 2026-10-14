"""Behavioral contract tests for future native responsive Grid declarations."""
import pytest

from psx.core.errors import RendererCapabilityError
from psx.core.grid_contract import (
    GRID_BREAKPOINTS, normalize_grid_props, normalize_grid_item_props,
)


def test_grid_has_exactly_twelve_columns_and_default_gaps():
    assert dict(normalize_grid_props({})) == {
        "columns": 12, "gap": 0, "row_gap": 0, "column_gap": 0,
    }
    assert GRID_BREAKPOINTS == {
        "base": 0, "sm": 576, "md": 768, "lg": 992, "xl": 1200,
    }


def test_grid_item_defaults_to_distributive_auto_metadata():
    assert dict(normalize_grid_item_props({})) == {"span": "auto", "offset": 0}


def test_explicit_span_and_offset_are_accepted():
    assert dict(normalize_grid_item_props({"span": 8, "offset": 2})) == {
        "span": 8, "offset": 2,
    }


def test_responsive_maps_are_preserved_without_calculating_geometry():
    result = normalize_grid_item_props({
        "span": {"base": 12, "md": 8},
        "offset": {"base": 0, "md": 2},
    })
    assert dict(result["span"]) == {"base": 12, "md": 8}
    assert dict(result["offset"]) == {"base": 0, "md": 2}


@pytest.mark.parametrize("props", [
    {"columns": 11}, {"columns": True}, {"columns": 12.0},
    {"gap": -1}, {"gap": float("nan")}, {"gap": True},
    {"gap": "calc(2px)"}, {"unknown": 1},
])
def test_grid_rejects_invalid_properties(props):
    with pytest.raises(RendererCapabilityError):
        normalize_grid_props(props)


@pytest.mark.parametrize("props", [
    {"span": 0}, {"span": 13}, {"span": True},
    {"span": 1.5}, {"span": None}, {"offset": -1},
    {"offset": 12}, {"offset": False}, {"offset": 0.5},
    {"span": 12, "offset": 1}, {"unknown": 1},
    {"span": {"xxl": 4}}, {"span": {"md": 6}},
    {"offset": {"base": 0, "tablet": 1}},
    {"span": {}},
])
def test_grid_item_rejects_invalid_properties(props):
    with pytest.raises(RendererCapabilityError):
        normalize_grid_item_props(props)


def test_contract_normalization_does_not_mutate_caller_input():
    source = {"span": {"base": 12, "md": 6}}
    normalized = normalize_grid_item_props(source)
    assert source == {"span": {"base": 12, "md": 6}}
    with pytest.raises(TypeError):
        normalized["span"]["md"] = 4
