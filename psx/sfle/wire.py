"""Versioned JSON-safe SFLE exchange format for Python/Rust parity.

This is a strict *logical schema*, not an ABI or a claim of zero-copy data.
JSON encoding is supported for diagnostics/conformance; a batched native
binding can later consume the same versioned typed representation.

Unknown fields, non-finite numbers, ambiguous IDs and unexpected tags fail
rather than silently changing layout semantics.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import TypeAlias

from .capabilities import SCHEMA_VERSION
from .errors import DiagnosticCode, SFLEWireError
from .lengths import Length, LengthKind
from .model import (
    AvailableSize, BoxRect, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, LayoutResult, MeasuredBox, Rect, WritingDirection,
)

WireScalar: TypeAlias = str | int | float | bool | None
WireValue: TypeAlias = WireScalar | list["WireValue"] | dict[str, "WireValue"]


def _fail(message: str) -> None:
    raise SFLEWireError(DiagnosticCode.INVALID_WIRE, message)


def _fields(value: object, required: set[str], context: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != required:
        _fail(f"{context} must be an object with exactly {sorted(required)}.")
    if not all(isinstance(k, str) for k in value):
        _fail(f"{context} field names must be strings.")
    return value


def _seq(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        _fail(f"{context} must be an array.")
    return value


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{context} must be numeric, not boolean.")
    if not math.isfinite(value):
        _fail(f"{context} must be finite.")
    return float(value)


def _integer(value: object, context: str) -> int:
    if type(value) is not int:
        _fail(f"{context} must be an integer.")
    return value


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{context} must be a nonempty string.")
    return value


def length_to_wire(value: Length) -> dict[str, WireValue]:
    return {"kind": value.kind.value, "value": value.value}


def length_from_wire(value: object) -> Length:
    data = _fields(value, {"kind", "value"}, "Length")
    try:
        kind = LengthKind(_string(data["kind"], "Length.kind"))
        payload = data["value"]
        if kind in (LengthKind.PX, LengthKind.PERCENT):
            return Length(kind, _number(payload, "Length.value"))
        if payload is not None:
            _fail("Keyword lengths must have a null value.")
        return Length(kind)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SFLEWireError):
            raise
        _fail(f"Invalid length: {exc}")


def _size_to_wire(s: AvailableSize) -> dict[str, WireValue]:
    return {"value": s.value, "definite": s.definite}


def _size_from_wire(v: object) -> AvailableSize:
    d = _fields(v, {"value", "definite"}, "AvailableSize")
    if type(d["definite"]) is not bool:
        _fail("AvailableSize.definite must be a boolean.")
    value = None if d["value"] is None else _number(d["value"], "AvailableSize.value")
    try:
        return AvailableSize(value, d["definite"])
    except (TypeError, ValueError) as exc:
        _fail(f"Invalid AvailableSize: {exc}")


def _constraints_to_wire(c: LayoutConstraints) -> dict[str, WireValue]:
    return {"width": _size_to_wire(c.width), "height": _size_to_wire(c.height)}


def _constraints_from_wire(v: object) -> LayoutConstraints:
    d = _fields(v, {"width", "height"}, "LayoutConstraints")
    return LayoutConstraints(_size_from_wire(d["width"]), _size_from_wire(d["height"]))


def _intrinsic_to_wire(i: IntrinsicSizes) -> dict[str, WireValue]:
    return {
        "min_content_width": i.min_content_width,
        "max_content_width": i.max_content_width,
        "min_content_height": i.min_content_height,
        "max_content_height": i.max_content_height,
        "preferred_width": i.preferred_width,
        "preferred_height": i.preferred_height,
        "baseline": i.baseline,
    }


def _intrinsic_from_wire(v: object) -> IntrinsicSizes:
    names = {
        "min_content_width", "max_content_width", "min_content_height",
        "max_content_height", "preferred_width", "preferred_height", "baseline",
    }
    d = _fields(v, names, "IntrinsicSizes")
    try:
        values = {
            key: (None if key == "baseline" and d[key] is None
                  else _number(d[key], f"IntrinsicSizes.{key}"))
            for key in names
        }
        return IntrinsicSizes(**values)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SFLEWireError):
            raise
        _fail(f"Invalid IntrinsicSizes: {exc}")


def _style_to_wire(style: tuple[tuple[str, Length | str | float | int], ...]) -> list[WireValue]:
    result: list[WireValue] = []
    for name, value in style:
        if isinstance(value, Length):
            payload: WireValue = {"type": "length", "data": length_to_wire(value)}
        elif isinstance(value, str):
            payload = {"type": "string", "data": value}
        elif type(value) is int:
            payload = {"type": "int", "data": value}
        elif type(value) is float:
            payload = {"type": "float", "data": _number(value, name)}
        else:
            _fail(f"Unsupported style value for {name!r}.")
        result.append({"name": name, "value": payload})
    return result


def _style_from_wire(v: object) -> tuple[tuple[str, Length | str | float | int], ...]:
    entries: list[tuple[str, Length | str | float | int]] = []
    for item in _seq(v, "LayoutNode.style"):
        d = _fields(item, {"name", "value"}, "Style entry")
        name = _string(d["name"], "Style.name")
        payload = _fields(d["value"], {"type", "data"}, "Style value")
        tag = payload["type"]
        raw = payload["data"]
        if tag == "length":
            item_value: Length | str | float | int = length_from_wire(raw)
        elif tag == "string":
            if not isinstance(raw, str):
                _fail("String style value must be a string.")
            item_value = raw
        elif tag == "int":
            item_value = _integer(raw, "Style.int")
        elif tag == "float":
            item_value = _number(raw, "Style.float")
        else:
            _fail(f"Unsupported style type {tag!r}.")
        entries.append((name, item_value))
    return tuple(entries)


def _rect_to_wire(r: Rect) -> dict[str, WireValue]:
    return {"x": r.x, "y": r.y, "width": r.width, "height": r.height}


def _rect_from_wire(v: object) -> Rect:
    d = _fields(v, {"x", "y", "width", "height"}, "Rect")
    try:
        return Rect(*(_number(d[k], f"Rect.{k}") for k in ("x", "y", "width", "height")))
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SFLEWireError):
            raise
        _fail(f"Invalid Rect: {exc}")


def layout_input_to_wire(request: LayoutInput) -> dict[str, WireValue]:
    return {
        "schema_version": request.schema_version,
        "generation": request.generation,
        "writing_direction": request.direction.value,
        "constraints": _constraints_to_wire(request.constraints),
        "nodes": [
            {"node_id": n.node_id, "parent_id": n.parent_id,
             "component": n.component, "style": _style_to_wire(n.style)}
            for n in request.nodes
        ],
        "measurements": [
            {"node_id": m.node_id, "intrinsic": _intrinsic_to_wire(m.intrinsic),
             "constraints": _constraints_to_wire(m.constraints), "revision": m.revision}
            for m in request.measurements
        ],
    }


def layout_input_from_wire(value: object) -> LayoutInput:
    d = _fields(value, {
        "schema_version", "generation", "writing_direction", "constraints",
        "nodes", "measurements",
    }, "LayoutInput")
    version = _integer(d["schema_version"], "schema_version")
    if version != SCHEMA_VERSION:
        _fail("Unsupported SFLE schema version.")
    direction = d["writing_direction"]
    if direction not in ("ltr", "rtl"):
        _fail("Writing direction must be ltr or rtl.")
    nodes: list[LayoutNode] = []
    for raw in _seq(d["nodes"], "LayoutInput.nodes"):
        item = _fields(raw, {"node_id", "parent_id", "component", "style"}, "LayoutNode")
        parent = item["parent_id"]
        if parent is not None:
            parent = _string(parent, "LayoutNode.parent_id")
        nodes.append(LayoutNode(
            _string(item["node_id"], "LayoutNode.node_id"),
            parent,
            _string(item["component"], "LayoutNode.component"),
            _style_from_wire(item["style"]),
        ))
    measurements: list[MeasuredBox] = []
    for raw in _seq(d["measurements"], "LayoutInput.measurements"):
        item = _fields(raw, {"node_id", "intrinsic", "constraints", "revision"}, "MeasuredBox")
        measurements.append(MeasuredBox(
            _string(item["node_id"], "MeasuredBox.node_id"),
            _intrinsic_from_wire(item["intrinsic"]),
            _constraints_from_wire(item["constraints"]),
            _integer(item["revision"], "MeasuredBox.revision"),
        ))
    try:
        return LayoutInput(
            version,
            _integer(d["generation"], "generation"),
            WritingDirection(direction),
            _constraints_from_wire(d["constraints"]),
            tuple(nodes), tuple(measurements),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SFLEWireError):
            raise
        _fail(f"Invalid LayoutInput: {exc}")


def layout_result_to_wire(result: LayoutResult) -> dict[str, WireValue]:
    return {
        "schema_version": result.schema_version,
        "generation": result.generation,
        "boxes": [
            {"node_id": n, "content": _rect_to_wire(b.content),
             "padding": _rect_to_wire(b.padding), "border": _rect_to_wire(b.border),
             "margin": _rect_to_wire(b.margin)}
            for n, b in result.boxes
        ],
        "diagnostics": list(result.diagnostics),
    }


def layout_result_from_wire(value: object) -> LayoutResult:
    d = _fields(value, {"schema_version", "generation", "boxes", "diagnostics"}, "LayoutResult")
    boxes: list[tuple[str, BoxRect]] = []
    for raw in _seq(d["boxes"], "LayoutResult.boxes"):
        item = _fields(raw, {"node_id", "content", "padding", "border", "margin"}, "BoxRect")
        boxes.append((
            _string(item["node_id"], "BoxRect.node_id"),
            BoxRect(*(_rect_from_wire(item[k]) for k in ("content", "padding", "border", "margin"))),
        ))
    diagnostics = tuple(
        _string(v, "Diagnostic") for v in _seq(d["diagnostics"], "LayoutResult.diagnostics")
    )
    try:
        version = _integer(d["schema_version"], "schema_version")
        if version != SCHEMA_VERSION:
            _fail("Unsupported SFLE schema version.")
        return LayoutResult(
            version, _integer(d["generation"], "generation"), tuple(boxes), diagnostics
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SFLEWireError):
            raise
        _fail(f"Invalid LayoutResult: {exc}")


def dumps_input(request: LayoutInput) -> str:
    """Create deterministic UTF-8 safe JSON for a normalized snapshot."""
    return json.dumps(layout_input_to_wire(request), sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def loads_input(text: str) -> LayoutInput:
    """Decode an SFLE input and reject duplicate JSON object keys."""
    return layout_input_from_wire(json.loads(text, object_pairs_hook=_unique_pairs,
                                             parse_constant=_reject_constant))


def _reject_constant(value: str) -> None:
    _fail(f"Non-finite JSON number {value!r} is forbidden.")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"Duplicate JSON field: {key!r}.")
        result[key] = value
    return result
