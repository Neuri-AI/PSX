"""Validated renderer-neutral metadata for the planned 12-column Grid API.

Pure contract utilities only. This module does not expose a mounted Grid
component, run layout, or provide a native backend implementation.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
import math

from psx.sfle.lengths import LengthKind, parse_length

from .errors import RendererCapabilityError

GRID_COLUMNS = 12
GRID_BREAKPOINTS = MappingProxyType({
    "base": 0, "sm": 576, "md": 768, "lg": 992, "xl": 1200,
})
GRID_DEFAULTS = MappingProxyType({
    "columns": 12, "gap": 0, "row_gap": None, "column_gap": None,
})
GRID_ITEM_DEFAULTS = MappingProxyType({"span": "auto", "offset": 0})
GRID_PROPS = frozenset(GRID_DEFAULTS)
GRID_ITEM_PROPS = frozenset(GRID_ITEM_DEFAULTS)
_BREAKPOINT_NAMES = frozenset(GRID_BREAKPOINTS)


def _integer(value: object, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise RendererCapabilityError(
            f"{name} must be an integer between {minimum} and {maximum}.")
    return value


def _responsive(value: object, *, name: str, auto: bool) -> object:
    def check(item: object) -> object:
        if auto and item == "auto":
            return "auto"
        return _integer(item, minimum=1 if auto else 0,
                        maximum=GRID_COLUMNS if auto else GRID_COLUMNS - 1,
                        name=name)

    if not isinstance(value, Mapping):
        return check(value)
    if not value or "base" not in value:
        raise RendererCapabilityError(f"{name} responsive mapping requires base.")
    invalid = set(value) - _BREAKPOINT_NAMES
    if invalid:
        raise RendererCapabilityError(
            f"{name} has unknown breakpoints: {sorted(map(str, invalid))}.")
    return MappingProxyType({key: check(item) for key, item in value.items()})


def _gap(value: object, *, name: str) -> object:
    """Validate a nonnegative pixel length using Cinnamon's canonical grammar."""
    try:
        parsed = parse_length(value)
    except (TypeError, ValueError) as exc:
        raise RendererCapabilityError(
            f"{name} must be a nonnegative finite pixel length.") from exc
    if parsed.kind is not LengthKind.PX or parsed.value is None or parsed.value < 0:
        raise RendererCapabilityError(
            f"{name} must be a nonnegative finite pixel length.")
    return value


def _at_breakpoint(value: object, breakpoint: str) -> object:
    if not isinstance(value, Mapping):
        return value
    active = next((name for name in reversed(GRID_BREAKPOINTS)
                   if name in value and GRID_BREAKPOINTS[name] <= GRID_BREAKPOINTS[breakpoint]),
                  None)
    if active is None:
        raise RendererCapabilityError("Responsive value requires base.")
    return value[active]


def normalize_grid_props(props: Mapping[str, object]) -> Mapping[str, object]:
    """Validate the 12-column declaration; no geometry is computed."""
    unknown = set(props) - GRID_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Grid props: {sorted(unknown)}")
    values = dict(GRID_DEFAULTS)
    values.update(props)
    if type(values["columns"]) is not int or values["columns"] != GRID_COLUMNS:
        raise RendererCapabilityError("Grid.columns must be exactly 12 in F4.")
    if values["gap"] is None:
        raise RendererCapabilityError("Grid.gap must be a nonnegative finite pixel length.")
    for name in ("gap", "row_gap", "column_gap"):
        value = values[name]
        if value is not None:
            values[name] = _gap(value, name=f"Grid.{name}")
    for name in ("row_gap", "column_gap"):
        if values[name] is None:
            values[name] = values["gap"]
    return MappingProxyType(values)


def normalize_grid_item_props(props: Mapping[str, object]) -> Mapping[str, object]:
    """Validate explicit/auto widths and logical offsets without reflow."""
    unknown = set(props) - GRID_ITEM_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported GridItem props: {sorted(unknown)}")
    values = dict(GRID_ITEM_DEFAULTS)
    values.update(props)
    values["span"] = _responsive(values["span"], name="GridItem.span", auto=True)
    values["offset"] = _responsive(values["offset"], name="GridItem.offset", auto=False)
    for breakpoint in GRID_BREAKPOINTS:
        span = _at_breakpoint(values["span"], breakpoint)
        offset = _at_breakpoint(values["offset"], breakpoint)
        if span != "auto" and span + offset > GRID_COLUMNS:
            raise RendererCapabilityError(
                f"GridItem span + offset exceeds 12 columns at {breakpoint}.")
    return MappingProxyType(values)
