"""Native SFLE: translate the already-normalized declarative tree to SFLE v1.

This is a lossless *style/identity* adapter, not a Flexbox implementation.
The engine alone distributes space; widgets supply intrinsic measurements
and native adapters apply immutable rectangles. Structural PSX boundaries
never turn into invisible SFLE layout boxes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from psx.core.layout_tree import LayoutPath, NormalizedLayoutNode
from psx.core.props import FLEX_ITEM_PROPS
from psx.core.vnode import NodeKind, VNode

from .canonical_box_style import CanonicalItemBoxStyle, normalize_item_box_style
from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .lengths import Length
from .model import LayoutConstraints, LayoutInput, LayoutNode, MeasuredBox, WritingDirection

_ITEM_STYLE = FLEX_ITEM_PROPS
_FLEX_STYLE = frozenset({
    "direction", "wrap", "justify_content", "align_items", "align_content",
    "width", "height", "min_width", "min_height", "max_width", "max_height",
    "row_gap", "column_gap",
})
_SIDE_NAMES = ("top", "right", "bottom", "left")
_SKIP_DEFAULT = {"auto", "none"}


def path_identity(path: LayoutPath) -> str:
    """Deterministic key-aware ID; no Python object address is serialized."""
    if not path:
        raise ValueError("A normalized layout path must not be empty.")
    return repr(path)


@dataclass(frozen=True, slots=True)
class PreparedNativeLayoutSnapshot:
    """Immutable SFLE input plus the exact originating PSX node identities."""

    snapshot: LayoutInput
    identities: tuple[tuple[str, VNode], ...]
    box_styles: tuple[tuple[str, CanonicalItemBoxStyle], ...] = ()


# Retain the old class name for existing internal imports during migration.
PreparedF3Snapshot = PreparedNativeLayoutSnapshot


def _edges(value: object) -> tuple[object, object, object, object]:
    """CSS shorthand: one / vertical-horizontal / top-right-bottom-left."""
    parts = tuple(value) if isinstance(value, (list, tuple)) else (value,)
    if len(parts) == 1:
        return parts * 4
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 4:
        return parts
    raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Flex.padding needs 1, 2 or 4 edges.")


def _style(node: VNode) -> tuple[tuple[str, object], ...]:
    result: dict[str, object] = {}
    props = node.props
    for name in _ITEM_STYLE:
        if name in props:
            value = props[name]
            if name.startswith("layout_max_") and value == "none":
                continue  # CSS unbounded default: no SFLE max constraint.
            if name == "flex_basis" and value == "auto":
                continue
            if name.startswith("layout_min_") and value == "auto":
                continue
            if name in ("layout_width", "layout_height") and value == "auto":
                continue
            result[name] = value
    if node.kind is NodeKind.HOST and node.type == "Flex":
        for name in _FLEX_STYLE:
            if name not in props:
                continue
            value = props[name]
            if name in ("width", "height", "min_width", "min_height",
                        "max_width", "max_height") and value in _SKIP_DEFAULT:
                continue
            if name == "align_content" and value == "normal":
                continue  # The layout engine treats normal alignment as stretch.
            result[name] = value
        if "gap" in props:
            result.setdefault("row_gap", props["gap"])
            result.setdefault("column_gap", props["gap"])
        if "padding" in props:
            for side, value in zip(_SIDE_NAMES, _edges(props["padding"])):
                result.setdefault(f"layout_padding_{side}", value)
    if node.kind is NodeKind.HOST and node.type == "Scroll":
        result["direction"] = (
            "row" if props["content_direction"] == "horizontal" else "column"
        )
        for axis in ("width", "height"):
            if props[axis] is not None and f"layout_{axis}" not in result:
                result[axis] = f"{props[axis]}px"
        result["align_items"] = "flex-start"
    if node.kind is NodeKind.HOST and node.type in ("Box", "RadioGroup", "Divider"):
        if node.type == "Box":
            result.setdefault("direction", "column")
            result.setdefault("width", "100%")
            result.setdefault("height", "100%")
        elif node.type == "RadioGroup":
            result["direction"] = (
                "row" if props["orientation"] == "horizontal" else "column"
            )
            result["row_gap"] = props["spacing"]
            result["column_gap"] = props["spacing"]
            for side, value in zip(_SIDE_NAMES, _edges(props["padding"])):
                result[f"layout_padding_{side}"] = value
        else:
            result["direction"] = (
                "row" if props["orientation"] == "horizontal" else "column"
            )
            result["justify_content"] = "center"
            result["align_items"] = "center"
    return tuple(sorted(result.items()))


def prepare_native_layout_snapshot(
    normalized: NormalizedLayoutNode,
    constraints: LayoutConstraints,
    *,
    generation: int,
    direction: WritingDirection = WritingDirection.LTR,
    measurements: Iterable[MeasuredBox] = (),
) -> PreparedNativeLayoutSnapshot:
    """Create SFLE v1 input without native imports or implicit measurement.

    The effective root must be one explicit Flex. Components/Fragments are
    transparent. Scroll is excluded pending the native viewport/content
    binding; fail closed rather than fabricating a layout root.
    Consumers must supply real measured leaf metrics as MeasuredBox values.
    No guess of an intrinsic size is permitted.
    """
    if not isinstance(normalized, NormalizedLayoutNode):
        raise TypeError("Expected a normalized layout tree.")
    roots = normalized._participating_roots()
    if len(roots) != 1 or roots[0].kind is not NodeKind.HOST or roots[0].type != "Flex":
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE, "Native SFLE requires one explicit Flex root."
        )
    nodes: list[LayoutNode] = []
    origins: list[tuple[str, VNode]] = []
    box_styles: list[tuple[str, CanonicalItemBoxStyle]] = []
    seen: set[str] = set()

    def visit(node: NormalizedLayoutNode, parent_id: str | None) -> None:
        identifier = path_identity(node.path)
        if identifier in seen:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate normalized node identity.", identifier)
        if node.kind not in (NodeKind.HOST, NodeKind.NATIVE):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Unresolved structural layout boundary.", identifier)
        if node.kind is NodeKind.HOST and node.type == "Scroll":
            from psx.sfle.native_scroll_viewport import require_scroll_content_root
            require_scroll_content_root(node)
        seen.add(identifier)
        name = str(node.type) if node.kind is NodeKind.HOST else "Native"
        # These hosts now participate as SFLE containers. Their native
        # adapters retain painting/selection, never place PSX children.
        if name in ("Box", "RadioGroup", "Scroll") or (
            name == "Divider" and node.effective_children
        ):
            name = "Flex"
        # Preserve specified snapshot values for both layout engines while
        # carrying an immutable, typed box representation alongside them.
        box_style = normalize_item_box_style(node.source.props, owner=str(node.type))
        nodes.append(LayoutNode(identifier, parent_id, name, _style(node.source)))
        box_styles.append((identifier, box_style))
        origins.append((identifier, node.source))
        # A Grid participates in the enclosing Flex solver as one measured
        # leaf. Its descendants are resolved by Cinnamon Grid at the actual
        # width assigned to this box, never by the Flex solver or a toolkit.
        if name != "Grid":
            for child in node.effective_children:
                visit(child, identifier)

    visit(roots[0], None)
    snapshot = LayoutInput(
        1, generation, direction, constraints, tuple(nodes), tuple(measurements)
    )
    return PreparedNativeLayoutSnapshot(snapshot, tuple(origins), tuple(box_styles))
