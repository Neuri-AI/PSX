"""Mounted-component stylesheet inheritance without process-wide CSS state."""
from psx.core.vnode import NodeKind
from psx.css.cascade import ComputedStyle, StyleTarget
from psx.css.markup import MarkupStyleSource, compute_markup_styles
from psx.css.parser import Rule, Stylesheet


def inherit_component_styles(instance, result):
    ancestors = []
    parent = instance.parent
    while parent is not None:
        ancestors.append(parent)
        parent = parent.parent
    inherited_sheet = next(
        (node.node.css_stylesheet for node in ancestors
         if isinstance(node.node.css_stylesheet, Stylesheet)
         and node.node.css_stylesheet.rules), None
    )
    if inherited_sheet is None:
        return result
    local = result.css_stylesheet
    own_rules = local.rules if isinstance(local, Stylesheet) else ()
    sheet = Stylesheet(tuple(
        Rule(rule.selectors, rule.declarations, index)
        for index, rule in enumerate((*inherited_sheet.rules, *own_rules))
    ))
    target = None
    inherited = None
    for ancestor in reversed(ancestors):
        node = ancestor.node
        if node.kind is not NodeKind.HOST:
            continue
        source = node.css_source
        if isinstance(source, MarkupStyleSource):
            target = StyleTarget(source.tag, source.classes, source.node_id, target)
        else:
            target = StyleTarget(
                node.type.lower() if isinstance(node.type, str) else "",
                parent=target,
            )
        if isinstance(node.css_computed, ComputedStyle):
            inherited = node.css_computed
    return compute_markup_styles(result, sheet, inherited=inherited, parent=target)
