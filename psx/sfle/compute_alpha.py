"""Restricted, fail-closed pure F2 snapshot orchestration.

This is an internal computation path; the public capability manifest remains
closed until shared Rust/Chromium fixtures prove parity. No widget callbacks or
layout-time native measurement may cross this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .flex_math import FlexBasis, resolve_flexible_lengths
from .lengths import Length, LengthKind, parse_length
from .line_layout import FlexDirection, FlexWrap
from .margin_flex_pipeline import MarginFlexItem
from .margin_tree import MarginTreeNode, compute_margin_tree
from .model import (
    AvailableSize, BoxRect, LayoutInput, LayoutResult, MeasuredBox, Rect,
)
from .cross_alignment import CrossAlign


@dataclass(frozen=True)
class _Style:
    direction: FlexDirection
    width: Length
    height: Length
    flex_basis: Length
    grow: float
    shrink: float
    min_width: Length
    min_height: Length
    align_items: CrossAlign
    row_gap: Length
    column_gap: Length


_ALLOWED = frozenset({
    "direction", "width", "height", "layout_width", "layout_height",
    "flex_basis", "flex_grow", "flex_shrink", "min_width", "min_height",
    "layout_min_width", "layout_min_height", "align_items",
    "row_gap", "column_gap",
})


def _length(style: dict[str, object], *keys: str) -> Length:
    for key in keys:
        if key in style:
            return parse_length(style[key])
    return Length(LengthKind.AUTO)


def _styles(request: LayoutInput) -> dict[str, _Style]:
    result = {}
    for node in request.nodes:
        values = dict(node.style)
        unknown = set(values).difference(_ALLOWED)
        if unknown:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                f"Unimplemented CSS style properties: {sorted(unknown)}.", node.node_id,
            )
        if "width" in values and "layout_width" in values:
            raise SFLEError(DiagnosticCode.LAYOUT_CONSTRAINT, "Conflicting width declarations.", node.node_id)
        if "height" in values and "layout_height" in values:
            raise SFLEError(DiagnosticCode.LAYOUT_CONSTRAINT, "Conflicting height declarations.", node.node_id)
        try:
            direction = FlexDirection(values.get("direction", "row"))
            alignment = CrossAlign(values.get("align_items", "stretch"))
        except ValueError as exc:
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, str(exc), node.node_id) from exc
        if alignment not in (CrossAlign.STRETCH, CrossAlign.FLEX_START):
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unsupported alignment in initial snapshot slice.", node.node_id)
        grow, shrink = values.get("flex_grow", 0), values.get("flex_shrink", 1)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v < float("inf") for v in (grow, shrink)):
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Invalid flex factors.", node.node_id)
        result[node.node_id] = _Style(
            direction=direction,
            width=_length(values, "layout_width", "width"),
            height=_length(values, "layout_height", "height"),
            flex_basis=_length(values, "flex_basis"),
            grow=float(grow),
            shrink=float(shrink),
            min_width=_length(values, "layout_min_width", "min_width"),
            min_height=_length(values, "layout_min_height", "min_height"),
            align_items=alignment,
            row_gap=parse_length(values.get('row_gap', 0)),
            column_gap=parse_length(values.get('column_gap', 0)),
        )
    return result


def _axis_value(length: Length, reference: float | None, *,
                axis: str, node_id: str) -> float | None:
    if length.kind == LengthKind.PX:
        assert length.value is not None
        return length.value
    if length.kind == LengthKind.AUTO:
        return None
    if length.kind == LengthKind.PERCENT:
        if reference is not None:
            assert length.value is not None
            return length.value * reference
        # CSS block-axis cyclic percentage on an auto-sized containing block:
        # do not globally resolve to 0. This supported sizing context treats
        # it as auto and obtains the item's intrinsic contribution.
        if axis == "height":
            return None
    raise SFLECapabilityError(
        DiagnosticCode.UNSUPPORTED_FEATURE,
        f"CSS {axis} value requires an unsupported intrinsic/percentage context.",
        node_id,
    )


def _intrinsic_gap(length: Length, node_id: str) -> float:
    if length.kind == LengthKind.PX:
        assert length.value is not None
        if length.value < 0:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Negative gap.", node_id)
        return length.value
    if length.kind == LengthKind.PERCENT:
        assert length.value is not None
        if length.value < 0:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Negative gap percentage.", node_id)
        # CSS cyclic gap contributes zero during intrinsic contribution only.
        return 0.0
    raise SFLECapabilityError(DiagnosticCode.INVALID_LENGTH, "Invalid gap keyword.", node_id)


def _used_gap(length: Length, reference: float, node_id: str) -> float:
    _intrinsic_gap(length, node_id)
    if length.kind == LengthKind.PERCENT:
        assert length.value is not None
        return length.value * reference
    assert length.value is not None
    return length.value


def _main_gap(style: _Style, width: float, height: float, node_id: str) -> float:
    horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    return _used_gap(style.column_gap if horizontal else style.row_gap,
                     width if horizontal else height, node_id)


def compute_snapshot(request: LayoutInput) -> LayoutResult:
    """Compute accepted nowrap content-box snapshots or fail explicitly.

    Final height-for-width measurements must already be part of the immutable
    input; no callback, approximation or UI-thread measurement occurs here.
    """
    if not isinstance(request, LayoutInput):
        raise TypeError("Expected immutable LayoutInput.")
    if not request.nodes:
        return LayoutResult(1, request.generation, ())
    styles = _styles(request)
    children: dict[str, list[str]] = {node.node_id: [] for node in request.nodes}
    parents = {node.node_id: node.parent_id for node in request.nodes}
    components = {node.node_id: node.component for node in request.nodes}
    for node in request.nodes[1:]:
        children[node.parent_id].append(node.node_id)
    measures = {box.node_id: box for box in request.measurements}

    # The alpha C99 restriction is a specific multi-node dependency cycle.
    # Do not confuse it with a generic unsupported-compute placeholder.
    for node in request.nodes:
        if len(children[node.node_id]) != 1:
            continue
        child_id = children[node.node_id][0]
        grand = children[child_id]
        if not grand:
            continue
        s, c, g = styles[node.node_id], styles[child_id], styles[grand[0]]
        if (s.width.kind == LengthKind.AUTO and s.height.kind == LengthKind.AUTO
            and c.width.kind == c.height.kind == LengthKind.PERCENT
            and g.width.kind == g.height.kind == LengthKind.PERCENT):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted multi-node percentage dependency cycle across auto ancestors.",
                child_id,
            )

    def preferred(node_id: str, horizontal: bool) -> float:
        style = styles[node_id]
        length = style.width if horizontal else style.height
        if length.kind == LengthKind.PX:
            assert length.value is not None
            return length.value
        metric = measures.get(node_id)
        if not children[node_id]:
            if metric is not None:
                return metric.intrinsic.preferred_width if horizontal else metric.intrinsic.preferred_height
            if components[node_id] == "Text":
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Text requires intrinsic measurement.", node_id)
            return 0.0
        is_row = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        contributions = [preferred(child, horizontal) for child in children[node_id]]
        if is_row == horizontal:
            gap_length = style.column_gap if is_row else style.row_gap
            return sum(contributions) + _intrinsic_gap(gap_length, node_id) * max(0,len(contributions)-1)
        return max(contributions, default=0.0)

    used: dict[str, tuple[float, float]] = {}

    def layout(node_id: str, forced_width: float | None, forced_height: float | None,
               parent_width: float | None, parent_height: float | None) -> tuple[float, float]:
        style = styles[node_id]
        width = forced_width if forced_width is not None else _axis_value(
            style.width, parent_width, axis="width", node_id=node_id,
        )
        height = forced_height if forced_height is not None else _axis_value(
            style.height, parent_height, axis="height", node_id=node_id,
        )
        if not children[node_id]:
            metrics = measures.get(node_id)
            if width is None:
                width = preferred(node_id, True)
            if height is None:
                if metrics is not None:
                    measured_width = metrics.constraints.width
                    if measured_width.definite and abs(measured_width.value - width) > 0.01:
                        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Missing post-flex width-specific intrinsic measurement.", node_id)
                height = preferred(node_id, False)
            used[node_id] = (width, height)
            return width, height

        horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        if width is None:
            width = preferred(node_id, True)
        if height is None and not horizontal:
            height = preferred(node_id, False)
        main_size = width if horizontal else height
        assert main_size is not None
        # Intrinsically auto-sized main axes are NOT percentage-definite simply
        # because the intrinsic phase produced a finite provisional number.
        main_reference = main_size
        if horizontal and style.width.kind == LengthKind.AUTO and forced_width is None:
            main_reference = None
        if not horizontal and style.height.kind == LengthKind.AUTO and forced_height is None:
            main_reference = None

        bases = []
        for child_id in children[node_id]:
            child_style = styles[child_id]
            basis = child_style.flex_basis
            basis_axis = child_style.width if horizontal else child_style.height
            if basis.kind == LengthKind.AUTO:
                desired = _axis_value(basis_axis, main_reference, axis="width" if horizontal else "height", node_id=child_id)
                if desired is None:
                    desired = preferred(child_id, horizontal)
            elif basis.kind == LengthKind.PX:
                desired = basis.value
            elif basis.kind == LengthKind.PERCENT:
                desired = basis.value * main_reference if main_reference is not None else preferred(child_id, horizontal)
            else:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unsupported flex basis keyword.", child_id)
            assert desired is not None
            min_length = child_style.min_width if horizontal else child_style.min_height
            if min_length.kind == LengthKind.PX:
                minimum = min_length.value
            elif min_length.kind == LengthKind.AUTO:
                metric = measures.get(child_id)
                minimum = (metric.intrinsic.min_content_width if horizontal else metric.intrinsic.min_content_height) if metric is not None else (
                    basis_axis.value if basis_axis.kind == LengthKind.PX else 0.0
                )
            else:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unresolved automatic minimum.", child_id)
            assert minimum is not None
            bases.append(FlexBasis(desired, max(desired,minimum),
                                    grow=child_style.grow,shrink=child_style.shrink,
                                    min_size=minimum))
        main_gap = _main_gap(style,width,height if height is not None else 0.0,node_id)
        targets = resolve_flexible_lengths(tuple(bases), main_size, main_gap)
        cross_sizes = []
        for child_id, target in zip(children[node_id], targets):
            child_style = styles[child_id]
            if horizontal:
                cross = _axis_value(child_style.height,height,axis="height",node_id=child_id)
                if cross is None and height is not None and style.align_items == CrossAlign.STRETCH:
                    cross = height
                child_width, child_height = layout(child_id,target,cross,width,height)
                cross_sizes.append(child_height)
            else:
                cross = _axis_value(child_style.width,width,axis="width",node_id=child_id)
                if cross is None and style.align_items == CrossAlign.STRETCH:
                    cross = width
                child_width, child_height = layout(child_id,cross,target,width,height)
                cross_sizes.append(child_width)
        if height is None:
            height = max(cross_sizes, default=0.0)
        used[node_id] = (width,height)
        return width,height

    root = request.nodes[0].node_id
    root_style = styles[root]
    root_width = _axis_value(root_style.width,
        request.constraints.width.value if request.constraints.width.definite else None,
        axis="width",node_id=root)
    root_height = _axis_value(root_style.height,
        request.constraints.height.value if request.constraints.height.definite else None,
        axis="height",node_id=root)
    if root_width is None and request.constraints.width.definite:
        root_width = request.constraints.width.value
    if root_height is None and request.constraints.height.definite:
        root_height = request.constraints.height.value
    layout(root,root_width,root_height,None,None)

    resolved = []
    for node in request.nodes:
        node_id, parent_id = node.node_id,node.parent_id
        width,height = used[node_id]
        if parent_id is None:
            resolved.append(MarginTreeNode(node_id,None,width,height,
                direction=styles[node_id].direction,align_items=CrossAlign.FLEX_START,
                main_gap=_main_gap(styles[node_id],width,height,node_id)))
            continue
        horizontal = styles[parent_id].direction in (FlexDirection.ROW,FlexDirection.ROW_REVERSE)
        main = width if horizontal else height
        cross = height if horizontal else width
        item = MarginFlexItem(
            node_id, FlexBasis(main,main,grow=0,shrink=0,min_size=0),
            cross, cross_size_auto=False,
        )
        resolved.append(MarginTreeNode(node_id,parent_id,width,height,item=item,
            direction=styles[node_id].direction,align_items=CrossAlign.FLEX_START,
            main_gap=_main_gap(styles[node_id],width,height,node_id)))
    result = compute_margin_tree(tuple(resolved),generation=request.generation,writing=request.direction)
    boxes = tuple((box.node_id,BoxRect(box.content,box.padding,box.border,box.border))
                  for box in result.boxes)
    return LayoutResult(1,request.generation,boxes)
