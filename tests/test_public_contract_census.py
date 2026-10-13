"""Public contract smoke tests: no native execution claims are implied.

Every built-in portable contract contributes to this parametrized census.
These tests reject unknown surface drift and exercise validation defaults,
but do not replace the per-property native G5 behavior drivers.
"""
from __future__ import annotations

import pytest

from psx.core.registry import builtin_component_registry
from psx.core.errors import RendererCapabilityError


MANDATORY = {
    "Text": {"value": "hello"},
    "Button": {"label": "Go"},
    "Image": {"source": "not-loaded.png"},
    "Radio": {"value": "choice"},
}


@pytest.mark.parametrize("name", sorted(builtin_component_registry().snapshot()))
def test_public_contract_valid_defaults_and_rejects_unknown_properties(name):
    definition = builtin_component_registry().resolve(name)
    contract = definition.contract
    if contract is None:
        # Structural/raw native components do not publish a portable contract.
        assert name in {"Fragment", "Box", "Native"}
        return
    values = {**MANDATORY.get(name, {}), **contract.defaults}
    contract.validate(values)
    resolved = contract.with_defaults(values)
    for key, value in contract.defaults.items():
        assert resolved[key] == value
    with pytest.raises((ValueError, TypeError, KeyError, AttributeError, RendererCapabilityError)):
        contract.validate({**values, "__unregistered_property__": True})


@pytest.mark.parametrize("name", sorted(builtin_component_registry().snapshot()))
def test_contract_declared_events_are_properties_and_not_magic_methods(name):
    contract = builtin_component_registry().resolve(name).contract
    if contract is None:
        return
    assert contract.events <= contract.properties
    assert all(event.startswith("on_") for event in contract.events)
    assert contract.child_policy in {
        "none", "text", "text-only", "none-or-single", "multiple"
    }
