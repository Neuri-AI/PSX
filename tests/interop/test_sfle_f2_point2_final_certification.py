"""Final SFLE point-2 certification of frozen CSS classification boundaries.

Proves that both backends consume the same public immutable normalized
snapshot and cannot silently diverge when a style enum is numeric or when
length spelling uses ordinary CSS normalization. Not an expansion of the
supported alpha CSS feature set. No skip, xfail or tolerance.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from test_sfle_f2_differential import _python_compute, _rects, _rust_compute, rust_binary


def snapshot_of(prop: str, value: str | float | int) -> LayoutInput:
    return LayoutInput(
        1, 812, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(240, True), AvailableSize(120, True)),
        (
            LayoutNode("root", None, "Flex", (
                ("direction", "row"), ("width", "240px"), ("height", "120px"),
                ("align_items", "flex-start"),
            )),
            LayoutNode("child", "root", "Box", (
                ("width", "31px"), ("height", "19px"), ("flex_basis", "31px"),
                ("min_width", "0px"), (prop, value),
            ) if prop not in {"width", "height", "flex_basis", "min_width"}
            else tuple({
                "width": "31px", "height": "19px",
                "flex_basis": "31px", "min_width": "0px",
                prop: value,
            }.items())),
        ),
        (),
    )


@pytest.mark.parametrize("property_name", (
    "direction", "wrap", "justify_content", "align_items", "align_self",
    "align_content", "overflow",
))
@pytest.mark.parametrize("number", (0, 1, 999))
def test_non_string_css_enumerations_cannot_silently_default(
    property_name, number, rust_binary,
):
    request = snapshot_of(property_name, number)
    py = _python_compute(request)
    rs = _rust_compute(rust_binary, request)
    for name, side in (("python", py), ("rust", rs)):
        assert side["ok"] is False, (
            "Invalid CSS enumeration silently fell back to default",
            name, property_name, number, side,
        )
        assert side["error"]["code"] == "SFLE_UNSUPPORTED_FEATURE"
        assert side["error"]["node_id"] == "child"
    assert (py["error"]["code"], py["error"]["node_id"]) == (
        rs["error"]["code"], rs["error"]["node_id"]
    )


@pytest.mark.parametrize("property_name",(
    "width", "height", "flex_basis", "min_width",
))
@pytest.mark.parametrize("value",(
    "  27PX  ", "  21.5px  ", "  50%  ", " AUTO ", " 18px",
))
def test_css_length_token_normalization_is_equivalent(
    property_name, value, rust_binary,
):
    request = snapshot_of(property_name, value)
    py = _python_compute(request)
    rs = _rust_compute(rust_binary, request)
    assert py["ok"] == rs["ok"], (
        "CSS length spelling accepted by only one engine",
        property_name, value, py.get("error"), rs.get("error"),
    )
    if not py["ok"]:
        assert (py["error"]["code"], py["error"]["node_id"]) == (
            rs["error"]["code"], rs["error"]["node_id"]
        )
        return
    assert _rects(py["result"]) == _rects(rs["result"]), (
        "Normalized CSS length geometry differs", property_name, value,
    )


@pytest.mark.parametrize("property_name,value",(
    ("width","none"), ("height","normal"), ("flex_basis","fit-content"),
    ("min_width","content"), ("layout_padding_top","max-content"),
))
def test_frozen_out_of_scope_length_keywords_have_matching_verdicts(
    property_name, value, rust_binary,
):
    request = snapshot_of(property_name,value)
    py = _python_compute(request)
    rs = _rust_compute(rust_binary, request)
    assert py["ok"] == rs["ok"],(
        "Out-of-scope CSS keyword silently accepted on only one backend",
        property_name,value,py.get("error"),rs.get("error"),
    )
    if not py["ok"]:
        assert (py["error"]["code"],py["error"]["node_id"]) == (
            rs["error"]["code"],rs["error"]["node_id"]
        )
