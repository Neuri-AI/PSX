"""Immutable, renderer-neutral view of existing item box metadata.

This normalization boundary is not yet connected to the layout runtime.
It does not modify legacy VNode props, resolve percentages, apply CSS cascade,
or change Kivy/Qt/Tkinter behavior. Runtime integration requires an approved style precedence contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
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


def _normalize_uncached(
    props: Mapping[str, object], owner: str,
) -> CanonicalItemBoxStyle:
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


@lru_cache(maxsize=1024)
def _normalize_literal_fields(
    fields: tuple[tuple[str, object], ...], owner: str,
) -> CanonicalItemBoxStyle:
    # The cached value is fully immutable. Keys contain only layout metadata,
    # never Text.value, callbacks, widget references or native resources.
    return _normalize_uncached(dict(fields), owner)


def normalize_item_box_style(
    props: Mapping[str, object], *, owner: str = "Flex item",
) -> CanonicalItemBoxStyle:
    """Validate and normalize immutable layout metadata, never native props.

    Repeated Grid/Flex leaves often share the same layout fields. A bounded
    cache avoids reparsing their 18 default lengths every resize. Unusual
    mutable values and custom mappings retain the original validation path.
    """
    if type(props) is dict:
        fields = tuple(sorted(
            (name, value) for name, value in props.items()
            if name in FLEX_ITEM_PROPS
        ))
        if all(
            type(value) in (str, int, float, bool, type(None), Length)
            for _name, value in fields
        ):
            return _normalize_literal_fields(fields, owner)
    return _normalize_uncached(props, owner)


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
