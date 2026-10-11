"""Executable F2 adapter-authority boundary for portable SFLE geometry.

This module is deliberately renderer-neutral. F3 adapters bind these typed
ports to Qt, Kivy, Tkinter, and Headless without introducing a second native
Flex calculation. Scroll stays a native viewport concern: SFLE receives the
content constraint and returns content bounds, while the adapter owns only
offset, clipping, and input.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math

from .errors import DiagnosticCode, SFLEError
from .model import LayoutInput, LayoutResult


@dataclass(frozen=True, slots=True)
class ScrollViewport:
    """Native scroll state that cannot participate in Flex sizing authority."""

    host_id: str
    content_root_id: str
    viewport_width: float
    viewport_height: float
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id:
            raise ValueError("Scroll viewport host_id must be nonempty.")
        if not isinstance(self.content_root_id, str) or not self.content_root_id:
            raise ValueError("Scroll viewport content_root_id must be nonempty.")
        if self.host_id == self.content_root_id:
            raise ValueError("Scroll host and content Flex root must differ.")
        for value in (self.viewport_width, self.viewport_height, self.offset_x, self.offset_y):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise ValueError("Scroll viewport values must be finite numbers.")
        if self.viewport_width < 0 or self.viewport_height < 0:
            raise ValueError("Scroll viewport dimensions must be nonnegative.")


@dataclass(frozen=True, slots=True)
class SFLEAdapterPorts:
    """The only allowed native operations around a pure geometry transaction."""

    current_generation: Callable[[], int]
    nodes_alive: Callable[[tuple[str, ...]], bool]
    apply_rectangles: Callable[[LayoutResult], None]
    read_rectangles: Callable[[], Mapping[str, Mapping[str, float]]]

    def __post_init__(self) -> None:
        if not all(callable(port) for port in (
            self.current_generation, self.nodes_alive, self.apply_rectangles, self.read_rectangles,
        )):
            raise TypeError("Adapter ports must be callable.")


def validate_adapter_commit(
    snapshot: LayoutInput,
    result: LayoutResult,
    ports: SFLEAdapterPorts,
    *,
    scroll_viewports: tuple[ScrollViewport, ...] = (),
) -> tuple[str, ...]:
    """Validate a current SFLE-only geometry commit before native mutation.

    Native adapters may read widgets for measurement and write SFLE rectangles,
    but may not supply independently calculated child geometry. Scroll hosts
    are excluded from SFLE result IDs; their explicit content Flex roots must
    be present so native offsets cannot become an implicit layout algorithm.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(result, LayoutResult):
        raise TypeError("Expected immutable snapshot and SFLE result.")
    if not isinstance(ports, SFLEAdapterPorts) or not isinstance(scroll_viewports, tuple):
        raise TypeError("Expected adapter ports and an immutable viewport tuple.")
    if result.generation != snapshot.generation or ports.current_generation() != snapshot.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale SFLE generation cannot commit geometry.")
    snapshot_ids = tuple(node.node_id for node in snapshot.nodes)
    result_ids = tuple(node_id for node_id, _ in result.boxes)
    if result_ids != snapshot_ids:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "SFLE result identity/order differs from its snapshot.")
    if not ports.nodes_alive(result_ids):
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed native nodes cannot receive SFLE geometry.")
    seen_hosts: set[str] = set()
    seen_content_roots: set[str] = set()
    by_id = {node.node_id: node for node in snapshot.nodes}
    for viewport in scroll_viewports:
        if not isinstance(viewport, ScrollViewport):
            raise TypeError("Expected ScrollViewport entries.")
        if viewport.host_id in seen_hosts:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Duplicate native scroll host.", viewport.host_id)
        seen_hosts.add(viewport.host_id)
        if viewport.content_root_id in seen_content_roots:
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT,
                "One Flex content root cannot be governed by multiple Scroll hosts.",
                viewport.content_root_id,
            )
        seen_content_roots.add(viewport.content_root_id)
        if viewport.host_id in result_ids:
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT,
                "Native scroll host must not receive an SFLE geometry rectangle.",
                viewport.host_id,
            )
        if viewport.content_root_id not in result_ids:
            raise SFLEError(
                DiagnosticCode.INVALID_SNAPSHOT,
                "Scroll viewport must target an explicit SFLE content Flex root.",
                viewport.content_root_id,
            )
        if by_id[viewport.content_root_id].component != "Flex":
            raise SFLEError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Scroll viewport content must be explicitly rooted at a Flex node.",
                viewport.content_root_id,
            )
    return result_ids


@dataclass(frozen=True, slots=True)
class ScrollContentMetrics:
    """Read-only scroll extents; native offsets never resize SFLE content."""

    content_width: float
    content_height: float
    max_offset_x: float
    max_offset_y: float
    offset_x: float
    offset_y: float


def derive_scroll_content_metrics(
    snapshot: LayoutInput,
    result: LayoutResult,
    ports: SFLEAdapterPorts,
    viewport: ScrollViewport,
) -> ScrollContentMetrics:
    """Derive a Scroll host's extent and clamped offset *only* from SFLE boxes.

    The native host may clip or scroll, but must not re-run a BoxLayout,
    QBoxLayout or pack algorithm to determine content or descendant sizes.
    Descendant overflows can increase the positive scrollable extent. Negative
    overflow is not converted into a fabricated negative scroll offset.
    """
    validate_adapter_commit(snapshot, result, ports, scroll_viewports=(viewport,))
    nodes = {node.node_id: node for node in snapshot.nodes}
    boxes = dict(result.boxes)
    root = boxes[viewport.content_root_id].border

    def inside(node_id: str) -> bool:
        cursor: str | None = node_id
        while cursor is not None:
            if cursor == viewport.content_root_id:
                return True
            cursor = nodes[cursor].parent_id
        return False

    content_width = root.width
    content_height = root.height
    for node_id, box in result.boxes:
        if not inside(node_id):
            continue
        rect = box.border
        content_width = max(content_width, rect.x + rect.width - root.x)
        content_height = max(content_height, rect.y + rect.height - root.y)
    max_x = max(0.0, content_width - viewport.viewport_width)
    max_y = max(0.0, content_height - viewport.viewport_height)
    return ScrollContentMetrics(
        content_width, content_height, max_x, max_y,
        min(max(0.0, viewport.offset_x), max_x),
        min(max(0.0, viewport.offset_y), max_y),
    )
