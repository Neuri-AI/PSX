"""Explicit portable HTML-like aliases for the PSX markup resolver.

Aliases lower to existing native component VNode types. They must not be
registered as new native host types: doing so would falsify the backend
capability census. Generic flow tags need their own Cinnamon contexts.
"""
from __future__ import annotations

from collections.abc import Mapping

from psx.core.registry import ComponentDefinition
from psx.core.vnode import Image, VNode, create_element
from psx.sfle.display_context import resolve_display

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


def _html_div(*children: object, display: str = "block", **props: object) -> VNode:
    """Preserve a true block host in the VNode tree; never alias to Flex."""
    if display != "block":
        raise ValueError("div display overrides require the native formatting-context port")
    # Creating a VNode is not evidence that a native renderer can mount it.
    allowed = {"layout_width", "layout_height", "ref"}
    unsupported = set(props) - allowed
    if unsupported:
        raise ValueError(f"Unsupported div properties: {sorted(unsupported)}")
    resolve_display("div", display)
    return create_element("div", *children, display=display, **props)


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
    # The block host is markup-only until a renderer has a certified native
    # layout port. Do not mutate builtin_component_registry() here.
    if "div" not in result:
        result["div"] = ComponentDefinition("div", _html_div)
    return result
