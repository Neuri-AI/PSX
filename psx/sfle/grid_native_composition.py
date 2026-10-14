"""Recursive Grid composition using Cinnamon as the only geometry authority.

Each Grid computes its own horizontal allocations before measuring descendants.
A nested Grid's intrinsic height is the output of its own Cinnamon plan, not a
native layout manager estimate. Native ports supply only terminal leaf metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
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
from .model import IntrinsicSizes, MeasuredBox
from .native_measurement import NativeMeasurementPort
from .native_layout_snapshot import path_identity


class NativeLeafMeasurement(Protocol):
    def __call__(self, item_id: str, node: NormalizedLayoutNode, width: float) -> IntrinsicSizes: ...


@dataclass(frozen=True, slots=True)
class ComposedGrid:
    grid: NormalizedLayoutNode
    prepared: PreparedGridMeasurement
    nested: dict[str, "ComposedGrid"]
    nested_flex: dict[str, ComposedFlex]
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
            if child.kind is NodeKind.HOST and child.type == "Grid":
                subgrid = prepare_composed_grid(
                    child, content_width=width, generation=generation,
                    current_generation=current_generation,
                    measure_leaf=measure_leaf, is_ui_thread=is_ui_thread,
                    breakpoints=breakpoints, engine=engine,
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
                        ),
                    is_ui_thread=is_ui_thread, engine=engine,
                )
                nested_flex[identifier] = flex
                height = flex.content_height
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
    return ComposedGrid(grid, prepared, nested, nested_flex, height)


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
