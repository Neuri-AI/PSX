"""Explicit portable HTML-like aliases for the PSX markup resolver.

Aliases lower to existing native component VNode types. They must not be
registered as new native host types: doing so would falsify the backend
capability census. Generic flow tags need their own Cinnamon contexts.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

from psx.core.registry import ComponentDefinition
from psx.core.vnode import Image, Text, VNode, create_element
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


def _html_div(*children: object, display: str = "block", key: str | int | None = None, **props: object) -> VNode:
    """Preserve a true block host in the VNode tree; never alias to Flex."""
    if display not in ("block", "inline"):
        raise ValueError("div display overrides require the native formatting-context port")
    # Creating a VNode is not evidence that a native renderer can mount it.
    allowed = {"layout_width", "layout_height", "ref"}
    unsupported = set(props) - allowed
    if unsupported:
        raise ValueError(f"Unsupported div properties: {sorted(unsupported)}")
    resolve_display("div", display)
    return create_element("div", *children, key=key, display=display, **props)



# Generic HTML-like boxes remain explicit VNode identities rather than
# aliases to existing Flex/Box components. The verified formatting subset
# currently includes block containers and measured inline text fragments.
_BLOCK_TAGS = frozenset({
    "div", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "main", "header", "footer", "form", "ul", "li",
})
_INLINE_TAGS = frozenset({"span", "label"})
FORMATTING_TAGS = _BLOCK_TAGS | _INLINE_TAGS
_HEADING_FONT_SIZES = {
    "h1": 32, "h2": 28, "h3": 24, "h4": 20, "h5": 18, "h6": 16,
}


def _inline_text_fragments(node: VNode) -> tuple[VNode, ...]:
    """Prepare measured, breakable text words, retaining native font styling."""
    if node.type != "Text":
        return (node,)
    raw = node.props["value"]
    if not isinstance(raw, str):
        raise TypeError("Inline text must have a string value.")
    words = re.findall(r"\S+\s*|\s+", re.sub(r"\s+", " ", raw))
    preserved = {name: value for name, value in node.props.items()
                 if name not in ("value", "ref")}
    return tuple(Text(word, **preserved) for word in words if word.strip())


def _formatting_host(
    tag: str, *children: object, key: str | int | None = None,
    display: str | None = None, **props: object,
) -> VNode:
    initial = "inline" if tag in _INLINE_TAGS else "block"
    selected = initial if display is None else display
    if selected not in ("inline", "block"):
        raise ValueError(
            f"{tag} display requires an implemented Block/Inline formatting context."
        )
    allowed = {"ref", "layout_width", "layout_height"}
    extra = set(props) - allowed
    if extra:
        raise ValueError(f"Unsupported {tag} properties: {sorted(extra)}")
    resolve_display(tag, selected)
    if tag == "li" and not children:
        raise ValueError("li requires content to render a list item.")
    normalized = []
    for child in children:
        if tag in ("span", "label", "li") and isinstance(child, VNode) and child.type == "Text":
            normalized.extend(_inline_text_fragments(child))
        elif tag in _HEADING_FONT_SIZES and isinstance(child, VNode) and child.type == "Text":
            options = {
                name: value for name, value in child.props.items()
                if name not in ("value", "font_size", "bold", "ref")
            }
            normalized.append(Text(
                child.props["value"], font_size=_HEADING_FONT_SIZES[tag],
                bold=True, **options,
            ))
        else:
            normalized.append(child)
    if tag == "li":
        # Marker and adjacent text form one measured inline run, rather than
        # converting the list item to Flex or asking native layouts to place it.
        marker = create_element(
            "span", Text("\u2022 "), display="inline",
        )
        normalized.insert(0, marker)
    return create_element(
        tag, *normalized, key=key, display=selected, **props,
    )


def _formatting_constructor(tag: str):
    def construct(*children: object, **props: object) -> VNode:
        return _formatting_host(tag, *children, **props)
    return construct


PORTABLE_HTML_ALIASES: Mapping[str, str] = {
    "button": "Button",
    "input": "Input",
    "textarea": "TextArea",
    "img": "Image",
    "div": "div",
    "span": "span",
    "p": "p",
    "h1": "h1", "h2": "h2", "h3": "h3",
    "h4": "h4", "h5": "h5", "h6": "h6",
    "section": "section", "main": "main",
    "header": "header", "footer": "footer",
    "form": "form", "label": "label", "ul": "ul", "li": "li",
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
    # Generic formatting boxes are private markup constructors. They must
    # never masquerade as registered legacy/native toolkit primitives.
    for tag in FORMATTING_TAGS:
        if tag not in result:
            constructor = _html_div if tag == "div" else _formatting_constructor(tag)
            result[tag] = ComponentDefinition(tag, constructor)
    return result
