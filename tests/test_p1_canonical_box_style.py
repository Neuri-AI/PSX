"""Pure box-style normalization tests; no GUI runtime required."""
from __future__ import annotations

from types import MappingProxyType

import pytest

from psx.core.errors import RendererCapabilityError
from psx.sfle.canonical_box_style import (
    normalize_item_box_style,
    partition_item_box_style,
)
from psx.sfle.lengths import LengthKind


def test_defaults_are_immutable_unresolved_content_box_fields() -> None:
    style = normalize_item_box_style({})
    assert style.dimension("layout_width").kind is LengthKind.AUTO
    assert style.dimension("layout_max_width").kind is LengthKind.NONE
    assert style.margin.top.value == 0
    assert style.padding.left.value == 0
    assert style.border.right.value == 0


def test_legacy_native_width_is_not_reinterpreted() -> None:
    props = MappingProxyType({
        "source": "logo.png", "width": 48,
        "layout_width": "25%", "layout_padding_left": "10px",
        "layout_margin_top": "-4px",
    })
    native, style = partition_item_box_style(props, owner="Image")
    assert native == {"source": "logo.png", "width": 48}
    assert props["layout_width"] == "25%"
    assert style.dimension("layout_width").kind is LengthKind.PERCENT
    assert style.dimension("layout_width").value == 0.25
    assert style.padding.left.value == 10
    assert style.margin.top.value == -4


def test_unsupported_units_and_negative_padding_are_rejected() -> None:
    for invalid in ("2rem", "calc(1px + 1px)", True):
        with pytest.raises(RendererCapabilityError):
            normalize_item_box_style({"layout_width": invalid})
    with pytest.raises(RendererCapabilityError):
        normalize_item_box_style({"layout_padding_top": "-1px"})


def test_no_shared_mutable_defaults_and_identity_preserved() -> None:
    native1, first = partition_item_box_style({"label": "First"})
    native2, second = partition_item_box_style({"label": "Second"})
    native1["label"] = "Edited"
    assert native2 == {"label": "Second"}
    assert first == second
    assert first is not second


def test_namespaced_validation_does_not_accept_unknown_component_props() -> None:
    # Native validators remain authoritative; this function must never
    # pretend unknown component fields are valid portable host properties.
    native, _ = partition_item_box_style({"unknown_native_field": 123})
    assert native == {"unknown_native_field": 123}


def test_literal_box_cache_keeps_native_fields_private_and_revalidates_changes() -> None:
    from psx.sfle.canonical_box_style import _normalize_literal_fields

    _normalize_literal_fields.cache_clear()
    first = normalize_item_box_style({
        "layout_padding_left": "12px", "label": "First",
    })
    second = normalize_item_box_style({
        "layout_padding_left": "12px", "label": "Second",
    })
    assert first is not second
    assert first == second
    assert _normalize_literal_fields.cache_info().hits >= 1
    changed = normalize_item_box_style({
        "layout_padding_left": "16px", "label": "Second",
    })
    assert changed.padding.left.value == 16
    assert first.padding.left.value == 12
    with pytest.raises(RendererCapabilityError):
        normalize_item_box_style({"layout_padding_left": "-1px"})
    # Custom mappings keep their original uncached validation semantics.
    proxied = normalize_item_box_style(
        MappingProxyType({"layout_padding_left": "12px"}),
    )
    assert proxied == first
