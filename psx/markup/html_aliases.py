"""Explicit portable HTML-like aliases for the PSX markup resolver.

Aliases lower to existing native component VNode types. They must not be
registered as new native host types: doing so would falsify the backend
capability census. Generic flow tags need their own Cinnamon contexts.
"""
from __future__ import annotations

from collections.abc import Mapping

from psx.core.registry import ComponentDefinition

PORTABLE_HTML_ALIASES: Mapping[str, str] = {
    "button": "Button",
    "input": "Input",
    "textarea": "TextArea",
    "img": "Image",
}


def markup_alias_definitions(
    definitions: Mapping[str, ComponentDefinition],
) -> dict[str, ComponentDefinition]:
    """Create scoped aliases without adding phantom native registry entries."""
    result = dict(definitions)
    for alias, native in PORTABLE_HTML_ALIASES.items():
        if native not in definitions or alias in result:
            continue
        source = definitions[native]
        result[alias] = ComponentDefinition(
            alias,
            source.constructor,
            contract=source.contract,
            markup_integer_properties=source.markup_integer_properties,
        )
    return result
