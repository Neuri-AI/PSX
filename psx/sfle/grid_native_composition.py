"""Recursive Grid composition using Cinnamon as the only geometry authority.

Each Grid computes its own horizontal allocations before measuring descendants.
A nested Grid's intrinsic height is the output of its own Cinnamon plan, not a
native layout manager estimate. Native ports supply only terminal leaf metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import OrderedDict
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





class FlowBlueprintReuse:
    """Bounded, renderer-owned reuse of immutable GridItem Flow structure.

    A viewport resize changes the input width/generation, not the mounted
    VNodes or their CSS projection. Cache only the *structural* snapshot;
    leaf measurements, width-dependent layout solves and native geometry
    are always fresh. No background work and no native handle retention.
    """

    def __init__(self, limit: int = 4096):
        self.limit = limit
        self._entries = OrderedDict()

    def clear(self):
        self._entries.clear()

    def prepare(self, flow, constraints, generation, viewport_constraints, epoch):
        # Include the actual normalized descendants, not just a parent
        # VNode. Nested component/hooks reconciliation may replace children
        # while retaining the outer element identity.
        # VNode props, resolved CSS and stylesheet are immutable snapshots.
        # The cached PreparedNativeLayoutSnapshot itself strongly retains
        # every VNode, so object identities cannot be recycled while an
        # entry remains live. Avoid serializing a complete CSS registry
        # through repr() for every descendant on every resize.
        from .lengths import Length, LengthKind
        viewport_kinds = {
            LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX,
        }
        viewport_suffixes = ("vw", "vh", "vmin", "vmax")

        def has_viewport_unit(value):
            if isinstance(value, Length):
                return value.kind in viewport_kinds
            return (isinstance(value, str)
                    and value.strip().lower().endswith(viewport_suffixes))

        fingerprint = []
        cacheable = True
        def visit(node):
            nonlocal cacheable
            origin = node.source
            fingerprint.append((
                node.path, id(origin), id(origin.props),
                id(origin.css_computed), id(origin.css_stylesheet),
                id(origin.css_source),
            ))
            if cacheable:
                computed = origin.css_computed
                if any(has_viewport_unit(value) for value in origin.props.values()):
                    cacheable = False
                elif computed is not None:
                    properties = getattr(computed, "properties", None)
                    specified = getattr(computed, "specified", ())
                    if properties is not None and any(
                        has_viewport_unit(properties[name])
                        for name in specified if name in properties
                    ):
                        cacheable = False
            for child in node.effective_children:
                visit(child)
        visit(flow)
        signature = tuple(fingerprint)
        key = (id(flow.source), path_identity(flow.path))
        cached = self._entries.get(key) if cacheable else None
        if cached is not None:
            retained_source, saved_signature, saved_epoch, saved_prepared, saved_css = cached
            if retained_source is flow.source and saved_signature == signature and saved_epoch == epoch:
                self._entries.move_to_end(key)
                prepared = replace(
                    saved_prepared,
                    snapshot=replace(
                        saved_prepared.snapshot, generation=generation,
                        constraints=constraints,
                    ),
                    viewport_constraints=viewport_constraints,
                )
                # The CSS root can change its width while retaining a
                # content-height-auto constraint. Preserve that height
                # definiteness, but rebind the current containing width.
                current_constraints = replace(
                    saved_css.constraints, width=constraints.width,
                )
                return prepared, replace(
                    saved_css, generation=generation,
                    constraints=current_constraints,
                )
        prepared = prepare_native_layout_snapshot(
            flow, constraints, generation=generation,
            viewport_constraints=viewport_constraints,
        )
        normalized = prepared.css_geometry_snapshot()
        if cacheable:
            self._entries[key] = (
                flow.source, signature, epoch, prepared, normalized,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
        return prepared, normalized


class _FlowContainingWidths:
    """Lazy O(N) aggregate width resolver for nested Grids in one Flow.

    The old implementation rebuilt a node index and walked every ancestor
    for every Grid: O(G*N + sum(depth)). Memoize each ancestor's content
    width once, while retaining exact CSS percentage reference semantics.
    Invalid styles are still checked only on ancestors of a requested Grid.
    """

    def __init__(self, snapshot, width):
        self.nodes = {node.node_id: node for node in snapshot.nodes}
        self.width = width
        self.after = {}

    def resolve(self, node_id):
        parent_id = self.nodes[node_id].parent_id
        if parent_id is None:
            return self.width
        ancestors = []
        current = parent_id
        while current is not None and current not in self.after:
            ancestors.append(current)
            current = self.nodes[current].parent_id
        available = self.after[current] if current is not None else self.width
        from .lengths import LengthKind, parse_length
        for ancestor_id in reversed(ancestors):
            style = dict(self.nodes[ancestor_id].style)
            containing = available
            explicit = style.get("layout_width")
            if explicit is not None:
                specified = parse_length(explicit)
                if specified.kind is LengthKind.PX:
                    available = float(specified.value)
                elif specified.kind is LengthKind.PERCENT:
                    available *= float(specified.value)
                elif specified.kind not in (LengthKind.AUTO, LengthKind.NONE):
                    raise GridPackingError(
                        "Nested Grid containing width is not resolvable."
                    )
                else:
                    explicit = None
            if explicit is None:
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
                            raise GridPackingError(
                                "Nested Grid container edges require concrete lengths."
                            )
                available = max(0.0, available)
            self.after[ancestor_id] = available
        return available


def nested_flow_grid_width(snapshot, node_id, width, *, resolver=None):
    """Resolve nested Grid containing width without repeating ancestor walks."""
    if resolver is None:
        resolver = _FlowContainingWidths(snapshot, width)
    return resolver.resolve(node_id)


def prepare_composed_flow(flow, *, width, generation, measure_leaf, engine,
                          viewport_constraints=None, measure_grid=None,
                          flow_reuse=None, invalidation_epoch=0):
    """Measure an HTML block subtree using Cinnamon's flow layout kernel."""
    constraints = LayoutConstraints(AvailableSize(width, True),
                                    AvailableSize(None, False))
    if flow_reuse is None:
        prepared = prepare_native_layout_snapshot(
            flow, constraints, generation=generation,
            viewport_constraints=viewport_constraints,
        )
        normalized = prepared.css_geometry_snapshot()
    else:
        prepared, normalized = flow_reuse.prepare(
            flow, constraints, generation, viewport_constraints,
            invalidation_epoch,
        )
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
    containing_widths = _FlowContainingWidths(normalized, width)
    # Reuse actual native leaf measurements only during this flow composition.
    # Subsequent commits and invalidations create a new cache.
    measured_leaves: dict[tuple[str, float], IntrinsicSizes] = {}

    def measure_flow_leaf(identifier, origin, leaf_width):
        key = (identifier, leaf_width)
        if key not in measured_leaves:
            measured_leaves[key] = measure_leaf(identifier, origin, leaf_width)
        return measured_leaves[key]

    for node in normalized.nodes[1:]:
        if node.component in FORMATTING_TAGS or node.component == "Flex":
            continue
        origin = identities[node.node_id]
        if origin.type == "Grid":
            if measure_grid is None:
                raise GridPackingError("Nested Grid flow requires a Cinnamon Grid measurement callback.")
            available = nested_flow_grid_width(
                normalized, node.node_id, width, resolver=containing_widths,
            )
            nested = measure_grid(origin, available)
            nested_grids[node.node_id] = nested
            height = nested.content_height
            intrinsic = IntrinsicSizes(0, available, 0, height, available, height)
        else:
            if origin.effective_children:
                raise GridPackingError("Nested GridItem flow supports native leaves and Grid hosts.")
            intrinsic = measure_flow_leaf(node.node_id, origin, width)
        if not isinstance(intrinsic, IntrinsicSizes):
            raise GridPackingError("GridItem flow leaf requires native IntrinsicSizes.")
        measurements.append(MeasuredBox(node.node_id, intrinsic,
            LayoutConstraints(AvailableSize(width, True),
                              AvailableSize(None, False)), generation))
    snapshot = replace(normalized, measurements=tuple(measurements))
    if normalized.nodes[0].component == "Flex":
        from .width_dependent_intrinsic_measurement import (
            auto_height_measurement_ids, compute_width_dependent,
            seed_unconstrained_width_measurements,
        )
        width_sensitive = auto_height_measurement_ids(snapshot)
        measured_ids = {item.node_id for item in measurements}
        callbacks = {
            node.node_id: (
                lambda assigned_width, origin=identities[node.node_id]:
                    measure_flow_leaf(path_identity(origin.path), origin, assigned_width)
            )
            for node in normalized.nodes[1:]
            if node.node_id in measured_ids
            and (node.node_id in width_sensitive
                 or identities[node.node_id].type == "Grid")
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
            measure_width=lambda identifier, assigned_width: measure_flow_leaf(
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
    flow_reuse: FlowBlueprintReuse | None = None,
    invalidation_epoch: int = 0,
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
                    flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
                    measure_grid=lambda subgrid, grid_width:
                        prepare_composed_grid(
                            subgrid, content_width=grid_width,
                            generation=generation, current_generation=current_generation,
                            measure_leaf=measure_leaf, is_ui_thread=is_ui_thread,
                            breakpoints=breakpoints, engine=engine,
                            viewport_constraints=viewport_constraints,
                            flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
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
                    flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
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
                            flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
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
                    flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
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
                            flow_reuse=flow_reuse, invalidation_epoch=invalidation_epoch,
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
                # A Flow with N children formerly scanned N snapshot nodes
                # for every child (quadratic). Build the immutable parent
                # index once; geometry and identity checks remain identical.
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
