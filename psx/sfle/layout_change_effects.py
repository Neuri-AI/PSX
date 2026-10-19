"""Internal dependency-effect classification for native layout scheduling.

This is a conservative, backend-neutral characterization of existing public
properties, not a CSS property registry and not a public styling API.
Unknown properties must invalidate layout rather than silently skip Cinnamon.
"""
from __future__ import annotations

from enum import Enum
from typing import Mapping


class ChangeEffect(str, Enum):
    PAINT = "paint"
    MEASUREMENT = "measurement"
    GEOMETRY = "geometry"
    STRUCTURE = "structure"
    INTERACTION = "interaction"


# Deliberately small: only these existing properties are certified as
# non-geometric for these component types. Expand solely with native evidence.
_PAINT_ONLY = frozenset({("Text", "color")})
_MEASUREMENT = frozenset({
    ("Text", "value"), ("Text", "font_size"),
    ("Text", "bold"), ("Text", "italic"),
    ("Button", "label"), ("Button", "font_size"),
    ("Image", "source"), ("Image", "width"), ("Image", "height"),
})
_INTERACTION_ONLY = frozenset({
    ("Text", "enabled"),
})
_LAYOUT_ITEM_FIELDS = frozenset({
    "flex_grow", "flex_shrink", "flex_basis", "align_self", "order",
    "layout_width", "layout_height",
    "layout_min_width", "layout_min_height",
    "layout_max_width", "layout_max_height",
    *(f"layout_{kind}_{side}" for kind in ("margin", "padding", "border")
      for side in ("top", "right", "bottom", "left")),
})
_STRUCTURE_FIELDS = frozenset({"key", "ref"})


def classify_change(component: str, property_name: str) -> ChangeEffect:
    """Return the conservative dependency effect of an existing property."""
    if property_name in _STRUCTURE_FIELDS:
        return ChangeEffect.STRUCTURE
    if (component, property_name) in _PAINT_ONLY:
        return ChangeEffect.PAINT
    if (component, property_name) in _MEASUREMENT:
        return ChangeEffect.MEASUREMENT
    if (component, property_name) in _INTERACTION_ONLY:
        return ChangeEffect.INTERACTION
    if property_name in _LAYOUT_ITEM_FIELDS:
        return ChangeEffect.GEOMETRY
    return ChangeEffect.GEOMETRY


def detached_literal(value: object) -> tuple[bool, object]:
    """Keep only scalar/tuple values; do not retain callbacks or native owners."""
    if value is None or type(value) in (str, int, float, bool):
        return True, value
    if type(value) is tuple:
        parts = tuple(detached_literal(part) for part in value)
        return all(ok for ok, _ in parts), tuple(value for _, value in parts)
    return False, None


def partition_dependency_signature(
    nodes: tuple[tuple[str, str, int, Mapping[str, object]], ...],
    constraints: object,
) -> tuple[tuple[object, object], bool]:
    """Produce immutable dependency and paint fingerprints for mounted nodes.

    Unrecognized or nonliteral values *disable* reuse. The caller owns the
    single successful signature and must clear it on teardown/invalidation.
    Node identifiers and handle ids are values, never strong references.
    """
    safe = True
    geometry = []
    paint = []
    for node_id, component, handle_id, props in nodes:
        dependencies = []
        for name, value in sorted(props.items()):
            valid, detached = detached_literal(value)
            safe &= valid
            if classify_change(component, name) is ChangeEffect.PAINT:
                paint.append((node_id, name, detached))
            else:
                # Measurement, geometry, structure and interaction stay in
                # the conservative signature until separately certified.
                dependencies.append((name, detached))
        geometry.append((node_id, component, handle_id, tuple(dependencies)))
    return ((constraints, tuple(geometry)), tuple(paint)), safe


def dirty_layout_nodes(
    previous: tuple[tuple[str, str, int, Mapping[str, object]], ...] | None,
    current: tuple[tuple[str, str, int, Mapping[str, object]], ...],
    *,
    constraints_changed: bool = False,
) -> frozenset[str] | None:
    """Identify changed mounted nodes; None means full-tree invalidation.

    This is a conservative *planning* primitive, not permission to skip a
    Cinnamon compute. It does not retain native widget or callback references.
    Structural changes, unstable identity or unrepresentable property values
    require whole-tree invalidation. Paint-only edits are excluded.
    """
    if previous is None or constraints_changed:
        return None
    if len(previous) != len(current):
        return None

    dirty: set[str] = set()
    seen: set[str] = set()
    for old, new in zip(previous, current):
        old_id, old_type, old_handle, old_props = old
        node_id, node_type, handle, props = new
        if (old_id, old_type, old_handle) != (node_id, node_type, handle):
            return None
        if node_id in seen:
            return None
        seen.add(node_id)
        old_names, new_names = set(old_props), set(props)
        for name in old_names | new_names:
            old_valid, old_value = detached_literal(old_props[name]) if name in old_props else (True, None)
            new_valid, new_value = detached_literal(props[name]) if name in props else (True, None)
            if not old_valid or not new_valid:
                return None
            if (name in old_props) != (name in props) or old_value != new_value:
                effect = classify_change(node_type, name)
                if effect is ChangeEffect.STRUCTURE:
                    return None
                if effect is not ChangeEffect.PAINT:
                    dirty.add(node_id)
    return frozenset(dirty)


def affected_flex_contexts(
    dirty_nodes: frozenset[str] | None,
    *,
    parent_by_id: Mapping[str, str | None],
    flex_node_ids: frozenset[str],
) -> frozenset[str] | None:
    """Conservatively find Flex contexts reachable from dirty nodes.

    The ancestor chain may influence size or sibling positions, so every
    ancestor Flex must be invalidated. Descendant Flex contexts are included
    because an upstream geometry change can alter their available size.
    Unrelated sibling Flex contexts are not *directly* dirty, but their final
    geometry must still be validated by the parent transaction.
    """
    if dirty_nodes is None:
        return None
    ids = set(parent_by_id)
    if not dirty_nodes <= ids or not flex_node_ids <= ids:
        return None
    children: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for node_id, parent in parent_by_id.items():
        if parent is not None:
            if parent not in ids or parent == node_id:
                return None
            children[parent].append(node_id)

    # Reject cycles anywhere in the mounted parent graph, including contexts
    # outside the immediately dirty chain.
    for node_id in ids:
        visited_path: set[str] = set()
        cursor: str | None = node_id
        while cursor is not None:
            if cursor in visited_path:
                return None
            visited_path.add(cursor)
            cursor = parent_by_id[cursor]
    if not dirty_nodes:
        return frozenset()

    affected: set[str] = set()
    for node_id in dirty_nodes:
        visited: set[str] = set()
        cursor: str | None = node_id
        while cursor is not None:
            if cursor in visited:
                return None
            visited.add(cursor)
            if cursor in flex_node_ids:
                affected.add(cursor)
            cursor = parent_by_id[cursor]

    stack = list(affected)
    visited_descendants: set[str] = set()
    while stack:
        current_id = stack.pop()
        if current_id in visited_descendants:
            continue
        visited_descendants.add(current_id)
        for child in children[current_id]:
            if child in flex_node_ids:
                affected.add(child)
            stack.append(child)
    return frozenset(affected)
