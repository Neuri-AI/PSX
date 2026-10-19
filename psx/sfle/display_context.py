"""CSS display decomposition for future Cinnamon formatting contexts.

This is internal style normalization, not native host registration. Never
rewrite a logical VNode merely because its display changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OuterDisplay(str, Enum):
    BLOCK = "block"
    INLINE = "inline"


class InnerDisplay(str, Enum):
    FLOW = "flow"
    FLOW_ROOT = "flow-root"
    FLEX = "flex"


@dataclass(frozen=True, slots=True)
class DisplayMode:
    outer: OuterDisplay
    inner: InnerDisplay

    @property
    def establishes_independent_formatting_context(self) -> bool:
        return self.inner in (InnerDisplay.FLOW_ROOT, InnerDisplay.FLEX)


_DISPLAY_MODES = {
    "block": DisplayMode(OuterDisplay.BLOCK, InnerDisplay.FLOW),
    "inline": DisplayMode(OuterDisplay.INLINE, InnerDisplay.FLOW),
    "inline-block": DisplayMode(OuterDisplay.INLINE, InnerDisplay.FLOW_ROOT),
    "flow-root": DisplayMode(OuterDisplay.BLOCK, InnerDisplay.FLOW_ROOT),
    "flex": DisplayMode(OuterDisplay.BLOCK, InnerDisplay.FLEX),
    "inline-flex": DisplayMode(OuterDisplay.INLINE, InnerDisplay.FLEX),
}

_DEFAULT_DISPLAYS = {
    "div": "block", "span": "inline", "p": "block",
    "h1": "block", "h2": "block", "h3": "block",
    "h4": "block", "h5": "block", "h6": "block",
    "section": "block", "main": "block", "header": "block",
    "footer": "block", "form": "block", "label": "inline",
    "ul": "block", "li": "block",
}


def resolve_display(tag: str, declared: str | None = None) -> DisplayMode:
    """Resolve a bounded display vocabulary without guessing CSS behavior."""
    if tag not in _DEFAULT_DISPLAYS:
        raise ValueError(f"Unsupported HTML-like layout tag {tag!r}.")
    value = _DEFAULT_DISPLAYS[tag] if declared is None else declared
    if not isinstance(value, str) or value not in _DISPLAY_MODES:
        raise ValueError(f"Unsupported CSS display value {value!r}.")
    return _DISPLAY_MODES[value]


def display_change_requires_reflow(before: DisplayMode, after: DisplayMode) -> bool:
    """Only geometry/context changes require reflow; VNode identity is unchanged."""
    return before != after


def layout_measured_children(
    mode: DisplayMode,
    available_width: float,
    items: tuple[object, ...],
) -> tuple[object, ...]:
    """Dispatch a strictly measured flow, without claiming full CSS support.

    Block flow accepts BlockItem boxes; inline flow currently accepts only
    atomic InlineAtom boxes. Text fragments must be handled by a separate
    typography-aware formatter; flex belongs to the existing Cinnamon solver.
    """
    from .flow_layout import (
        BlockItem, InlineAtom, layout_block_children, layout_inline_atoms,
    )

    if mode.inner is InnerDisplay.FLEX:
        raise NotImplementedError("Flex display must use the Cinnamon Flex solver.")
    if mode.outer is OuterDisplay.BLOCK and mode.inner is InnerDisplay.FLOW:
        if not all(isinstance(item, BlockItem) for item in items):
            raise TypeError("Block flow requires measured BlockItem boxes.")
        return layout_block_children(available_width, items)
    if mode.inner is InnerDisplay.FLOW and mode.outer is OuterDisplay.INLINE:
        if not all(isinstance(item, InlineAtom) for item in items):
            raise TypeError("Inline flow requires measured atomic boxes; text runs are not supported.")
        return layout_inline_atoms(available_width, items)
    raise NotImplementedError(
        "Independent flow-root and inline-block contexts require native "
        "measurement and nested formatting integration."
    )
