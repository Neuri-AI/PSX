"""P1 IM-01: immutable, renderer-neutral view of existing item box metadata.

This is a *non-integrated* normalization boundary for verified F1 properties.
It does not modify legacy VNode props, resolve percentages, apply CSS cascade,
or change Kivy/Qt/Tkinter behavior. Integration requires the P1 contract gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from psx.core.layout_item import validate_flex_item_props
from psx.core.props import FLEX_ITEM_PROPS
from psx.sfle.lengths import Length, parse_length
from psx.sfle.model import BoxEdges


_SIDES = ("top", "right", "bottom", "left")
_DIMENSIONS = (
    "layout_width", "layout_height",
    "layout_min_width", "layout_min_height",
    "layout_max_width", "layout_max_height",
)
_EDGE_PREFIXES = ("layout_margin_", "layout_padding_", "layout_border_")
_DEFAULT_LENGTHS = {
    "layout_width": "auto", "layout_height": "auto",
    "layout_min_width": "auto", "layout_min_height": "auto",
    "layout_max_width": "none", "layout_max_height": "none",
}


@dataclass(frozen=True, slots=True)
class CanonicalItemBoxStyle:
    """Normalized existing box fields, not a replacement for component props.

    Lengths are immutable and percent values remain fractions. Content-box
    sizing is the ratified existing default; exposing per-element border-box
    switches requires the still-pending public property contract.
    """

    dimensions: tuple[tuple[str, Length], ...]
    margin: BoxEdges
    padding: BoxEdges
    border: BoxEdges

    def dimension(self, name: str) -> Length:
        if name not in _DIMENSIONS:
            raise KeyError(name)
        return dict(self.dimensions)[name]


def _edge_group(props: Mapping[str, object], prefix: str) -> BoxEdges:
    values = [parse_length(props.get(prefix + side, 0)) for side in _SIDES]
    return BoxEdges(*values)


def normalize_item_box_style(
    props: Mapping[str, object], *, owner: str = "Flex item",
) -> CanonicalItemBoxStyle:
    """Adapt supported F1 layout-item fields without native width collisions.

    Validation is delegated to the existing closed shared item validator, so
    unknown native/component fields remain outside this function's authority.
    No mutation of the input mapping or of the native component properties.
    """
    validate_flex_item_props(props, owner=owner)
    dimensions = tuple(
        (name, parse_length(props.get(name, _DEFAULT_LENGTHS[name])))
        for name in _DIMENSIONS
    )
    return CanonicalItemBoxStyle(
        dimensions=dimensions,
        margin=_edge_group(props, "layout_margin_"),
        padding=_edge_group(props, "layout_padding_"),
        border=_edge_group(props, "layout_border_"),
    )


def partition_item_box_style(
    props: Mapping[str, object], *, owner: str = "Flex item",
) -> tuple[dict[str, object], CanonicalItemBoxStyle]:
    """Return untouched component-owned props and an immutable box snapshot.

    The native props mapping is a fresh copy, retaining Image.width,
    Scroll.width, and all unrelated component properties unchanged.
    """
    style = normalize_item_box_style(props, owner=owner)
    component_props = {
        name: value for name, value in props.items()
        if name not in FLEX_ITEM_PROPS
    }
    return component_props, style
