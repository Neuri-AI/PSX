"""Explicit portable HTML-like aliases for the PSX markup resolver.

Aliases lower to existing native component VNode types. They must not be
registered as new native host types: doing so would falsify the backend
capability census. Generic flow tags need their own Cinnamon contexts.
"""
from __future__ import annotations

from collections.abc import Mapping

from psx.core.registry import ComponentDefinition
from psx.core.vnode import Image, VNode

def _html_img(*children: object, src: str | None = None, source: str | None = None, **props: object) -> VNode:
    """Translate HTML src to the existing portable image source property."""
    if children:
        raise TypeError("img is a void element and cannot have children")
    if src is not None and source is not None:
        raise ValueError("img cannot specify both src and source")
    selected = src if src is not None else source
    if selected is None:
        raise ValueError("img requires src (or the legacy source property)")
    return Image(selected, **props)


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
            _html_img if alias == "img" else source.constructor,
            contract=source.contract,
            markup_integer_properties=source.markup_integer_properties,
        )
    return result
