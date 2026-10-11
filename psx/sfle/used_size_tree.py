"""F2.2.4 top-down definite used-size propagation (restricted pure stage).

Only CSS specified sizes whose references are definite are established.
No ancestor available-space hint is mistaken for an established content box.
Unresolved axes remain indefinite; no auto, intrinsic, or flex sizing is guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .constraint_propagation import ChildSizing
from .errors import DiagnosticCode, SFLEError
from .model import LayoutConstraints, LayoutInput
from .percentage_box_sizing import BoxSizing
from .used_size import resolve_used_content_size


@dataclass(frozen=True, slots=True)
class NodeUsedSizing:
    node_id: str
    sizing: ChildSizing
    box_sizing: BoxSizing = BoxSizing.CONTENT_BOX
    horizontal_padding_border: float = 0.0
    vertical_padding_border: float = 0.0


@dataclass(frozen=True, slots=True)
class UsedSizeTree:
    generation: int
    content: tuple[tuple[str, LayoutConstraints], ...]
    deferred: tuple[str, ...]


def propagate_definite_used_sizes(
    snapshot: LayoutInput,
    *,
    root_content: LayoutConstraints,
    children: tuple[NodeUsedSizing, ...],
) -> UsedSizeTree:
    """Propagate established root content dimensions through preorder nodes.

    A caller must provide the root's genuine used content-box dimensions.
    The result is NOT final flex geometry. Deferred nodes still have a
    typed partial constraint snapshot; their indefinite dimensions cannot
    be used as percentage reference sizes until resolved by another stage.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("snapshot must be LayoutInput.")
    if not isinstance(root_content, LayoutConstraints) or not isinstance(children, tuple):
        raise TypeError("Expected root LayoutConstraints and tuple of child sizing.")
    if not snapshot.nodes:
        if children:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Styles without a tree.")
        return UsedSizeTree(snapshot.generation, (), ())
    ids = {node.node_id for node in snapshot.nodes}
    root = snapshot.nodes[0].node_id
    styles: dict[str, NodeUsedSizing] = {}
    for entry in children:
        if not isinstance(entry, NodeUsedSizing):
            raise TypeError("Expected NodeUsedSizing.")
        if entry.node_id not in ids or entry.node_id == root or entry.node_id in styles:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Unknown/duplicate/root sizing.")
        styles[entry.node_id] = entry
    expected = ids - {root}
    if styles.keys() != expected:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Missing child sizing declarations.")
    content = {root: root_content}
    deferred = []
    for node in snapshot.nodes[1:]:
        assert node.parent_id is not None
        style = styles[node.node_id]
        size = resolve_used_content_size(
            content[node.parent_id],
            style.sizing,
            box_sizing=style.box_sizing,
            horizontal_padding_border=style.horizontal_padding_border,
            vertical_padding_border=style.vertical_padding_border,
        ).content
        content[node.node_id] = size
        if not size.width.definite or not size.height.definite:
            deferred.append(node.node_id)
    return UsedSizeTree(
        snapshot.generation,
        tuple((node.node_id, content[node.node_id]) for node in snapshot.nodes),
        tuple(deferred),
    )
