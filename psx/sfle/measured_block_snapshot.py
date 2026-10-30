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
from .fixed_point import nearest_layout_px
from .model import AvailableSize, BoxRect, LayoutConstraints, LayoutInput, LayoutNode, LayoutResult, Rect
from .lengths import Length, LengthKind, parse_length


_FLOW_ALLOWED_STYLES = frozenset({
    "display", "layout_width", "layout_height",
    "layout_min_width", "layout_min_height",
    "layout_max_width", "layout_max_height",
    *(f"layout_{group}_{side}"
      for group in ("margin", "padding", "border")
      for side in ("top", "right", "bottom", "left")),
})


def compute_measured_block_snapshot(snapshot: LayoutInput, *, flex_engine=None,
                                    measure_width=None) -> LayoutResult:
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
    # A snapshot is immutable throughout this transaction. Resolve the
    # style tuples once, not on every edge/dimension/display query.
    style_by_id = {node.node_id: dict(node.style) for node in snapshot.nodes}
    edge_cache: dict[tuple[str, str, float], tuple[float, float, float, float]] = {}
    # Auto margins are resolved from remaining block inline space, not from
    # the CSS lexer. Keep their used values for the border/margin box receipt.
    resolved_block_margins: dict[str, tuple[float, float, float, float]] = {}
    display_cache: dict[str, str] = {}
    children = defaultdict(list)
    for node in snapshot.nodes[1:]:
        children[node.parent_id].append(node)
    # Most native snapshots are depth-first/preorder. Index that structure
    # once so a Flex subtree with k nodes costs O(k), not O(N) scans of
    # the entire Flow snapshot for each sibling Flex context. Preserve the
    # original order for unusual caller-supplied non-preorder snapshots.
    node_positions = {node.node_id: i for i, node in enumerate(snapshot.nodes)}
    subtree_end = {}
    preorder_stack = []
    preorder_valid = True
    for index, node in enumerate(snapshot.nodes):
        if index:
            while preorder_stack and preorder_stack[-1] != node.parent_id:
                subtree_end[preorder_stack.pop()] = index
            if not preorder_stack or preorder_stack[-1] != node.parent_id:
                preorder_valid = False
        preorder_stack.append(node.node_id)
    for node_id in preorder_stack:
        subtree_end[node_id] = len(snapshot.nodes)
    metrics = {item.node_id: item.intrinsic for item in snapshot.measurements}
    # Per-subtree Flex composition must not rescan every native measurement.
    # Keep source ordering metadata so atypical caller-supplied measurement
    # orders still produce exactly the same local LayoutInput as before.
    measurements_by_id = {item.node_id: item for item in snapshot.measurements}
    measurement_order = {
        item.node_id: i for i, item in enumerate(snapshot.measurements)
    }
    geometry: dict[str, Rect] = {}
    composed_boxes: dict[str, BoxRect] = {}
    containing_width: dict[str, float] = {}
    containing_height: dict[str, float | None] = {
        root.node_id: snapshot.constraints.height.value if snapshot.constraints.height.definite else None,
    }

    def quantized_rect(x: float, y: float, width: float, height: float) -> Rect:
        """Keep flow boxes on Cinnamon's shared 1/64 px geometry grid."""
        return Rect(
            nearest_layout_px(x), nearest_layout_px(y),
            nearest_layout_px(width), nearest_layout_px(height),
        )


    def dimension(node, axis: str, available: float) -> float | None:
        value = style_by_id[node.node_id].get("layout_" + axis)
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
        reference = containing_width.get(node.node_id, width)
        key = (node.node_id, prefix, reference)
        if key in edge_cache:
            return edge_cache[key]
        style = style_by_id[node.node_id]
        sides = []
        for side in ("top", "right", "bottom", "left"):
            value = style.get(f"layout_{prefix}_{side}")
            if value is None:
                sides.append(0.0)
                continue
            length = parse_length(value)
            if length.kind is LengthKind.PX:
                resolved = float(length.value)
            elif length.kind is LengthKind.PERCENT:
                resolved = float(length.value) * reference
            elif prefix == "margin" and length.kind is LengthKind.AUTO:
                # Used vertical auto margins are zero in normal block flow.
                # Horizontal auto margins are distributed by block_node once
                # the content width has been determined.
                resolved = 0.0
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
        result = tuple(sides)
        edge_cache[key] = result
        return result

    def box_rect(node, content: Rect) -> BoxRect:
        def expand(rect: Rect, sides: tuple[float, float, float, float]) -> Rect:
            # All source geometry is already on the 1/64px grid. Empty
            # edges preserve the exact same immutable rectangle, avoiding
            # three redundant quantization passes for every unstyled leaf.
            if sides == (0.0, 0.0, 0.0, 0.0):
                return rect
            top, right, bottom, left = sides
            return quantized_rect(
                rect.x - left, rect.y - top,
                max(0.0, rect.width + left + right),
                max(0.0, rect.height + top + bottom),
            )
        padded = expand(content, edges(node, "padding"))
        bordered = expand(padded, edges(node, "border"))
        margin = expand(
            bordered, resolved_block_margins.get(node.node_id, edges(node, "margin"))
        )
        return BoxRect(content, padded, bordered, margin)

    def valid_style(node) -> bool:
        return style_by_id[node.node_id].keys() <= _FLOW_ALLOWED_STYLES

    def display(node) -> str | None:
        if node.component not in FORMATTING_TAGS:
            return None
        if node.node_id in display_cache:
            return display_cache[node.node_id]
        from psx.sfle.display_context import resolve_display, InnerDisplay
        selected = style_by_id[node.node_id].get("display")
        mode = resolve_display(node.component, selected)
        if mode.inner is not InnerDisplay.FLOW or not valid_style(node):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"{node.component} requires a supported Block/Inline flow style.",
                node.node_id,
            )
        display_cache[node.node_id] = mode.outer.value
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
        if preorder_valid:
            local_nodes = snapshot.nodes[
                node_positions[node.node_id]:subtree_end[node.node_id]
            ]
        else:
            # Fallback retains original LayoutInput ordering even when a
            # caller has supplied a non-preorder but valid parent graph.
            pending = [node.node_id]
            selected = set()
            while pending:
                current = pending.pop()
                selected.add(current)
                pending.extend(child.node_id for child in children[current])
            local_nodes = sorted(
                (tree[item_id] for item_id in selected),
                key=lambda item: node_positions[item.node_id],
            )
        descendants = []
        # The parent supplies the available border-box width. For an
        # auto-sized nested Flex, Cinnamon must lay out its children within
        # the content box, leaving the Flex host's padding and border inside.
        horizontal_edges = sum(
            edges(node, group)[side]
            for group in ("padding", "border", "margin")
            for side in (1, 3)
        )
        for item in local_nodes:
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
        local_measurements = [
            measurements_by_id[item.node_id]
            for item in local_nodes if item.node_id in measurements_by_id
        ]
        # Preserve the original measurement tuple order on noncanonical
        # inputs. The usual preorder case never sorts.
        if any(measurement_order[a.node_id] > measurement_order[b.node_id]
               for a, b in zip(local_measurements, local_measurements[1:])):
            local_measurements.sort(key=lambda item: measurement_order[item.node_id])
        local = LayoutInput(
            snapshot.schema_version, snapshot.generation, snapshot.direction,
            constraints, tuple(descendants), tuple(local_measurements),
        )
        if measure_width is not None:
            from .width_dependent_intrinsic_measurement import (
                compute_width_dependent, seed_unconstrained_width_measurements,
            )
            # Nested CSS Flex rows receive their final assigned widths only
            # after Cinnamon's provisional pass. Seeded viewport-width text
            # metrics cannot be reused for wrapped paragraph labels.
            measured_ids = {metric.node_id for metric in local.measurements}
            parent_ids = {child.parent_id for child in local.nodes}
            width_ids = frozenset(
                item.node_id for item in local.nodes
                if item.node_id in measured_ids
                and item.node_id not in parent_ids
                and "layout_height" not in style_by_id[item.node_id]
                and item.component in ("Text", "p", "span")
            )
            if width_ids:
                local = seed_unconstrained_width_measurements(local, width_ids)
                result = compute_width_dependent(
                    selected_engine, local,
                    {identifier: (lambda width, identifier=identifier:
                                  measure_width(identifier, width))
                     for identifier in width_ids},
                    current_generation=lambda: snapshot.generation,
                )
            else:
                result = selected_engine.compute(local)
        else:
            result = selected_engine.compute(local)
        solved = dict(result.boxes)
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
        bottom = margin[2] + padding[2] + border[2]
        horizontal = sum(group[1] + group[3] for group in (margin, padding, border))
        content_available = max(0.0, available - horizontal)
        used_width = constrained_dimension(node, "width", available, content_available)

        # CSS 2.1 §10.3.3: distribute positive leftover inline space across
        # authored auto margins AFTER resolving the used content width. When
        # both sides are auto, center; one side absorbs all free space.
        # Block auto margins on the vertical axis resolve to zero. Flex auto
        # margins are already handled by the shared Rust/Python flex solver.
        margin_style = style_by_id[node.node_id]
        auto_left = (
            parse_length(margin_style["layout_margin_left"]).kind is LengthKind.AUTO
            if "layout_margin_left" in margin_style else False
        )
        auto_right = (
            parse_length(margin_style["layout_margin_right"]).kind is LengthKind.AUTO
            if "layout_margin_right" in margin_style else False
        )
        if auto_left or auto_right:
            remaining = max(0.0, content_available - used_width)
            share = remaining / (int(auto_left) + int(auto_right))
            margin = (
                margin[0], share if auto_right else margin[1],
                margin[2], share if auto_left else margin[3],
            )
            resolved_block_margins[node.node_id] = margin
        left = margin[3] + padding[3] + border[3]
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
            elif display(child) == "inline" or (display(child) is None and child.component not in ("Text", "Grid", "Native")):
                pending.append(child)
            else:
                flush()
                cursor += block_node(child, content_x, content_y + cursor, used_width)
        flush()
        used_width = constrained_dimension(node, "width", available, content_available)
        used_height = constrained_dimension(node, "height", available, cursor)
        # A native replaced widget in a height-constrained block should
        # receive the available content-box height rather than its unconstrained
        # sizeHint. Do not change explicit child heights or other flow siblings.
        # Qt can then resize an expanding PlotWidget while Cinnamon remains
        # the sole source of its native geometry.
        if used_height < cursor and dimension(node, "max_height", available) is not None:
            for child in children[node.node_id]:
                if child.component != "Native" or style_by_id[child.node_id].get("layout_height") is not None:
                    continue
                rect = geometry.get(child.node_id)
                if rect is None:
                    continue
                remaining = max(0.0, content_y + used_height - rect.y)
                if rect.height > remaining:
                    geometry[child.node_id] = quantized_rect(
                        rect.x, rect.y, rect.width, remaining,
                    )
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
