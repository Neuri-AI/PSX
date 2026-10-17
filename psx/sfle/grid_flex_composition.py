"""Cinnamon Flex embedded in a GridItem.

No parallel layout algorithm: the existing SFLE engine computes every Flex
rectangle after receiving the GridItem's definite Cinnamon content width.
Native terminal measurements are passed in from the toolkit owner thread.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections.abc import Callable
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind
from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .lengths import LengthKind, parse_length
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


def _auto_root_content_width(flex: NormalizedLayoutNode, border_width: float) -> float | None:
    """Return an auto Flex root's content width inside its GridItem border box.

    A Grid placement is a border-box rectangle.  An auto-width Flex occupying
    that placement therefore has its padding and border inside that rectangle.
    Feeding the border width to the SFLE root as though it were a content width
    makes every child extend by the horizontal edges and lets native parents
    clip the right side.
    """
    props = flex.source.props
    if props.get("width", "auto") != "auto" or "layout_width" in props:
        return None

    def shorthand(value: object) -> tuple[object, object, object, object]:
        values = tuple(value) if isinstance(value, (tuple, list)) else (value,)
        if len(values) == 1:
            return values * 4
        if len(values) == 2:
            return values[0], values[1], values[0], values[1]
        if len(values) == 4:
            return values
        raise GridPackingError("Flex padding must have 1, 2, or 4 edges.")

    padding = shorthand(props.get("padding", 0))

    def edge(name: str, fallback: object) -> float:
        value = props.get(name, fallback)
        parsed = parse_length(value)
        if parsed.kind is LengthKind.PX:
            return float(parsed.value)
        if parsed.kind is LengthKind.PERCENT:
            return border_width * float(parsed.value)
        raise GridPackingError(f"GridItem Flex {name} must be a concrete length.")

    horizontal = (
        edge("layout_padding_left", padding[3])
        + edge("layout_padding_right", padding[1])
        + edge("layout_border_left", 0)
        + edge("layout_border_right", 0)
    )
    return max(0.0, border_width - horizontal)


def _with_auto_root_content_width(prepared, flex: NormalizedLayoutNode,
                                  border_width: float):
    """Pin only the root content box; retain the outer Grid constraint.

    The Grid bridge's outer constraint is also used by Qt while negotiating a
    top-level window resize.  Replacing that constraint with the content box
    made the native size-hint feedback loop unstable.  Giving the root an
    explicit resolved ``layout_width`` instead preserves the Grid border-box
    contract while making the inner Flex children honor padding.
    """
    width = _auto_root_content_width(flex, border_width)
    if width is None:
        return prepared
    root, *rest = prepared.snapshot.nodes
    style = dict(root.style)
    style["layout_width"] = width
    snapshot = replace(
        prepared.snapshot,
        nodes=(replace(root, style=tuple(sorted(style.items()))), *rest),
    )
    return replace(prepared, snapshot=snapshot)


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
    prepared = _with_auto_root_content_width(
        prepare_native_layout_snapshot(flex, constraints, generation=generation),
        flex, content_width,
    )
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
