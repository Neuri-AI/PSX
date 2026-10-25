"""Recursive Grid composition using Cinnamon as the only geometry authority.

Each Grid computes its own horizontal allocations before measuring descendants.
A nested Grid's intrinsic height is the output of its own Cinnamon plan, not a
native layout manager estimate. Native ports supply only terminal leaf metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Callable, Mapping
from psx.core.grid_contract import GRID_BREAKPOINTS
from typing import Protocol

from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind

from .grid_math import GridPackingError
from .grid_native_measurement import measure_grid_native
from .grid_flex_composition import ComposedFlex, prepare_composed_flex
from .grid_tree_measurement import PreparedGridMeasurement
from .grid_native_plan import GridNativePlacement
from .model import IntrinsicSizes, MeasuredBox, LayoutConstraints, AvailableSize
from .native_measurement import NativeMeasurementPort
from .native_layout_snapshot import prepare_native_layout_snapshot
from .measured_block_snapshot import compute_measured_block_snapshot
from psx.markup.html_aliases import FORMATTING_TAGS
from .native_layout_snapshot import path_identity


class NativeLeafMeasurement(Protocol):
    def __call__(self, item_id: str, node: NormalizedLayoutNode, width: float) -> IntrinsicSizes: ...


@dataclass(frozen=True, slots=True)
class ComposedFlow:
    prepared: object
    result: object
    content_height: float
    nested_grids: dict[str, "ComposedGrid"]




def nested_flow_grid_width(snapshot, node_id, width):
    """Resolve the containing content width for a Grid nested in CSS block flow."""
    from .lengths import LengthKind, parse_length
    by_id = {node.node_id: node for node in snapshot.nodes}
    chain = []
    parent_id = by_id[node_id].parent_id
    while parent_id is not None:
        ancestor = by_id[parent_id]
        chain.append(ancestor)
        parent_id = ancestor.parent_id
    available = width
    for ancestor in reversed(chain):
        style = dict(ancestor.style)
        containing = available
        explicit = style.get("layout_width")
        if explicit is not None:
            specified = parse_length(explicit)
            if specified.kind is LengthKind.PX:
                available = float(specified.value)
            elif specified.kind is LengthKind.PERCENT:
                available *= float(specified.value)
            elif specified.kind not in (LengthKind.AUTO, LengthKind.NONE):
                raise GridPackingError("Nested Grid containing width is not resolvable.")
            continue
        for group in ("margin", "border", "padding"):
            for side in ("left", "right"):
                value = style.get(f"layout_{group}_{side}")
                if value is None:
                    continue
                parsed = parse_length(value)
                if parsed.kind is LengthKind.PX:
                    available -= float(parsed.value)
                elif parsed.kind is LengthKind.PERCENT:
                    available -= containing * float(parsed.value)
                else:
                    raise GridPackingError("Nested Grid container edges require concrete lengths.")
        available = max(0.0, available)
    return available

def prepare_composed_flow(flow, *, width, generation, measure_leaf, engine,
                          viewport_constraints=None, measure_grid=None):
    """Measure an HTML block subtree using Cinnamon's flow layout kernel."""
    constraints = LayoutConstraints(AvailableSize(width, True),
                                    AvailableSize(None, False))
    prepared = prepare_native_layout_snapshot(
        flow, constraints, generation=generation,
        viewport_constraints=viewport_constraints,
    )
    normalized = prepared.css_geometry_snapshot()
    if normalized.nodes[0].component == "Flex":
        # Grid allocates a border-box width. An auto-sized CSS Flex host
        # must give Cinnamon its *content* width, excluding its own edges.
        # Otherwise stretched children paint across the parent's padding.
        from .lengths import Length, LengthKind
        root, *rest = normalized.nodes
        style = dict(root.style)
        if "layout_width" not in style and "width" not in style:
            def edge(group, side):
                value = style.get(f"layout_{group}_{side}")
                if value is None:
                    return 0.0
                if isinstance(value, Length):
                    if value.kind is LengthKind.PX:
                        return float(value.value)
                    if value.kind is LengthKind.PERCENT:
                        return width * float(value.value)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
                raise GridPackingError(
                    "CSS Flex auto-width edges must resolve against GridItem width."
                )
            horizontal = sum(
                edge(group, side)
                for group in ("padding", "border")
                for side in ("left", "right")
            )
            style["layout_width"] = max(0.0, width - horizontal)
            normalized = replace(
                normalized, nodes=(
                    replace(root, style=tuple(sorted(style.items()))), *rest
                ),
            )
    if normalized.nodes[0].component not in (*FORMATTING_TAGS, "Flex"):
        raise GridPackingError("GridItem flow root must retain block or CSS Flex semantics.")
    identities = {}
    def visit(node):
        identities[path_identity(node.path)] = node
        for child in node.effective_children:
            visit(child)
    visit(flow)
    measurements = []
    nested_grids = {}
    for node in normalized.nodes[1:]:
        if node.component in FORMATTING_TAGS or node.component == "Flex":
            continue
        origin = identities[node.node_id]
        if origin.type == "Grid":
            if measure_grid is None:
                raise GridPackingError("Nested Grid flow requires a Cinnamon Grid measurement callback.")
            available = nested_flow_grid_width(normalized, node.node_id, width)
            nested = measure_grid(origin, available)
            nested_grids[node.node_id] = nested
            height = nested.content_height
            intrinsic = IntrinsicSizes(0, available, 0, height, available, height)
        else:
            if origin.effective_children:
                raise GridPackingError("Nested GridItem flow supports native leaves and Grid hosts.")
            intrinsic = measure_leaf(node.node_id, origin, width)
        if not isinstance(intrinsic, IntrinsicSizes):
            raise GridPackingError("GridItem flow leaf requires native IntrinsicSizes.")
        measurements.append(MeasuredBox(node.node_id, intrinsic,
            LayoutConstraints(AvailableSize(width, True),
                              AvailableSize(None, False)), generation))
    snapshot = replace(normalized, measurements=tuple(measurements))
    if normalized.nodes[0].component == "Flex":
        from .width_dependent_intrinsic_measurement import (
            compute_width_dependent, seed_unconstrained_width_measurements,
        )
        callbacks = {
            node.node_id: (
                lambda assigned_width, origin=identities[node.node_id]:
                    measure_leaf(path_identity(origin.path), origin, assigned_width)
            )
            for node in normalized.nodes[1:]
            if node.node_id in {item.node_id for item in measurements}
        }
        snapshot = seed_unconstrained_width_measurements(
            snapshot, frozenset(callbacks),
        )
        solved = compute_width_dependent(
            engine, snapshot, callbacks,
            current_generation=lambda: generation,
        )
    else:
        solved = compute_measured_block_snapshot(
            snapshot, flex_engine=engine,
            measure_width=lambda identifier, assigned_width: measure_leaf(
                identifier, identities[identifier], assigned_width,
            ),
        )
    root_id = normalized.nodes[0].node_id
    return ComposedFlow(prepared, solved, dict(solved.boxes)[root_id].border.height,
                        nested_grids)


