"""Component definitions and isolated registries for future markup resolution.

This module deliberately does not alter the current markup compiler.  It
provides the typed, renderer-independent lookup seam that REF-M3 will consume.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .component import ComponentType
from .contracts import (
    BUTTON_CONTRACT,
    CHECKBOX_CONTRACT,
    COLUMN_CONTRACT,
    DIVIDER_CONTRACT,
    INPUT_CONTRACT,
    ROW_CONTRACT,
    SLIDER_CONTRACT,
    SPACER_CONTRACT,
    TEXT_CONTRACT,
    TEXTAREA_CONTRACT,
    ComponentContract,
)
from .errors import DuplicateComponentError, UnknownComponentError
from .vnode import VNode

ComponentConstructor = Callable[..., VNode] | ComponentType


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    """One named component constructor and its optional portable contract."""

    name: str
    constructor: ComponentConstructor
    contract: ComponentContract | None = None
    markup_integer_properties: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Component names must be non-empty strings.")
        if not callable(self.constructor):
            raise TypeError("Component constructors must be callable.")


class ComponentRegistry:
    """A mutable, instance-scoped registry with immutable lookup snapshots.

    Registries do not auto-import GUI packages and have no global mutable
    singleton.  ``version`` changes only after a successful registration and
    is reserved for resolver/template-cache isolation in REF-M3.
    """

    def __init__(self, definitions: Mapping[str, ComponentDefinition] | None = None) -> None:
        self._definitions: dict[str, ComponentDefinition] = {}
        self._version = 0
        for name, definition in (definitions or {}).items():
            if name != definition.name:
                raise ValueError(
                    "Registry mapping keys must match definition names.")
            self.register_definition(definition)

    @property
    def version(self) -> int:
        return self._version

    def register(
        self,
        name: str,
        constructor: ComponentConstructor,
        *,
        contract: ComponentContract | None = None,
    ) -> ComponentDefinition:
        definition = ComponentDefinition(name, constructor, contract)
        self.register_definition(definition)
        return definition

    def register_definition(self, definition: ComponentDefinition) -> None:
        if definition.name in self._definitions:
            raise DuplicateComponentError(
                f"Component {definition.name!r} is already registered.")
        self._definitions[definition.name] = definition
        self._version += 1

    def resolve(self, name: str) -> ComponentDefinition:
        try:
            return self._definitions[name]
        except KeyError as error:
            raise UnknownComponentError(
                f"Unknown component {name!r}.") from error

    def contains(self, name: str) -> bool:
        return name in self._definitions

    def snapshot(self) -> Mapping[str, ComponentDefinition]:
        """Return an immutable mapping suitable for deterministic resolution."""
        return MappingProxyType(dict(self._definitions))

    def clone(self) -> "ComponentRegistry":
        """Create an independent registry with the same definitions."""
        return ComponentRegistry(self.snapshot())


def builtin_component_registry() -> ComponentRegistry:
    """Create a fresh default registry populated with current built-ins.

    Importing this function imports only PSX core modules; GUI bindings remain
    lazy and optional. Every call returns an isolated registry.
    """
    from .native import Native
    from .vnode import (
        Button,
        Checkbox,
        Column,
        Divider,
        Fragment,
        Input,
        Row,
        Slider,
        Spacer,
        Text,
        TextArea,
    )

    registry = ComponentRegistry()
    registry.register_definition(ComponentDefinition(
        "Column", Column, contract=COLUMN_CONTRACT,
        markup_integer_properties=frozenset({"spacing", "padding"})))
    registry.register_definition(ComponentDefinition(
        "Row", Row, contract=ROW_CONTRACT,
        markup_integer_properties=frozenset({"spacing", "padding"})))
    registry.register("Text", Text, contract=TEXT_CONTRACT)
    registry.register("Button", Button, contract=BUTTON_CONTRACT)
    registry.register("Input", Input, contract=INPUT_CONTRACT)
    registry.register("Checkbox", Checkbox, contract=CHECKBOX_CONTRACT)
    registry.register("TextArea", TextArea, contract=TEXTAREA_CONTRACT)
    registry.register("Slider", Slider, contract=SLIDER_CONTRACT)
    registry.register("Spacer", Spacer, contract=SPACER_CONTRACT)
    registry.register("Divider", Divider, contract=DIVIDER_CONTRACT)
    registry.register("Fragment", Fragment)
    registry.register("Native", Native)

    return registry