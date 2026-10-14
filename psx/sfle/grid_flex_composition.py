"""Cinnamon Flex embedded in a GridItem.

No parallel layout algorithm: the existing SFLE engine computes every Flex
rectangle after receiving the GridItem's definite Cinnamon content width.
Native terminal measurements are passed in from the toolkit owner thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind
from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .model import IntrinsicSizes, MeasuredBox, AvailableSize, LayoutConstraints
from .native_layout_snapshot import path_identity, prepare_native_layout_snapshot
from .width_dependent_intrinsic_measurement import compute_width_dependent


@dataclass(frozen=True, slots=True)
class ComposedFlex:
    root: NormalizedLayoutNode
    prepared: object
    result: object
    nested_grids: dict[str, object]
    content_height: float


def prepare_composed_flex(
    flex: NormalizedLayoutNode,
    *,
    content_width: float,
    generation: int,
    current_generation: int,
    measure_leaf: Callable[[str, NormalizedLayoutNode, float], IntrinsicSizes],
    measure_grid: Callable[[NormalizedLayoutNode, float], object],
    is_ui_thread: Callable[[], bool],
    engine: object,
) -> ComposedFlex:
    """Compute one declarative Flex child with strict bounded width remeasurement."""
    if flex.kind is not NodeKind.HOST or flex.type != "Flex":
        raise GridPackingError("GridItem Flex composition requires an explicit Flex root.")
    if generation != current_generation or not is_ui_thread():
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Flex-in-Grid measurement.")
    constraints = LayoutConstraints(
        AvailableSize(content_width, True), AvailableSize(None, False),
    )
    prepared = prepare_native_layout_snapshot(flex, constraints, generation=generation)
    all_nodes = {}

    def visit(node):
        identifier = path_identity(node.path)
        all_nodes[identifier] = node
        if node.kind is NodeKind.HOST and node.type == "Grid":
            return
        for child in node.effective_children:
            visit(child)

    visit(flex)
    descendants = {node.node_id: all_nodes[node.node_id]
                   for node in prepared.snapshot.nodes
                   if node.parent_id is not None and node.component != "Flex"}
    if any(node.kind not in (NodeKind.HOST, NodeKind.NATIVE)
           or node.type == "Scroll" or node.effective_children
           and node.type != "Grid" for node in descendants.values()):
        raise GridPackingError(
            "Flex inside GridItem supports native leaves and nested Grid; "
            "Scroll and composite non-Grid hosts require a separately "
            "certified viewport integration."
        )
    nested_grids = {}

    def measure(identifier, width):
        node = descendants[identifier]
        if node.kind is NodeKind.HOST and node.type == "Grid":
            composition = measure_grid(node, width)
            nested_grids[identifier] = composition
            height = composition.content_height
            return IntrinsicSizes(0, width, 0, height, width, height)
        intrinsic = measure_leaf(identifier, node, width)
        if not isinstance(intrinsic, IntrinsicSizes):
            raise GridPackingError("Flex-in-Grid leaf requires actual native IntrinsicSizes.")
        return intrinsic

    metrics = tuple(
        MeasuredBox(identifier, measure(identifier, content_width),
                    LayoutConstraints(AvailableSize(None, False),
                                      AvailableSize(None, False)),
                    generation)
        for identifier in descendants
    )
    from dataclasses import replace
    snapshot = replace(prepared.snapshot, measurements=metrics)
    computed = compute_width_dependent(
        engine, snapshot,
        {identifier: (lambda width, identifier=identifier:
                      measure(identifier, width))
         for identifier in descendants},
        current_generation=lambda: current_generation,
    )
    boxes = dict(computed.boxes)
    root_id = prepared.snapshot.nodes[0].node_id
    if root_id not in boxes:
        raise GridPackingError("Composed Flex root was not returned by Cinnamon.")
    return ComposedFlex(
        flex, prepared, computed, nested_grids, boxes[root_id].border.height,
    )
