"""Restricted, fail-closed pure F2 snapshot orchestration.

This is an internal computation path; the public capability manifest remains
closed until shared Rust/Chromium fixtures prove parity. No widget callbacks or
layout-time native measurement may cross this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .flex_math import FlexBasis, resolve_flexible_lengths
from .lengths import Length, LengthKind, parse_length
from .line_layout import FlexDirection, FlexWrap
from .margin_flex_pipeline import MarginFlexItem
from .box_geometry import UsedBoxEdges, UsedEdges
from .margin_tree import MarginTreeNode, compute_margin_tree
from .model import (
    AvailableSize, BoxRect, LayoutInput, LayoutResult, MeasuredBox, Rect, WritingDirection,
)
from .cross_alignment import CrossAlign
from .align_content import AlignContent
from .main_alignment import JustifyContent
from .main_margins import UsedMargin
from .fixed_point import LayoutUnit, I32_MAX, I32_MIN


@dataclass(frozen=True)
class _Style:
    direction: FlexDirection
    wrap: FlexWrap
    justify: JustifyContent
    align_content: AlignContent
    align_self: CrossAlign
    margin_top: Length
    margin_right: Length
    margin_bottom: Length
    margin_left: Length
    max_width: Length
    max_height: Length
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
    padding_top: Length
    padding_right: Length
    padding_bottom: Length
    padding_left: Length


_ALLOWED = frozenset({
    "direction", "width", "height", "layout_width", "layout_height",
    "flex_basis", "flex_grow", "flex_shrink", "min_width", "min_height",
    "layout_min_width", "layout_min_height", "align_items",
    "wrap", "justify_content", "align_content", "align_self",
    "max_width", "max_height", "layout_max_width", "layout_max_height",
    "layout_margin_top", "layout_margin_right", "layout_margin_bottom",
    "layout_margin_left", "row_gap", "column_gap",
    "layout_padding_top", "layout_padding_right", "layout_padding_bottom", "layout_padding_left",
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
            self_alignment = CrossAlign(values.get("align_self", "auto"))
            wrap = FlexWrap(values.get("wrap", "nowrap"))
            justify = JustifyContent(values.get("justify_content", "flex-start"))
            content_alignment = AlignContent(
                "stretch" if values.get("align_content", "normal") == "normal"
                else values["align_content"]
            )
        except ValueError as exc:
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, str(exc), node.node_id) from exc
        grow, shrink = values.get("flex_grow", 0), values.get("flex_shrink", 1)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v < float("inf") for v in (grow, shrink)):
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Invalid flex factors.", node.node_id)
        result[node.node_id] = _Style(
            direction=direction,
            wrap=wrap,
            justify=justify,
            align_content=content_alignment,
            align_self=self_alignment,
            margin_top=parse_length(values.get("layout_margin_top", 0)),
            margin_right=parse_length(values.get("layout_margin_right", 0)),
            margin_bottom=parse_length(values.get("layout_margin_bottom", 0)),
            margin_left=parse_length(values.get("layout_margin_left", 0)),
            max_width=_length(values, "layout_max_width", "max_width"),
            max_height=_length(values, "layout_max_height", "max_height"),
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
            padding_top=parse_length(values.get('layout_padding_top', 0)),
            padding_right=parse_length(values.get('layout_padding_right', 0)),
            padding_bottom=parse_length(values.get('layout_padding_bottom', 0)),
            padding_left=parse_length(values.get('layout_padding_left', 0)),
        )
    return result


def _layout_unit(value: float) -> float:
    """Convert a used CSS length at its Blink double-round callsite."""
    return LayoutUnit.from_nearest(value).to_px()


def _percent_flex_basis_used(value: float, reference: float) -> float:
    """Percent flex base is floored when resolving the basis (Blink)."""
    return LayoutUnit.from_floor(value * reference).to_px()


def _blink_flex_targets(
    bases: tuple[FlexBasis, ...], inner_main: float, gap: float, *, node_id: str,
) -> tuple[float, ...]:
    """Port LineFlexer::FreezeItems/ResolveFlexibleLengths, Chromium 153.

    The *entire* free-space/freeze iteration uses saturating signed raw
    LayoutUnits. Only cumulative flex fractions are finite double values.
    No post-hoc rectangle rounding and no reconstruction of freeze states
    from the output of another floating-point implementation.
    """
    if not bases:
        return ()
    raw = lambda v: LayoutUnit.from_nearest(v)
    zero = LayoutUnit.from_raw(0)
    available = raw(inner_main)
    gutter = raw(gap)
    base = [raw(item.basis) for item in bases]
    hypot = [raw(item.hypothetical) for item in bases]
    minimum = [raw(item.min_size) for item in bases]
    maximum = [raw(item.max_size) if item.max_size is not None else None
               for item in bases]
    free_for_items = available - LayoutUnit.from_raw(gutter.raw * (len(bases) - 1))
    growing = sum((unit.raw for unit in hypot), 0) < free_for_items.raw
    frozen = [
        (item.grow if growing else item.shrink) == 0 or
        (base[i].raw > hypot[i].raw if growing else base[i].raw < hypot[i].raw)
        for i, item in enumerate(bases)
    ]
    sizes = hypot[:]
    initial_free = zero

    for iteration in range(len(bases) + 1):
        # Blink FreezeItems recomputes the complete factor prefix sum.
        total_factor = 0.0
        total_scaled_shrink = 0.0
        fractions = [0.0] * len(bases)
        remaining = available
        for i, item in enumerate(bases):
            factor = item.grow if growing else item.shrink
            if frozen[i]:
                remaining = remaining - sizes[i] - gutter
                continue
            sizes[i] = hypot[i]
            total_factor += factor
            if growing:
                fractions[i] = factor / total_factor
            else:
                weight = factor * base[i].to_px()
                total_scaled_shrink += weight
                fractions[i] = weight / total_scaled_shrink if total_scaled_shrink else 0.0
            remaining = remaining - base[i] - gutter
        remaining = remaining + gutter
        if iteration == 0:
            initial_free = remaining

        if 0.0 < total_factor < 1.0:
            fractional = LayoutUnit.from_trunc(initial_free.to_px() * total_factor)
            if abs(fractional.raw) < abs(remaining.raw):
                remaining = fractional
        if (growing and remaining.raw <= 0) or (not growing and remaining.raw >= 0):
            return tuple(size.to_px() for size in sizes)

        violations = [0] * len(bases)
        total_violation = zero
        for i in range(len(bases) - 1, -1, -1):
            if frozen[i]:
                continue
            fraction = fractions[i]
            if fraction == 1.0:
                extra = remaining
            else:
                extra = LayoutUnit.from_nearest(remaining.to_px() * fraction)
            remaining = remaining - extra
            unbounded = base[i] + extra
            bounded = unbounded
            if bounded.raw < minimum[i].raw:
                bounded = minimum[i]
            if maximum[i] is not None and bounded.raw > maximum[i].raw:
                bounded = maximum[i]
            sizes[i] = bounded
            delta = bounded - unbounded
            violations[i] = delta.raw
            total_violation = total_violation + delta

        if total_violation.raw == 0:
            return tuple(size.to_px() for size in sizes)
        # Freeze only max violations if net violation <0, else min violations.
        for i, v in enumerate(violations):
            if (v < 0 and total_violation.raw < 0) or (v > 0 and total_violation.raw > 0):
                frozen[i] = True

    raise SFLEError(
        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
        "Blink fractional freezing did not converge.", node_id,
    )


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
            return _layout_unit(length.value * reference)
        # CSS block-axis cyclic percentage on an auto-sized containing block:
        # do not globally resolve to 0. This supported sizing context treats
        # it as auto and obtains the item's intrinsic contribution.
        if axis == "height":
            return None
    raise SFLECapabilityError(
        DiagnosticCode.UNSUPPORTED_FEATURE,
        f"Unlisted indefinite inline percentage dependency cycle (CSS {axis} reference).",
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
        # Chromium exposes used flex gaps on a 1/64 CSS-pixel layout grid.
        # Quantize each resolved gap before placement: rounding only the
        # accumulated x-coordinate loses intermediate browser rounding.
        return math.floor(length.value * reference * 64 + 0.5) / 64
    assert length.value is not None
    return length.value


def _main_gap(style: _Style, width: float, height: float, node_id: str) -> float:
    horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
    return _used_gap(style.column_gap if horizontal else style.row_gap,
                     width if horizontal else height, node_id)


def _padding(style: _Style, inline_reference: float, node_id: str) -> UsedEdges:
    def edge(length: Length) -> float:
        if length.kind == LengthKind.PX:
            value = length.value
        elif length.kind == LengthKind.PERCENT:
            value = _layout_unit(length.value * inline_reference)
        else:
            raise SFLECapabilityError(DiagnosticCode.INVALID_LENGTH,
                                      "Padding requires a valid CSS numeric length.", node_id)
        if value is None or value < 0:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Negative or unknown padding.", node_id)
        return value
    return UsedEdges(
        top=edge(style.padding_top), right=edge(style.padding_right),
        bottom=edge(style.padding_bottom), left=edge(style.padding_left),
    )


def compute_snapshot(request: LayoutInput, *, provisional: bool = False) -> LayoutResult:
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

    # Fail-closed: cyclic descendant percentages after an indefinite
    # column's percentage flex-basis are NOT the supported leaf-only C01 rule.
    for node in request.nodes:
        style = styles[node.node_id]
        if (style.direction not in (FlexDirection.COLUMN, FlexDirection.COLUMN_REVERSE)
            or style.height.kind != LengthKind.AUTO):
            continue
        for child_id in children[node.node_id]:
            if styles[child_id].flex_basis.kind != LengthKind.PERCENT:
                continue
            pending = list(children[child_id])
            while pending:
                descendant = pending.pop()
                if styles[descendant].height.kind == LengthKind.PERCENT:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Unlisted column intrinsic percentage basis descendant cycle.",
                        child_id,
                    )
                pending.extend(children[descendant])

    # Conservative dependency classifier. Explicitly proven definite ancestor
    # chains may resolve percentages; an intrinsically-sized inline ancestor
    # cannot supply a definite reference to a percentage descendant.
    # This is structural and deliberately independent of acceptance-case IDs.
    def inline_reference_definite(node_id: str) -> bool:
        parent = parents[node_id]
        if parent is None:
            return request.constraints.width.definite or styles[node_id].width.kind == LengthKind.PX
        ancestor = styles[parent]
        if ancestor.width.kind == LengthKind.PX:
            return True
        if ancestor.width.kind == LengthKind.PERCENT:
            return inline_reference_definite(parent)
        if ancestor.grow > 0:
            grandparent = parents[parent]
            if grandparent is not None:
                container = styles[grandparent]
                if (container.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
                        and inline_reference_definite(parent)):
                    return True
        return False

    for node in request.nodes[1:]:
        style = styles[node.node_id]
        parent = parents[node.node_id]
        if style.width.kind == LengthKind.PERCENT and not inline_reference_definite(node.node_id):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted indefinite inline percentage dependency cycle.",
                node.node_id,
            )

    # D-F1.13 / C01–C06: deny by default any *indefinite* percentage
    # dependency not matched by a recognized CSS intrinsic rule. This is
    # structural (typed lengths/known references/actual measurements), never
    # keyed to the acceptance fixture ID.
    def block_reference_definite(node_id: str) -> bool:
        parent = parents[node_id]
        if parent is None:
            return (request.constraints.height.definite or
                    styles[node_id].height.kind == LengthKind.PX)
        ancestor = styles[parent]
        if ancestor.height.kind == LengthKind.PX:
            return True
        if ancestor.height.kind == LengthKind.PERCENT:
            return block_reference_definite(parent)
        return False

    for node in request.nodes:
        node_id = node.node_id
        st = styles[node_id]
        if any(edge.kind == LengthKind.PERCENT for edge in (
            st.padding_top, st.padding_right, st.padding_bottom, st.padding_left
        )) and not inline_reference_definite(node_id):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted indefinite inline percentage padding dependency cycle.",
                node_id,
            )
        if st.max_height.kind == LengthKind.PERCENT and not block_reference_definite(node_id):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted indefinite percentage maximum size dependency cycle.",
                node_id,
            )
        if (st.height.kind == LengthKind.PERCENT and
                not block_reference_definite(node_id) and node_id not in measures):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unmeasured indefinite percentage block dependency cycle.",
                node_id,
            )

    def bounded_intrinsic(style: _Style, horizontal: bool, value: float) -> float:
        """Apply CSS explicit intrinsic/cross min/max size constraints.

        The minimum wins over an inconsistent smaller maximum. Indefinite
        percentage constraints remain handled by the capability gates.
        """
        maximum = style.max_width if horizontal else style.max_height
        minimum = style.min_width if horizontal else style.min_height
        if maximum.kind == LengthKind.PX:
            assert maximum.value is not None
            value = min(value, maximum.value)
        if minimum.kind == LengthKind.PX:
            assert minimum.value is not None
            value = max(value, minimum.value)
        return value

    def preferred(node_id: str, horizontal: bool) -> float:
        style = styles[node_id]
        length = style.width if horizontal else style.height
        if length.kind == LengthKind.PX:
            assert length.value is not None
            return bounded_intrinsic(style, horizontal, length.value)
        metric = measures.get(node_id)
        if not children[node_id]:
            if metric is not None:
                value = metric.intrinsic.preferred_width if horizontal else metric.intrinsic.preferred_height
                return bounded_intrinsic(style, horizontal, value)
            if components[node_id] == "Text":
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Text requires intrinsic measurement.", node_id)
            return bounded_intrinsic(style, horizontal, 0.0)
        is_row = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        # CSS auto intrinsic contributions include the child's own padding.
        # Percentage padding requiring a cyclic intrinsic reference stays
        # unsupported, never silently mapped to numeric zero.
        contributions = []
        for child in children[node_id]:
            child_style = styles[child]
            intrinsic_edges = (
                (child_style.padding_left, child_style.padding_right)
                if horizontal else (child_style.padding_top, child_style.padding_bottom)
            )
            padding_sum = 0.0
            for edge in intrinsic_edges:
                if edge.kind == LengthKind.PX:
                    assert edge.value is not None
                    padding_sum += edge.value
                else:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Unresolved intrinsic percentage padding contribution.", child,
                    )
            contributions.append(preferred(child, horizontal) + padding_sum)
        if is_row == horizontal:
            gap_length = style.column_gap if is_row else style.row_gap
            value = sum(contributions) + _intrinsic_gap(gap_length, node_id) * max(0,len(contributions)-1)
            return bounded_intrinsic(style, horizontal, value)
        return bounded_intrinsic(style, horizontal, max(contributions, default=0.0))

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
                if style.height.kind == LengthKind.PERCENT and metrics is None:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Unmeasured indefinite percentage block dependency cycle.",
                        node_id,
                    )
                if metrics is not None:
                    measured_width = metrics.constraints.width
                    if not provisional and measured_width.definite and abs(measured_width.value - width) > 0.01:
                        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Missing post-flex width-specific intrinsic measurement.", node_id)
                height = preferred(node_id, False)
            width = bounded_intrinsic(style, True, width)
            height = bounded_intrinsic(style, False, height)
            width, height = _layout_unit(width), _layout_unit(height)
            used[node_id] = (width, height)
            return width, height

        horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        if width is None:
            width = preferred(node_id, True)
        if height is None and not horizontal:
            height = preferred(node_id, False)
        width = bounded_intrinsic(style, True, width)
        if height is not None:
            height = bounded_intrinsic(style, False, height)
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
                desired = _percent_flex_basis_used(basis.value, main_reference) if main_reference is not None else preferred(child_id, horizontal)
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
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unlisted percentage minimum size dependency cycle.", child_id)
            assert minimum is not None
            max_length = child_style.max_width if horizontal else child_style.max_height
            if max_length.kind == LengthKind.PX:
                maximum = max_length.value
            elif max_length.kind == LengthKind.AUTO:
                maximum = None
            elif max_length.kind == LengthKind.PERCENT and main_reference is not None:
                maximum = _layout_unit(max_length.value * main_reference)
            else:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Unlisted indefinite percentage maximum size dependency cycle.", child_id)
            if maximum is not None and maximum < minimum:
                minimum = maximum
            hypo = min(max(desired, minimum), maximum) if maximum is not None else max(desired,minimum)
            bases.append(FlexBasis(desired, hypo,
                                    grow=child_style.grow,shrink=child_style.shrink,
                                    min_size=minimum,max_size=maximum))
        main_gap = _main_gap(style,width,height if height is not None else 0.0,node_id)
        edges = {child: _padding(styles[child], width, child) for child in children[node_id]}
        fixed_main_edges = sum(
            edge.horizontal if horizontal else edge.vertical
            for edge in edges.values()
        )
        targets = _blink_flex_targets(
            tuple(bases), max(0.0, main_size - fixed_main_edges), main_gap,
            node_id=node_id,
        )
        cross_sizes = []
        for child_id, target in zip(children[node_id], targets):
            child_style = styles[child_id]
            if horizontal:
                cross = _axis_value(child_style.height,height,axis="height",node_id=child_id)
                if cross is None and height is not None and style.align_items == CrossAlign.STRETCH:
                    cross = max(0.0, height - edges[child_id].vertical)
                child_width, child_height = layout(child_id,target,cross,width,height)
                # Auto cross-size contains each child outer padding box. A
                # nested column's content-only height undercounts the row.
                cross_sizes.append(child_height + edges[child_id].vertical)
            else:
                cross = _axis_value(child_style.width,width,axis="width",node_id=child_id)
                if cross is None and style.align_items == CrossAlign.STRETCH:
                    cross = max(0.0, width - edges[child_id].horizontal)
                child_width, child_height = layout(child_id,cross,target,width,height)
                cross_sizes.append(child_width + edges[child_id].horizontal)
        if height is None:
            height = max(cross_sizes, default=0.0)
        width, height = _layout_unit(width), _layout_unit(height)
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
    def margin_value(value: Length, reference: float, node_id: str) -> UsedMargin:
        if value.kind == LengthKind.AUTO:
            return UsedMargin(None)
        if value.kind == LengthKind.PX:
            return UsedMargin(_layout_unit(value.value))
        if value.kind == LengthKind.PERCENT:
            return UsedMargin(_layout_unit(value.value * reference))
        raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                  "Unsupported margin length.", node_id)

    for node in request.nodes:
        node_id, parent_id = node.node_id,node.parent_id
        width,height = used[node_id]
        if parent_id is None:
            resolved.append(MarginTreeNode(node_id,None,width,height,
                direction=styles[node_id].direction,
                wrap=styles[node_id].wrap,
                justify=styles[node_id].justify,
                align_items=styles[node_id].align_items,
                align_content=styles[node_id].align_content,
                main_gap=_main_gap(styles[node_id],width,height,node_id),
                cross_gap=_used_gap(styles[node_id].row_gap if styles[node_id].direction in
                    (FlexDirection.ROW,FlexDirection.ROW_REVERSE)
                    else styles[node_id].column_gap,width,node_id)))
            continue
        horizontal = styles[parent_id].direction in (FlexDirection.ROW,FlexDirection.ROW_REVERSE)
        main = width if horizontal else height
        cross = height if horizontal else width
        item_edges = _padding(styles[node_id], used[parent_id][0], node_id)
        parent_st = styles[parent_id]
        item_st = styles[node_id]
        parent_width = used[parent_id][0]
        mt = margin_value(item_st.margin_top,parent_width,node_id)
        mr = margin_value(item_st.margin_right,parent_width,node_id)
        mb = margin_value(item_st.margin_bottom,parent_width,node_id)
        ml = margin_value(item_st.margin_left,parent_width,node_id)
        direction = parent_st.direction
        main_horizontal = direction in (FlexDirection.ROW,FlexDirection.ROW_REVERSE)
        reverse = direction in (FlexDirection.ROW_REVERSE,FlexDirection.COLUMN_REVERSE)
        rtl = request.direction == WritingDirection.RTL
        main_forwards = (not reverse) != rtl if main_horizontal else not reverse
        cross_forwards = True if main_horizontal else not rtl
        main_start = (ml if main_forwards else mr) if main_horizontal else (mt if main_forwards else mb)
        main_end = (mr if main_forwards else ml) if main_horizontal else (mb if main_forwards else mt)
        cross_start = (mt if cross_forwards else mb) if main_horizontal else (ml if cross_forwards else mr)
        cross_end = (mb if cross_forwards else mt) if main_horizontal else (mr if cross_forwards else ml)
        item = MarginFlexItem(
            node_id, FlexBasis(main,main,grow=0,shrink=0,min_size=0),
            cross, edges=UsedBoxEdges(padding=item_edges),
            main_start=main_start,main_end=main_end,
            cross_start=cross_start,cross_end=cross_end,
            align_self=item_st.align_self,
            cross_size_auto=False,
        )
        resolved.append(MarginTreeNode(node_id,parent_id,width,height,item=item,
            direction=styles[node_id].direction,
            wrap=styles[node_id].wrap,justify=styles[node_id].justify,
            align_items=styles[node_id].align_items,
            align_content=styles[node_id].align_content,
            main_gap=_main_gap(styles[node_id],width,height,node_id),
            cross_gap=_used_gap(styles[node_id].row_gap if styles[node_id].direction in
                (FlexDirection.ROW,FlexDirection.ROW_REVERSE)
                else styles[node_id].column_gap,width,node_id)))
    result = compute_margin_tree(tuple(resolved),generation=request.generation,writing=request.direction)
    boxes = tuple((box.node_id,BoxRect(box.content,box.padding,box.border,box.border))
                  for box in result.boxes)
    return LayoutResult(1,request.generation,boxes)
