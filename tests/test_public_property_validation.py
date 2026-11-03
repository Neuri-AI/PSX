"""Deterministic positive and invalid property classes for all live contracts.

The corpus exercises portable validator semantics, *not* native readback.
A new declared property without a representative fails review instead of
inheriting a generic fabricated success.
"""
from __future__ import annotations

import pytest

from psx.core.errors import RendererCapabilityError
from psx.core.layout_item import FLEX_ITEM_PROPS
from psx.core.registry import builtin_component_registry
from tests.certification.public_behavior_census import Feature, CONTRACT, assert_feature


REQUIRED = {"Text": {"value": "Hello"}, "Button": {"label": "Go"},
            "Image": {"source": "missing-file.png"}, "Radio": {"value": "first"}}

def cases():
    rows = []
    for component, definition in builtin_component_registry().snapshot().items():
        contract = definition.contract
        if contract is None:
            continue
        props = set(contract.properties)
        if component not in ("Flex", "Grid", "GridItem"):
            props.update(FLEX_ITEM_PROPS)
        for name in sorted(props):
            rows.append((component, name))
    return rows


@pytest.mark.parametrize(("component", "property_name"), cases())
def test_advertised_property_has_positive_and_invalid_classes(component, property_name, request):
    from tests.certification.public_property_cases import value_classes

    contract = builtin_component_registry().resolve(component).contract
    assert contract is not None
    baseline = dict(contract.defaults)
    baseline.update(REQUIRED.get(component, {}))
    if component == "Flex" and property_name.startswith("layout_"):
        baseline.pop(property_name.removeprefix("layout_"), None)
    valid, invalid = value_classes(component, property_name)
    minimum_valid = 1 if component == "Grid" and property_name == "columns" else 2
    assert len(valid) >= minimum_valid and len(invalid) >= 2
    for value in valid:
        variant = {**baseline, property_name: value}
        resolved = contract.with_defaults(variant)
        contract.validate_builder(variant)
        assert resolved[property_name] is value or resolved[property_name] == value
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "valid_boundary", applicability="shared"),
                   len(valid) >= minimum_valid)

    omitted = {key: value for key, value in baseline.items() if key != property_name}
    if property_name in REQUIRED.get(component, {}):
        with pytest.raises(RendererCapabilityError):
            contract.with_defaults(omitted)
        default_verified = property_name not in contract.defaults
    else:
        resolved = contract.with_defaults(omitted)
        default_verified = (resolved[property_name] == contract.defaults[property_name]
                            if property_name in contract.defaults else property_name not in resolved)
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "default", applicability="shared"), default_verified)

    rejected = 0
    for value in invalid:
        with pytest.raises((RendererCapabilityError, ValueError, TypeError)):
            contract.validate({**baseline, property_name: value})
        with pytest.raises((RendererCapabilityError, ValueError, TypeError)):
            contract.validate_builder({**baseline, property_name: value})
        rejected += 1
    assert_feature(request, Feature(component, CONTRACT, "property", property_name,
                                    "invalid_rejection", applicability="shared"),
                   rejected == len(invalid))


def test_all_public_property_names_are_in_executable_value_corpus():
    expected = sum(
        len(set(definition.contract.properties) |
            (set() if name in ("Flex", "Grid", "GridItem") else FLEX_ITEM_PROPS))
        for name, definition in builtin_component_registry().snapshot().items()
        if definition.contract is not None
    )
    assert len(cases()) == expected
