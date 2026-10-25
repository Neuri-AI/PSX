"""G2 scroll viewport geometry contract: no toolkit sizing or implicit root.

This is the portable hand-off contract for future native Scroll host ports.
The viewport size is an SFLE border box, NOT QScrollArea.sizeHint(), Tk Canvas
requested size or Kivy ScrollView.minimum_size.
"""
from __future__ import annotations

from dataclasses import dataclass

from psx.core.errors import RendererCapabilityError
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind
from psx.renderers.components.scroll import scroll_axes
from psx.sfle.model import Rect


@dataclass(frozen=True, slots=True)
class ScrollViewportBinding:
    """Source-derived viewport policy and SFLE-owned logical rectangles."""

    direction: str
    enabled: bool
    viewport: Rect
    content: Rect
    clip_x: bool
    clip_y: bool

    @property
    def overflow_x(self) -> float:
        return max(0.0, self.content.width - self.viewport.width)

    @property
    def overflow_y(self) -> float:
        return max(0.0, self.content.height - self.viewport.height)


def require_scroll_content_root(node: NormalizedLayoutNode) -> NormalizedLayoutNode:
    """Check the G1 explicit Flex rule, without mounting a fallback container."""
    if node.kind is not NodeKind.HOST or node.type != "Scroll":
        raise RendererCapabilityError("Scroll viewport binding requires a Scroll node.")
    roots = node.effective_children
    from psx.markup.html_aliases import FORMATTING_TAGS
    if len(roots) != 1 or (
        roots[0].kind is not NodeKind.HOST
        or roots[0].type not in ({"Flex"} | FORMATTING_TAGS)
    ):
        raise RendererCapabilityError(
            "Scroll SFLE content must have exactly one Flex or HTML-like block root."
        )
    return roots[0]


def bind_scroll_viewport(
    node: NormalizedLayoutNode, viewport: Rect, content: Rect,
) -> ScrollViewportBinding:
    """Bind the two engine rectangles without changing either.

    The native host may clip and display scroll indicators, but must not
    replace these measured boxes with its own layout calculations.
    """
    require_scroll_content_root(node)
    if min(viewport.width, viewport.height, content.width, content.height) < 0:
        raise RendererCapabilityError("Scroll geometry cannot have negative sizes.")
    direction = node.source.props["direction"]
    enabled = bool(node.source.props["enabled"])
    allow_x, allow_y = scroll_axes(direction)
    return ScrollViewportBinding(
        direction=direction, enabled=enabled,
        viewport=viewport, content=content,
        clip_x=allow_x and enabled, clip_y=allow_y and enabled,
    )
