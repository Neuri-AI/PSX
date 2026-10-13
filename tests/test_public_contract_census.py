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


@pytest.mark.parametrize("name", sorted(
    name for name, definition in builtin_component_registry().snapshot().items()
    if definition.contract is not None
))
def test_public_child_policy_accepts_legal_content_and_rejects_illegal_content(name, request):
    """Exercise the public parser/builders rather than the policy label alone."""
    from psx import psx
    from psx.core.errors import InvalidChildError, MarkupSyntaxError
    from psx.core.vnode import Radio, Text
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature

    definition = builtin_component_registry().resolve(name)
    contract = definition.contract
    assert contract is not None
    policy = contract.child_policy
    attributes = {'Image': ' source="missing.png"', 'Radio': ' value="first"'}.get(name, '')
    if policy == 'none':
        node = psx(f'<{name}{attributes} />')
        assert node.type == name and node.children == ()
        with pytest.raises(MarkupSyntaxError):
            psx(f'<{name}{attributes}><Text>forbidden</Text></{name}>')
    elif policy in ('text', 'text-only'):
        node = psx(f'<{name}>legal content</{name}>')
        content_property = contract.content_property or 'value'
        assert node.props[content_property] == 'legal content'
        assert node.children == ()
        with pytest.raises(MarkupSyntaxError):
            psx(f'<{name}><Text>forbidden widget</Text></{name}>')
        with pytest.raises(MarkupSyntaxError):
            psx(f'<{name} {content_property}="explicit">duplicate</{name}>')
    elif policy == 'none-or-single':
        assert psx(f'<{name} />').children == ()
        child = Text('child')
        node = definition.constructor(child)
        assert node.children == (child,)
        with pytest.raises(InvalidChildError):
            definition.constructor(child, Text('extra'))
        with pytest.raises(MarkupSyntaxError):
            psx(f'<{name}><Text>one</Text><Text>two</Text></{name}>')
    else:
        assert policy == 'multiple'
        children = ((Radio('one'), Radio('two')) if name == 'RadioGroup'
                    else (Text('one'), Text('two')))
        assert definition.constructor().children == ()
        node = definition.constructor(*children)
        assert node.children == children
        with pytest.raises(InvalidChildError):
            definition.constructor(object())
    assert_feature(request, Feature(name, CONTRACT, 'child_policy', policy,
                                    'validate', applicability='shared'), node.type == name)