@dataclass(frozen=True, slots=True)
class ComposedGrid:
    grid: NormalizedLayoutNode
    prepared: PreparedGridMeasurement
    nested: dict[str, "ComposedGrid"]
    nested_flex: dict[str, ComposedFlex]
    nested_flow: dict[str, ComposedFlow]
    nested_scroll: dict[str, tuple[ComposedFlow, float, float, float]]
    content_height: float


def prepare_composed_grid(
    grid: NormalizedLayoutNode,
    *,
    content_width: float,
    generation: int,
    current_generation: int,
    measure_leaf: NativeLeafMeasurement,
    is_ui_thread: Callable[[], bool],
    breakpoints: Mapping[str, object] = GRID_BREAKPOINTS,
    engine: object | None = None,
    viewport_constraints: LayoutConstraints | None = None,
) -> ComposedGrid:
    """Measure nested Grid children bottom-up using parent-allocated widths.

    Resolved Grid widths are recomputed on each transaction, independently of
    viewport width. Only a single primitive or nested Grid is currently a
    valid GridItem content root; unsupported Flex/Scroll stays fail-closed.
    """
    if grid.kind is not NodeKind.HOST or grid.type != "Grid":
        raise GridPackingError("Nested composition requires an explicit Grid host.")
    if not is_ui_thread():
        raise GridPackingError("Grid composition requires the renderer UI thread.")
    participants = grid.effective_children
    child_by_id = {}
    for item in participants:
        if item.kind is not NodeKind.HOST or item.type != "GridItem":
            raise GridPackingError("Grid composition requires direct GridItem children.")
        effective = item.effective_children
        if len(effective) != 1:
            raise GridPackingError("GridItem requires exactly one content root.")
        child_by_id[path_identity(item.path)] = effective[0]
    nested: dict[str, ComposedGrid] = {}
    nested_flex: dict[str, ComposedFlex] = {}
    nested_flow: dict[str, ComposedFlow] = {}
    nested_scroll: dict[str, tuple[ComposedFlow, float, float]] = {}

    class Source:
        def port(self):
            return NativeMeasurementPort(
                is_ui_thread,
                lambda request: MeasuredBox(
                    request.node_id,
                    self.measure_width(request.node_id, request.constraints.width.value),
                    request.constraints,
                    request.revision,
                ),
            )

        def measure_width(self, identifier, width):
            child = child_by_id[identifier]
            if child.kind is NodeKind.HOST and child.type == "Scroll":
                if engine is None:
                    raise GridPackingError("Scroll-in-Grid requires Cinnamon layout.")
                roots = child.effective_children
                if len(roots) != 1 or roots[0].type not in FORMATTING_TAGS:
                    raise GridPackingError(
                        "GridItem Scroll requires one HTML-like block content root."
                    )
                from .lengths import LengthKind, parse_length, resolve_viewport_length
                source = child.source.props
                requested = source.get("layout_height", source.get("height"))
                flow = prepare_composed_flow(
                    roots[0], width=width, generation=generation,
                    measure_leaf=measure_leaf, engine=engine,
                    viewport_constraints=viewport_constraints,
                    measure_grid=lambda subgrid, grid_width:
                        prepare_composed_grid(
                            subgrid, content_width=grid_width,
                            generation=generation, current_generation=current_generation,
                            measure_leaf=measure_leaf, is_ui_thread=is_ui_thread,
                            breakpoints=breakpoints, engine=engine,
                            viewport_constraints=viewport_constraints,
                        ),
                )
                height = flow.content_height
                if requested is not None:
                    parsed = parse_length(requested)
                    if parsed.kind in (
                        LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX,
                    ):
                        if viewport_constraints is None or (
                            viewport_constraints.width.value is None
                            or viewport_constraints.height.value is None
                        ):
                            raise GridPackingError(
                                "Viewport-sized Scroll needs definite window dimensions."
                            )
                        parsed = resolve_viewport_length(
                            parsed, viewport_constraints.width.value,
                            viewport_constraints.height.value,
                        )
                    if parsed.kind is not LengthKind.PX or parsed.value <= 0:
                        raise GridPackingError(
                            "GridItem Scroll height requires a definite positive size."
                        )
                    height = float(parsed.value)
                # A fixed-height CSS content root may still have descendants
                # overflowing its border box. Scroll extent is the union of
                # actual Cinnamon descendant rectangles, not just root height.
                # Preserve the root's CSS box geometry independently.
                from .model import Rect
                boxes = dict(flow.result.boxes)
                root_id = flow.prepared.snapshot.nodes[0].node_id
                origin_y = boxes[root_id].border.y
                extent = max(
                    (box.margin.y + box.margin.height - origin_y
                     for box in boxes.values()),
                    default=flow.content_height,
                )
                nested_scroll[identifier] = (flow, width, height, max(
                    height, flow.content_height, extent,
                ))
                return IntrinsicSizes(0, width, 0, height, width, height)
            if child.kind is NodeKind.HOST and child.type == "Grid":
                subgrid = prepare_composed_grid(
                    child, content_width=width, generation=generation,
                    current_generation=current_generation,
                    measure_leaf=measure_leaf, is_ui_thread=is_ui_thread,
                    breakpoints=breakpoints, engine=engine,
                    viewport_constraints=viewport_constraints,
                )
                nested[identifier] = subgrid
                height = subgrid.content_height
                return IntrinsicSizes(0, width, 0, height, width, height)
            if child.kind is NodeKind.HOST and child.type == "Flex":
                if engine is None:
                    raise GridPackingError(
                        "GridItem Flex requires the existing Cinnamon SFLE engine."
                    )
                flex = prepare_composed_flex(
                    child, content_width=width, generation=generation,
                    current_generation=current_generation,
                    measure_leaf=measure_leaf,
                    measure_grid=lambda nested_grid, nested_width:
                        prepare_composed_grid(
                            nested_grid, content_width=nested_width,
                            generation=generation, current_generation=current_generation,
                            measure_leaf=measure_leaf, is_ui_thread=is_ui_thread,
                            breakpoints=breakpoints, engine=engine,
                            viewport_constraints=viewport_constraints,
                        ),
                    is_ui_thread=is_ui_thread, engine=engine,
                )
                nested_flex[identifier] = flex
                height = flex.content_height
                return IntrinsicSizes(0, width, 0, height, width, height)
            if child.kind is NodeKind.HOST and child.type in FORMATTING_TAGS and child.effective_children:
                flow = prepare_composed_flow(
                    child, width=width, generation=generation,
                    measure_leaf=measure_leaf, engine=engine,
                    viewport_constraints=viewport_constraints,
                    measure_grid=lambda subgrid, grid_width:
                        prepare_composed_grid(
                            subgrid, content_width=grid_width,
                            generation=generation,
                            current_generation=current_generation,
                            measure_leaf=measure_leaf,
                            is_ui_thread=is_ui_thread,
                            breakpoints=breakpoints,
                            engine=engine,
                            viewport_constraints=viewport_constraints,
                        ),
                )
                nested_flow[identifier] = flow
                height = flow.content_height
                return IntrinsicSizes(0, width, 0, height, width, height)
            if child.kind not in (NodeKind.HOST, NodeKind.NATIVE) or child.effective_children:
                raise GridPackingError("Composite GridItem requires a supported nested Grid.")
            measured = measure_leaf(identifier, child, width)
            if not isinstance(measured, IntrinsicSizes):
                raise GridPackingError("Grid leaf must return actual IntrinsicSizes.")
            return measured

    ids = tuple(child_by_id)
    prepared = measure_grid_native(
        grid, content_width=content_width, source=Source(),
        mounted_ids=ids, revisions={identifier: generation for identifier in ids},
        generation=generation, current_generation=current_generation,
        allow_nested=True, breakpoints=breakpoints,
    )
    height = max((placement.y + placement.height for placement in prepared.placements),
                 default=0.0)
    return ComposedGrid(grid, prepared, nested, nested_flex, nested_flow, nested_scroll, height)


