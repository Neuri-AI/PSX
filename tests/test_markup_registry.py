from __future__ import annotations

import pytest

from psx import Text, component, psx
from psx.core.errors import MarkupSyntaxError
from psx.core.registry import builtin_component_registry
from psx.markup import clear_template_cache, compile_template


def test_registered_component_is_available_in_markup_without_parser_changes() -> None:
    @component
    def Card(title: str):
        return Text(f"Card: {title}")

    registry = builtin_component_registry()
    registry.register("Card", Card)
    tree = psx("<Column><Card title={title} /></Column>", scope={"title": "Ada"}, registry=registry)
    card = tree.children[0]
    assert card.type is Card
    assert card.props["title"] == "Ada"


def test_registry_isolation_controls_tag_resolution() -> None:
    @component
    def Card():
        return Text("card")

    first = builtin_component_registry()
    first.register("Card", Card)
    second = builtin_component_registry()
    assert psx("<Card />", registry=first).type is Card
    with pytest.raises(MarkupSyntaxError, match="Unknown PSX tag <Card>"):
        psx("<Card />", registry=second)


def test_template_cache_is_scoped_to_registry_identity_and_version() -> None:
    clear_template_cache()
    registry = builtin_component_registry()
    original = compile_template("<Text>ready</Text>", registry=registry)
    assert compile_template("<Text>ready</Text>", registry=registry) is original

    @component
    def Card():
        return Text("card")

    registry.register("Card", Card)
    updated = compile_template("<Text>ready</Text>", registry=registry)
    assert updated is not original
    assert compile_template("<Card />", registry=registry).render().type is Card

    equivalent_but_distinct = builtin_component_registry()
    assert compile_template("<Text>ready</Text>", registry=equivalent_but_distinct) is not updated


def test_registry_and_legacy_primitives_are_mutually_exclusive() -> None:
    with pytest.raises(TypeError, match="either primitives or registry"):
        compile_template("<Text>ready</Text>", primitives={"Text": Text}, registry=builtin_component_registry())
