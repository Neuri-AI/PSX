"""Strict versioned wire adapter for the normalized Rust/PyO3 compute boundary.

The legacy typed-pair wire module remains untouched; this adapter matches the
Rust `compute::LayoutInput` serde record consumed by the differential runner.
"""
from __future__ import annotations

import json
from .errors import DiagnosticCode, SFLEError, SFLEWireError
from .lengths import Length
from .model import AvailableSize, BoxRect, LayoutConstraints, LayoutInput, LayoutResult, Rect


def serialize_snapshot(request: LayoutInput) -> str:
    if not isinstance(request, LayoutInput):
        raise TypeError("Expected LayoutInput.")
    def axis(value: AvailableSize) -> dict[str, object]:
        return {"value": value.value, "definite": value.definite}
    def constraints(value: LayoutConstraints) -> dict[str, object]:
        return {"width": axis(value.width), "height": axis(value.height)}
    def style(value: Length | str | float | int) -> object:
        return {"kind": value.kind.value, "value": value.value} if isinstance(value, Length) else value
    return json.dumps({
        "schema_version": request.schema_version,
        "generation": request.generation,
        "direction": request.direction.value,
        "constraints": constraints(request.constraints),
        "nodes": [{
            "node_id": n.node_id,
            "parent_id": n.parent_id,
            "component": n.component,
            "style": {key: style(value) for key, value in n.style},
        } for n in request.nodes],
        "measurements": [{
            "node_id": m.node_id, "revision": m.revision,
            "constraints": constraints(m.constraints),
            "intrinsic": {
                "min_content_width": m.intrinsic.min_content_width,
                "max_content_width": m.intrinsic.max_content_width,
                "min_content_height": m.intrinsic.min_content_height,
                "max_content_height": m.intrinsic.max_content_height,
                "preferred_width": m.intrinsic.preferred_width,
                "preferred_height": m.intrinsic.preferred_height,
                "baseline": m.intrinsic.baseline,
                "orthogonal_baseline": m.intrinsic.orthogonal_baseline,
            },
        } for m in request.measurements],
    }, separators=(",", ":"), allow_nan=False)



def serialize_result(result: LayoutResult) -> str:
    """Serialize immutable committed geometry for native incremental reuse."""
    if not isinstance(result, LayoutResult):
        raise TypeError("Expected LayoutResult.")

    def rect(value: Rect) -> dict[str, float]:
        return {
            "x": value.x, "y": value.y,
            "width": value.width, "height": value.height,
        }

    return json.dumps({
        "schema_version": result.schema_version,
        "generation": result.generation,
        "boxes": [{
            "node_id": node_id,
            "content": rect(box.content),
            "padding": rect(box.padding),
            "border": rect(box.border),
            "margin": rect(box.margin),
        } for node_id, box in result.boxes],
        "diagnostics": list(result.diagnostics),
        "measurement_error": result.measurement_error,
        "engine_error": result.engine_error,
        "geometry_commit_error": result.geometry_commit_error,
    }, separators=(",", ":"), allow_nan=False)


def deserialize_response(payload: str, request: LayoutInput) -> LayoutResult:
    """Validate schema, identity, generation and exact diagnostic channels."""
    try:
        response = json.loads(payload)
        if type(response.get("ok")) is not bool:
            raise ValueError("Missing boolean native result discriminator.")
        if not response["ok"]:
            failure = response["error"]
            code = DiagnosticCode(failure["code"])
            if not isinstance(failure["message"], str):
                raise ValueError("Invalid error message.")
            if failure.get("node_id") is not None and not isinstance(failure["node_id"], str):
                raise ValueError("Invalid error identity.")
            raise SFLEError(code, failure["message"], failure.get("node_id"))
        result = response["result"]
        if result["schema_version"] != request.schema_version or result["generation"] != request.generation:
            raise ValueError("Native output version/generation mismatch.")
        boxes = []
        for box in result["boxes"]:
            def rect(key: str) -> Rect:
                r = box[key]
                return Rect(r["x"], r["y"], r["width"], r["height"])
            boxes.append((box["node_id"],
                          BoxRect(rect("content"), rect("padding"), rect("border"), rect("margin"))))
        if [node_id for node_id, _ in boxes] != [node.node_id for node in request.nodes]:
            raise ValueError("Native node identity/order disagrees with the snapshot.")
        return LayoutResult(
            result["schema_version"], result["generation"], tuple(boxes),
            tuple(result.get("diagnostics", ())),
            result.get("measurement_error"), result.get("engine_error"),
            result.get("geometry_commit_error"),
        )
    except SFLEError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        raise SFLEWireError(DiagnosticCode.INVALID_WIRE,
                            "Malformed SFLE native compute result.") from exc