def compose_geometry_batch(
    composition: ComposedGrid,
    *,
    handles: dict[int, object],
    root_height: float,
) -> tuple[tuple[GridNativePlacement, ...], dict[str, object], dict[str, float]]:
    """Flatten local Cinnamon rectangles while retaining native parent boxes."""
    placements: list[GridNativePlacement] = []
    widgets: dict[str, object] = {}
    heights: dict[str, float] = {}

    def walk(grid: ComposedGrid, parent_height: float):
        children = {path_identity(item.path): item for item in grid.grid.effective_children}
        for placement in grid.prepared.placements:
            identifier = placement.node_id
            item = children[identifier]
            child = item.effective_children[0]
            placements.append(placement)
            widgets[identifier] = handles[id(item.source)]
            heights[identifier] = parent_height
            nested = grid.nested.get(identifier)
            if nested is not None:
                grid_id = identifier + "/grid"
                child_height = placement.used_height
                placements.append(GridNativePlacement(
                    grid_id, 0, 0, placement.used_width, child_height,
                    placement.used_width, child_height, False, False,
                ))
                widgets[grid_id] = handles[id(child.source)]
                heights[grid_id] = placement.height
                walk(nested, child_height)
            elif identifier in grid.nested_scroll:
                flow, scroll_width, scroll_height, scroll_extent = grid.nested_scroll[identifier]
                scroll_id = identifier + "/scroll"
                placements.append(GridNativePlacement(
                    scroll_id, 0, 0, placement.width, scroll_height,
                    placement.width, scroll_height, False, False,
                ))
                widgets[scroll_id] = handles[id(child.source)]
                heights[scroll_id] = placement.height
                content_root = child.effective_children[0]
                flow_id = scroll_id + "/content"
                # Keep overflow descendants inside a real native parent rect;
                # otherwise Qt clips them at the CSS content root's fixed
                # height before the Scroll viewport can reveal them.
                placements.append(GridNativePlacement(
                    flow_id, 0, 0, scroll_width, scroll_extent,
                    scroll_width, scroll_extent, False, False,
                ))
                widgets[flow_id] = handles[id(content_root.source)]
                heights[flow_id] = scroll_height
                boxes = dict(flow.result.boxes)
                nodes_by_id = {node.node_id: node for node in flow.prepared.snapshot.nodes}
                for source_id, source in flow.prepared.identities[1:]:
                    current = nodes_by_id[source_id]
                    rect = boxes[source_id].border
                    parent = boxes[current.parent_id].border
                    local_x, local_y = rect.x - parent.x, rect.y - parent.y
                    segment_id = flow_id + "/" + source_id
                    placements.append(GridNativePlacement(
                        segment_id, max(0.0, local_x), max(0.0, local_y),
                        rect.width, rect.height, rect.width, rect.height,
                        False, False,
                    ))
                    widgets[segment_id] = handles[id(source)]
                    heights[segment_id] = parent.height
                    nested_grid = flow.nested_grids.get(source_id)
                    if nested_grid is not None:
                        walk(nested_grid, rect.height)
            elif identifier in grid.nested_flow:
                flow = grid.nested_flow[identifier]
                flow_id = identifier + "/flow"
                placements.append(GridNativePlacement(
                    flow_id, 0, 0, placement.used_width, flow.content_height,
                    placement.used_width, flow.content_height, False, False,
                ))
                widgets[flow_id] = handles[id(child.source)]
                heights[flow_id] = placement.height
                boxes = dict(flow.result.boxes)
                for source_id, source in flow.prepared.identities[1:]:
                    current = next(node for node in flow.prepared.snapshot.nodes
                                   if node.node_id == source_id)
                    rect = boxes[source_id].border
                    parent = boxes[current.parent_id].border
                    local_x, local_y = rect.x - parent.x, rect.y - parent.y
                    segment_id = flow_id + "/" + source_id
                    placements.append(GridNativePlacement(
                        segment_id, max(0.0, local_x), max(0.0, local_y),
                        rect.width, rect.height, rect.width, rect.height,
                        False, False,
                    ))
                    widgets[segment_id] = handles[id(source)]
                    heights[segment_id] = parent.height
                    nested_grid = flow.nested_grids.get(source_id)
                    if nested_grid is not None:
                        walk(nested_grid, rect.height)
            elif identifier in grid.nested_flex:
                subflex = grid.nested_flex[identifier]
                flex_id = identifier + "/flex"
                placements.append(GridNativePlacement(
                    flex_id, 0, 0, placement.used_width, placement.used_height,
                    placement.used_width, placement.used_height, False, False,
                ))
                widgets[flex_id] = handles[id(child.source)]
                heights[flex_id] = placement.height
                boxes = dict(subflex.result.boxes)
                identities = dict(subflex.prepared.identities)
                for node in subflex.prepared.snapshot.nodes[1:]:
                    rect = boxes[node.node_id].border
                    parent = boxes[node.parent_id].border
                    local_x, local_y = rect.x - parent.x, rect.y - parent.y
                    segment_id = flex_id + "/" + node.node_id
                    placements.append(GridNativePlacement(
                        segment_id, local_x, local_y, rect.width, rect.height,
                        rect.width, rect.height, False, False,
                    ))
                    widgets[segment_id] = handles[id(identities[node.node_id])]
                    heights[segment_id] = parent.height
                    nested_grid = subflex.nested_grids.get(node.node_id)
                    if nested_grid is not None:
                        walk(nested_grid, rect.height)
            else:
                leaf_id = identifier + "/leaf"
                placements.append(GridNativePlacement(
                    leaf_id, 0, 0, placement.used_width, placement.used_height,
                    placement.used_width, placement.used_height, False, False,
                ))
                widgets[leaf_id] = handles[id(child.source)]
                heights[leaf_id] = placement.height

    walk(composition, root_height)
    return tuple(placements), widgets, heights
