from __future__ import annotations

import pytest

from psx import Button, Column, Fragment, Row, Text, component
from psx.core.contracts import BUTTON_CONTRACT, INPUT_CONTRACT, TEXT_CONTRACT
from psx.core.errors import DuplicateComponentError, UnknownComponentError
from psx.core.registry import ComponentRegistry, builtin_component_registry
from psx.core.vnode import Input


def test_default_registry_registers_existing_builtins_without_gui_imports() -> None:
    registry = builtin_component_registry()
    assert registry.resolve("Column").constructor is Column
    assert registry.resolve("Row").constructor is Row
    assert registry.resolve("Text").constructor is Text
    assert registry.resolve("Button").constructor is Button
    assert registry.resolve("Input").constructor is Input
    assert registry.resolve("Fragment").constructor is Fragment
    assert registry.resolve("Text").contract is TEXT_CONTRACT
    assert registry.resolve("Button").contract is BUTTON_CONTRACT
    assert registry.resolve("Input").contract is INPUT_CONTRACT


def test_registration_conflicts_and_unknown_names_are_explicit() -> None:
    registry = ComponentRegistry()
    registry.register("Text", Text, contract=TEXT_CONTRACT)
    with pytest.raises(DuplicateComponentError, match="'Text'"):
        registry.register("Text", Text)
    with pytest.raises(UnknownComponentError, match="'Missing'"):
        registry.resolve("Missing")


def test_registries_and_snapshots_are_isolated() -> None:
    first = builtin_component_registry()
    second = builtin_component_registry()
    snapshot = first.snapshot()
    first.register("Custom", Text)
    assert "Custom" not in snapshot
    assert not second.contains("Custom")
    clone = first.clone()
    clone.register("Other", Text)
    assert not first.contains("Other")


def test_custom_component_can_be_registered_without_touching_builtins() -> None:
    @component
    def Card(title: str):
        return Text(title)

    registry = builtin_component_registry()
    definition = registry.register("Card", Card)
    assert registry.resolve("Card") is definition
    assert definition.constructor is Card
