"""Scoped CSS source binding for PSX Markup, without native style ownership.

The source lives on immutable VNodes outside widget props. Computing a style
does not imply a backend can paint or lay out that property; the dispatch
contracts are separate.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from psx.core.vnode import NodeKind, VNode

from .cascade import ComputedStyle, StyleTarget, resolve_style
from .parser import Stylesheet, parse_stylesheet
from .properties import CssDeclaration, foundation_registry, expand_box_shorthand


@dataclass(frozen=True, slots=True)
class MarkupStyleSource:
    tag: str
    classes: frozenset[str] = frozenset()
    node_id: str | None = None
    inline: tuple[CssDeclaration, ...] = ()


def parse_markup_style(
    tag: str,
    *,
    class_value: object = None,
    id_value: object = None,
    inline_value: object = None,
) -> MarkupStyleSource:
    """Validate CSS-only markup attributes before they reach native builders."""
    if class_value is None:
        classes = frozenset()
    elif isinstance(class_value, str):
        names = class_value.split()
        if any(not _valid_identifier(name) for name in names):
            raise ValueError("CSS class must contain valid identifiers.")
        classes = frozenset(names)
    else:
        raise TypeError("CSS class must be a space-separated string.")
    if id_value is not None and (
        not isinstance(id_value, str) or not _valid_identifier(id_value)
    ):
        raise ValueError("CSS id must be a valid identifier.")
    inline: tuple[CssDeclaration, ...] = ()
    if inline_value is not None:
        if isinstance(inline_value, str):
            parsed = parse_stylesheet(f"div {{{inline_value}}}")
            if len(parsed.rules) != 1:
                raise ValueError("Invalid inline CSS declaration block.")
            inline = tuple(
                CssDeclaration(name, value)
                for name, value in parsed.rules[0].declarations
            )
        elif isinstance(inline_value, Mapping):
            registry = foundation_registry()
            inline = tuple(item for name, value in inline_value.items() for item in expand_box_shorthand(registry, name, value))
        else:
            raise TypeError("CSS style must be declaration text or a property mapping.")
    return MarkupStyleSource(tag, classes, id_value, inline)


def _valid_identifier(value: str) -> bool:
    import re

    return re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]*", value) is not None


def compute_markup_styles(
    root: VNode, stylesheet: str | Stylesheet | None = None, *,
    inherited: ComputedStyle | None = None,
    parent: StyleTarget | None = None,
) -> VNode:
    """Decorate immutable VNodes with computed styles and preserve all public props.

    CSS matching covers markup elements and builtin VNodes. Custom lexical
    component hosts remain opaque while inherited CSS can flow to children.
    """
    if stylesheet is None:
        sheet = Stylesheet(())
    elif isinstance(stylesheet, Stylesheet):
        sheet = stylesheet
    else:
        sheet = parse_stylesheet(stylesheet)

    def visit(node: VNode, inherited: ComputedStyle | None, parent: StyleTarget | None = None) -> VNode:
        if node.kind is NodeKind.FRAGMENT:
            return replace(node, children=tuple(visit(child, inherited, parent) for child in node.children))
        if node.kind is not NodeKind.HOST:
            return node
        source = node.css_source
        if source is not None and not isinstance(source, MarkupStyleSource):
            raise TypeError("Unexpected PSX CSS style source metadata.")
        if isinstance(source, MarkupStyleSource):
            target = StyleTarget(source.tag, source.classes, source.node_id, parent)
            inline = source.inline
        else:
            # Builtin VNodes created programmatically also participate in the
            # global CSS cascade. Unknown/lexical components retain an opaque
            # selector identity; their children still inherit text properties.
            native_types = {
                "Button", "Input", "TextArea", "Checkbox", "Radio",
                "Select", "Link", "Badge", "SpinBox", "Text", "Flex",
                "Grid", "GridItem", "Box", "Scroll", "Slider", "Spacer",
                "Divider", "Image", "ProgressBar", "RadioGroup", "Switch",
            }
            tag = node.type.lower() if node.type in native_types else "__legacy_psx_host__"
            target = StyleTarget(tag, parent=parent)
            inline = ()
        if source is not None and source.tag == "__psx_text_content__":
            # Text content is not an element in CSS: inherit from its parent.
            computed = resolve_style(Stylesheet(()), target, inherited=inherited)
        else:
            computed = resolve_style(sheet, target, inline=inline, inherited=inherited)
        children = tuple(visit(child, computed, target) for child in node.children)
        return replace(node, css_computed=computed, children=children)

    return replace(visit(root, inherited, parent), css_stylesheet=sheet)

def compute_expressive_markup_styles(root: VNode | None, links: tuple[str, ...]) -> VNode | None:
    """Resolve static markup links after expression lowering, without widgets."""
    from .sources import CssSourceManager
    if root is None:
        return None
    from .context import current_css_context
    context = current_css_context()
    paths = (*(context.stylesheets if context else ()), *links)
    stylesheet = CssSourceManager(context.resolver if context else None, root=context.root if context else ".").load(paths) if paths else None
    return compute_markup_styles(root, stylesheet)
