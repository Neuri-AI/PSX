"""Validated renderer-neutral metadata for the planned 12-column Grid API.

Pure contract utilities only. This module does not expose a mounted Grid
component, run layout, or provide a native backend implementation.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
import math

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
    if isinstance(value, bool):
        raise RendererCapabilityError(f"{name} must be a nonnegative layout length.")
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value < 0:
            raise RendererCapabilityError(f"{name} must be a nonnegative finite length.")
        return value
    if isinstance(value, str):
        # Do not validate a different CSS grammar from Cinnamon: G1 accepts
        # only the elementary nonnegative px form, extending only alongside
        # the canonical length parser after its contract is verified.
        import re
        if re.fullmatch(r"(?:0|(?:\d+(?:\.\d+)?))px", value):
            return value
    raise RendererCapabilityError(f"{name} must be a nonnegative pixel length.")


def normalize_grid_props(props: Mapping[str, object]) -> Mapping[str, object]:
    """Validate the 12-column declaration; no geometry is computed."""
    unknown = set(props) - GRID_PROPS
    if unknown:
        raise RendererCapabilityError(f"Unsupported Grid props: {sorted(unknown)}")
    values = dict(GRID_DEFAULTS)
    values.update(props)
    if type(values["columns"]) is not int or values["columns"] != GRID_COLUMNS:
        raise RendererCapabilityError("Grid.columns must be exactly 12 in F4.")
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
    if isinstance(values["span"], int) and isinstance(values["offset"], int):
        if values["span"] + values["offset"] > GRID_COLUMNS:
            raise RendererCapabilityError("GridItem span + offset exceeds 12 columns.")
    return MappingProxyType(values)
