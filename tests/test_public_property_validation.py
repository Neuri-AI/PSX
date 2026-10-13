"""Deterministic positive and invalid property classes for all live contracts.

The corpus exercises portable validator semantics, *not* native readback.
A new declared property without a representative fails review instead of
inheriting a generic fabricated success.
"""
from __future__ import annotations

from collections.abc import Mapping

import pytest

from psx.core.errors import RendererCapabilityError
from psx.core.layout_item import FLEX_ITEM_PROPS
from psx.core.registry import builtin_component_registry
from tests.certification.public_behavior_census import Feature, CONTRACT, assert_feature


REQUIRED = {"Text": {"value": "Hello"}, "Button": {"label": "Go"},
            "Image": {"source": "missing-file.png"}, "Radio": {"value": "first"}}

ENUM_SAMPLE = {
    "direction": "column",
    "content_direction": "horizontal",
    "wrap": "wrap",
    "justify_content": "center",
    "align_items": "center",
    "align_content": "center",
    "align_self": "center",
    "align": "center",
    "orientation": "vertical",
    "fit": "cover",
    "scrollbar": "always",
    "variant": "success",
    "appearance": "outline",
    "size": "small",
    "shape": "pill",
    "color": "#123456",
    "href": "https://example.com",
}
NUMERIC_SAMPLE = {
    "value": 50, "min": -1, "max": 101, "step": 2,
    "font_size": 18, "decimals": 1, "spacing": 3, "thickness": 3,
    "width": 100, "height": 80, "padding": 4, "gap": "4px",
    "row_gap": "4px", "column_gap": "4px", "order": 1,
    "flex_grow": 1.5, "flex_shrink": 0.5,
}
TEXT_SAMPLE = {
    "value": "Changed", "label": "Changed", "source": "other-file.png",
    "alt": "Photo", "placeholder": "Please type",
}


def sample(component: str, name: str, default: object) -> object:
    if name.startswith(("on_",)):
        return lambda *args: args
    if name.startswith("layout_"):
        return "2px"
    if name == "flex_basis":
        return "20px"
    if name.startswith(("min_", "max_")) and component == "Flex":
        return "120px"
    if component == "Scroll" and name == "direction":
        return "horizontal"
    if name in ENUM_SAMPLE:
        return ENUM_SAMPLE[name]
    if name == "value" and component in {"Text", "Radio", "RadioGroup", "Select", "Input", "TextArea"}:
        return "Changed"
    if name == "options":
        return ["Changed", "Another"]
    if name == "checked" or isinstance(default, bool):
        return not bool(default)
    if name in NUMERIC_SAMPLE:
        return NUMERIC_SAMPLE[name]
    if name in TEXT_SAMPLE:
        return TEXT_SAMPLE[name]
    if default is None and name in ("width", "height"):
        return 100
    if name in ("max_width", "max_height", "min_width", "min_height"):
        return "120px"
    raise AssertionError(f"Missing reviewed value class for {component}.{name}")


def cases():
    rows = []
    for component, definition in builtin_component_registry().snapshot().items():
        contract = definition.contract
        if contract is None:
            continue
        props = set(contract.properties)
        if component != "Flex":
            props.update(FLEX_ITEM_PROPS)
        for name in sorted(props):
            rows.append((component, name))
    return rows


@pytest.mark.parametrize(("component", "property_name"), cases())
def test_advertised_property_has_positive_and_invalid_classes(component, property_name, request):
    contract = builtin_component_registry().resolve(component).contract
    assert contract is not None
    baseline = dict(contract.defaults)
    baseline.update(REQUIRED.get(component, {}))
    # Flex accepts the explicit layout_* spelling only as an alternative
    # to the native container size property.
    if component == "Flex" and property_name.startswith("layout_"):
        original = property_name.removeprefix("layout_")
        if original in ("width", "height", "min_width", "min_height",
                        "max_width", "max_height"):
            baseline.pop(original, None)
    value = sample(component, property_name, baseline.get(property_name))
    variant = {**baseline, property_name: value}
    contract.validate(variant)
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "valid_boundary", applicability="shared"),
                   contract.with_defaults(variant)[property_name] == value)
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "default", applicability="shared"),
                   all(contract.with_defaults(baseline)[key] == default
                       for key, default in contract.defaults.items()))

    invalid = {**baseline, property_name: object()}
    with pytest.raises((RendererCapabilityError, ValueError, TypeError)):
        contract.validate(invalid)
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "invalid_rejection", applicability="shared"), True)


def test_all_public_property_names_are_in_executable_value_corpus():
    expected = sum(
        len(set(definition.contract.properties) |
            (set() if name == "Flex" else FLEX_ITEM_PROPS))
        for name, definition in builtin_component_registry().snapshot().items()
        if definition.contract is not None
    )
    assert len(cases()) == expected
