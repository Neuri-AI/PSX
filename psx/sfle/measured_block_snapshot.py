"""Renderer-neutral Cinnamon Block/Inline geometry over native measurements.

Only explicit semantic flow hosts participate. All text widths, line heights
and baselines arrive from renderer-native intrinsic ports. Block descendants
stack in normal flow; consecutive inline descendants form measured lines, and
their stable per-host rectangles are unions of the actual native fragments.
Unsupported widths, CSS styles and anonymous layout contexts fail closed.
"""
from __future__ import annotations

from collections import defaultdict

from psx.markup.html_aliases import FORMATTING_TAGS
from .errors import DiagnosticCode, SFLECapabilityError
from .flow_layout import InlineAtom, layout_inline_atoms
from .fixed_point import LayoutUnit
from .model import AvailableSize, BoxRect, LayoutConstraints, LayoutInput, LayoutNode, LayoutResult, Rect
from .lengths import Length, LengthKind, parse_length


def compute_measured_block_snapshot(snapshot: LayoutInput, *, flex_engine=None) -> LayoutResult:
    """Layout a bounded Block/Inline tree, retaining exact VNode identities."""
    if not snapshot.nodes or snapshot.nodes[0].component not in FORMATTING_TAGS:
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Measured flow formatting requires a semantic Block/Inline root.",
        )
    width = snapshot.constraints.width.value
    if width is None or not snapshot.constraints.width.definite:
        raise SFLECapabilityError(
            DiagnosticCode.LAYOUT_CONSTRAINT,
            "Measured flow formatting requires a definite containing width.",
        )
    root = snapshot.nodes[0]
    if root.parent_id is not None:
        raise SFLECapabilityError(
            DiagnosticCode.INVALID_TREE, "Flow root must have no parent.",
        )
    tree = {node.node_id: node for node in snapshot.nodes}
    children = defaultdict(list)
    for node in snapshot.nodes[1:]:
        children[node.parent_id].append(node)
    metrics = {item.node_id: item.intrinsic for item in snapshot.measurements}
    geometry: dict[str, Rect] = {}
    composed_boxes: dict[str, BoxRect] = {}
    containing_width: dict[str, float] = {}
    containing_height: dict[str, float | None] = {
        root.node_id: snapshot.constraints.height.value if snapshot.constraints.height.definite else None,
    }

    def quantized_rect(x: float, y: float, width: float, height: float) -> Rect:
        """Keep flow boxes on Cinnamon's shared 1/64 px geometry grid."""
        return Rect(*(LayoutUnit.from_nearest(value).to_px()
                      for value in (x, y, width, height)))


    def dimension(node, axis: str, available: float) -> float | None:
        value = dict(node.style).get("layout_" + axis)
        if value is None:
            return None
        length = parse_length(value)
        if length.kind is LengthKind.PX:
            return max(0.0, float(length.value))
        if length.kind is LengthKind.PERCENT:
            reference = (
                containing_height.get(node.node_id)
                if axis.endswith("height")
                else available
            )
            return None if reference is None else max(0.0, float(length.value) * reference)
        if length.kind in (LengthKind.AUTO, LengthKind.NONE):
            return None
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            f"Unsupported flow {axis} keyword.", node.node_id,
        )

    def constrained_dimension(node, axis: str, available: float, fallback: float) -> float:
        preferred = dimension(node, axis, available)
        result = fallback if preferred is None else preferred
        maximum = dimension(node, "max_" + axis, available)
        minimum = dimension(node, "min_" + axis, available)
        if maximum is not None:
            result = min(result, maximum)
        if minimum is not None:
            result = max(result, minimum)
        return max(0.0, result)

    def edges(node, prefix: str) -> tuple[float, float, float, float]:
        styles = dict(node.style)
        sides = []
        for side in ("top", "right", "bottom", "left"):
            value = styles.get(f"layout_{prefix}_{side}")
            if value is None:
                sides.append(0.0)
                continue
            length = parse_length(value)
            if length.kind is LengthKind.PX:
                resolved = float(length.value)
            elif length.kind is LengthKind.PERCENT:
                resolved = float(length.value) * containing_width.get(node.node_id, width)
            else:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    f"Unsupported flow {prefix} edge keyword.", node.node_id,
                )
            if prefix != "margin" and resolved < 0.0:
                raise SFLECapabilityError(
                    DiagnosticCode.INVALID_LENGTH,
                    f"Flow {prefix} edges cannot be negative.", node.node_id,
                )
            sides.append(resolved)
        return tuple(sides)

    def box_rect(node, content: Rect) -> BoxRect:
        def expand(rect: Rect, sides: tuple[float, float, float, float]) -> Rect:
            top, right, bottom, left = sides
            return quantized_rect(
                rect.x - left, rect.y - top,
                max(0.0, rect.width + left + right),
                max(0.0, rect.height + top + bottom),
            )
        padded = expand(content, edges(node, "padding"))
        bordered = expand(padded, edges(node, "border"))
        margin = expand(bordered, edges(node, "margin"))
        return BoxRect(content, padded, bordered, margin)

    def valid_style(node) -> bool:
        return set(dict(node.style)).issubset({"display", "layout_width", "layout_height", "layout_min_width", "layout_min_height", "layout_max_width", "layout_max_height", *(f"layout_{group}_{side}" for group in ("margin", "padding", "border") for side in ("top", "right", "bottom", "left"))})

    def display(node) -> str | None:
        if node.component not in FORMATTING_TAGS:
            return None
        style = dict(node.style)
        from psx.sfle.display_context import resolve_display, InnerDisplay
        selected = style.pop("display", None)
        mode = resolve_display(node.component, selected)
        if mode.inner is not InnerDisplay.FLOW or not valid_style(node):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"{node.component} requires a supported Block/Inline flow style.",
                node.node_id,
            )
        return mode.outer.value

    def leaf(node):
        if node.node_id not in metrics:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                f"Native flow child {node.node_id!r} is missing intrinsic measurements.",
                node.node_id,
            )
        if not valid_style(node):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Flow child {node.node_id!r} has unresolved layout styles.",
                node.node_id,
            )
        if children[node.node_id]:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Nested Block/Inline formatting for native child {node.node_id!r} "
                "requires an explicit nested format adapter.",
                node.node_id,
            )
        return metrics[node.node_id]

    def flex_node(node, x: float, y: float, available: float) -> float:
        """Compose a nested CSS Flex context using the selected Cinnamon engine."""
        from .backend import load_layout_engine

        selected_engine = flex_engine if flex_engine is not None else load_layout_engine()
        descendants = []
        pending = [node.node_id]
        selected = set()
        while pending:
            current = pending.pop()
            selected.add(current)
            pending.extend(child.node_id for child in children[current])
        # The parent supplies the available border-box width. For an
        # auto-sized nested Flex, Cinnamon must lay out its children within
        # the content box, leaving the Flex host's padding and border inside.
        horizontal_edges = sum(
            edges(node, group)[side]
            for group in ("padding", "border", "margin")
            for side in (1, 3)
        )
        for item in snapshot.nodes:
            if item.node_id in selected:
                style = dict(item.style)
                if item.node_id == node.node_id and "layout_width" not in style:
                    style["layout_width"] = Length.px(
                        max(0.0, available - horizontal_edges)
                    )
                descendants.append(LayoutNode(
                    item.node_id,
                    None if item.node_id == node.node_id else item.parent_id,
                    item.component, tuple(sorted(style.items())),
                ))
        constraints = LayoutConstraints(
            AvailableSize(available, True), AvailableSize(None, False),
        )
        local = LayoutInput(
            snapshot.schema_version, snapshot.generation, snapshot.direction,
            constraints, tuple(descendants),
            tuple(measured for measured in snapshot.measurements
                  if measured.node_id in selected),
        )
        solved = dict(selected_engine.compute(local).boxes)
        root_border = solved[node.node_id].border
        dx, dy = x - root_border.x, y - root_border.y
        for identifier, boxes in solved.items():
            def shift(rect):
                return quantized_rect(rect.x + dx, rect.y + dy,
                                      rect.width, rect.height)
            translated = BoxRect(*(shift(getattr(boxes, part))
                                   for part in ("content", "padding", "border", "margin")))
            composed_boxes[identifier] = translated
            geometry[identifier] = translated.content
        return solved[node.node_id].margin.height

    def inline_run(nodes, x: float, y: float, available: float) -> float:
        atoms = []
        owners = []
        fragments = []

        def collect(node):
            containing_width[node.node_id] = available
            mode = display(node)
            if mode is None:
                intrinsic = leaf(node)
                baseline = (intrinsic.baseline
                            if intrinsic.baseline is not None
                            else intrinsic.preferred_height)
                content_width = constrained_dimension(node, "width", available, intrinsic.preferred_width)
                content_height = constrained_dimension(node, "height", available, intrinsic.preferred_height)
                edge_groups = (edges(node, group) for group in ("margin", "border", "padding"))
                all_edges = tuple(edge_groups)
                horizontal = sum(group[1] + group[3] for group in all_edges)
                vertical = sum(group[0] + group[2] for group in all_edges)
                atoms.append(InlineAtom(
                    content_width + horizontal,
                    content_height + vertical,
                    min(max(0.0, baseline), content_height) + sum(group[0] for group in all_edges),
                ))
                fragments.append(node)
                return
            if mode != "inline":
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Block children cannot participate inside an Inline formatting run.",
                    node.node_id,
                )
            if any(
                edges(node, group) != (0.0, 0.0, 0.0, 0.0)
                for group in ("padding", "border", "margin")
            ):
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Inline formatting owners with box edges require fragment-aware layout.",
                    node.node_id,
                )
            owners.append(node)
            for sub in children[node.node_id]:
                containing_height[sub.node_id] = containing_height.get(node.node_id)
                collect(sub)

        for node in nodes:
            collect(node)
        placements = layout_inline_atoms(available, tuple(atoms))
        for node, place in zip(fragments, placements):
            edge_groups = tuple(edges(node, group) for group in ("margin", "border", "padding"))
            offset_x = sum(group[3] for group in edge_groups)
            offset_y = sum(group[0] for group in edge_groups)
            horizontal = sum(group[1] + group[3] for group in edge_groups)
            vertical = sum(group[0] + group[2] for group in edge_groups)
            geometry[node.node_id] = quantized_rect(
                x + place.x + offset_x, y + place.y + offset_y,
                max(0.0, place.width - horizontal),
                max(0.0, place.height - vertical),
            )
        for owner in reversed(owners):
            descendants = [geometry[child.node_id]
                           for child in children[owner.node_id]
                           if child.node_id in geometry]
            if not descendants:
                geometry[owner.node_id] = quantized_rect(x, y, 0, 0)
                continue
            left = min(box.x for box in descendants)
            top = min(box.y for box in descendants)
            right = max(box.x + box.width for box in descendants)
            bottom = max(box.y + box.height for box in descendants)
            geometry[owner.node_id] = quantized_rect(
                left, top, right - left, bottom - top,
            )
        return max((place.y + place.height for place in placements), default=0.0)

    def block_node(node, x: float, y: float, available: float) -> float:
        containing_width[node.node_id] = available
        margin = edges(node, "margin")
        padding = edges(node, "padding")
        border = edges(node, "border")
        top = margin[0] + padding[0] + border[0]
        left = margin[3] + padding[3] + border[3]
        bottom = margin[2] + padding[2] + border[2]
        horizontal = sum(group[1] + group[3] for group in (margin, padding, border))
        content_available = max(0.0, available - horizontal)
        used_width = constrained_dimension(node, "width", available, content_available)
        content_x, content_y = x + left, y + top
        parent_height = dimension(node, "height", available)
        for child in children[node.node_id]:
            containing_height[child.node_id] = parent_height
        mode = display(node)
        if mode is None:
            intrinsic = leaf(node)
            used_width = constrained_dimension(node, "width", available, content_available)
            used_height = constrained_dimension(node, "height", available, intrinsic.preferred_height)
            geometry[node.node_id] = quantized_rect(content_x, content_y, used_width, used_height)
            return top + used_height + bottom
        if mode == "inline":
            if any(edges(node, part) != (0.0, 0.0, 0.0, 0.0)
                   for part in ("padding", "border", "margin")):
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Inline formatting owners with box edges require fragment-aware layout.",
                    node.node_id,
                )
            return inline_run((node,), x, y, available)
        cursor = 0.0
        pending = []

        def flush() -> None:
            nonlocal cursor
            if pending:
                cursor += inline_run(tuple(pending), content_x, content_y + cursor, used_width)
                pending.clear()

        for child in children[node.node_id]:
            if child.component == "Flex":
                flush()
                cursor += flex_node(child, content_x, content_y + cursor, used_width)
            elif display(child) == "inline" or (display(child) is None and child.component not in ("Text", "Grid")):
                pending.append(child)
            else:
                flush()
                cursor += block_node(child, content_x, content_y + cursor, used_width)
        flush()
        used_width = constrained_dimension(node, "width", available, content_available)
        used_height = constrained_dimension(node, "height", available, cursor)
        geometry[node.node_id] = quantized_rect(content_x, content_y, used_width, used_height)
        return top + used_height + bottom

    if display(root) == "inline":
        content_height = inline_run(
            tuple(children[root.node_id]), 0.0, 0.0, width,
        )
    else:
        content_height = block_node(root, 0.0, 0.0, width)
    has_root_edges = any(
        edges(root, group) != (0.0, 0.0, 0.0, 0.0)
        for group in ("margin", "padding", "border")
    )
    if not has_root_edges:
        root_width = constrained_dimension(root, "width", width, width)
        root_height = constrained_dimension(root, "height", width, content_height)
        geometry[root.node_id] = quantized_rect(0.0, 0.0, root_width, root_height)

    result = tuple((node.node_id, composed_boxes.get(node.node_id)
                    or box_rect(node, geometry[node.node_id]))
                   for node in snapshot.nodes)
    return LayoutResult(snapshot.schema_version, snapshot.generation, result)
