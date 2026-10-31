"""Restricted, fail-closed pure F2 snapshot orchestration.

This is an internal computation path; the public capability manifest remains
closed until shared Rust/Chromium fixtures prove parity. No widget callbacks or
layout-time native measurement may cross this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from collections.abc import Iterable
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
from .intrinsic import OverflowMode


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
    order: int
    min_width: Length
    min_height: Length
    align_items: CrossAlign
    row_gap: Length
    column_gap: Length
    padding_top: Length
    padding_right: Length
    padding_bottom: Length
    padding_left: Length
    border_top: Length
    border_right: Length
    border_bottom: Length
    border_left: Length
    aspect_ratio: float | None
    overflow: OverflowMode
    scroll_container: bool
    replaced: bool


_ALLOWED = frozenset({
    "direction", "width", "height", "layout_width", "layout_height",
    "flex_basis", "flex_grow", "flex_shrink", "min_width", "min_height",
    "order",
    "layout_min_width", "layout_min_height", "align_items",
    "wrap", "justify_content", "align_content", "align_self",
    "max_width", "max_height", "layout_max_width", "layout_max_height",
    "layout_margin_top", "layout_margin_right", "layout_margin_bottom",
    "layout_margin_left", "row_gap", "column_gap",
    "layout_padding_top", "layout_padding_right", "layout_padding_bottom", "layout_padding_left",
    "layout_border_top", "layout_border_right", "layout_border_bottom", "layout_border_left",
    "aspect_ratio",
    "overflow",
    "scroll_container",
    "replaced",
})


def _style_length(value: object, node_id: str) -> Length:
    """Convert unsupported CSS expressions into stable capability diagnostics.

    Python must not leak a raw parser ValueError where Rust reports
    SFLE_UNSUPPORTED_FEATURE for the same immutable layout snapshot.
    """
    try:
        parsed = parse_length(value)
    except ValueError as exc:
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Unsupported CSS length keyword or expression.", node_id,
        ) from exc
    if parsed.kind in (
        LengthKind.FIT_CONTENT, LengthKind.CONTENT,
        LengthKind.NONE, LengthKind.NORMAL,
    ):
        # The shared parser recognizes these tokens, but the frozen SFLE
        # alpha compute contract does not implement their used-size rules.
        # Fail before geometry rather than treating them as auto/zero.
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Unsupported CSS length keyword or expression.", node_id,
        )
    return parsed


def _length(style: dict[str, object], node_id: str, *keys: str) -> Length:
    for key in keys:
        if key in style:
            return _style_length(style[key], node_id)
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
        def enum_value(kind: type, key: str, default: str, label: str):
            raw = values.get(key, default)
            if key == "align_content" and raw == "normal":
                raw = "stretch"
            try:
                return kind(raw)
            except (TypeError, ValueError) as exc:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                          f"Unsupported {label} value.", node.node_id) from exc
        direction = enum_value(FlexDirection, "direction", "row", "direction")
        alignment = enum_value(CrossAlign, "align_items", "stretch", "align_items")
        self_alignment = enum_value(CrossAlign, "align_self", "auto", "align_self")
        wrap = enum_value(FlexWrap, "wrap", "nowrap", "wrap")
        justify = enum_value(JustifyContent, "justify_content", "flex-start", "justify-content")
        content_alignment = enum_value(AlignContent, "align_content", "normal", "align-content")
        overflow = enum_value(OverflowMode, "overflow", "visible", "overflow")
        grow, shrink = values.get("flex_grow", 0), values.get("flex_shrink", 1)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v < float("inf") for v in (grow, shrink)):
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Invalid flex factors.", node.node_id)
        order = values.get("order", 0)
        if isinstance(order, bool) or not isinstance(order, int):
            raise SFLEError(DiagnosticCode.INVALID_LENGTH, "order must be a signed integer.", node.node_id)
        if order < -(1 << 31) or order > (1 << 31) - 1:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH,
                            "order is outside the supported signed range.", node.node_id)
        ratio = values.get("aspect_ratio")
        if ratio is not None:
            if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 0:
                raise SFLEError(DiagnosticCode.INVALID_LENGTH,
                                "aspect_ratio must be a positive finite number.", node.node_id)
            ratio = float(ratio)
        scroll_container = values.get("scroll_container", overflow == OverflowMode.SCROLL)
        if type(scroll_container) is not bool:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH,
                            "scroll_container must be boolean.", node.node_id)
        if scroll_container and overflow not in (OverflowMode.AUTO, OverflowMode.SCROLL):
            raise SFLEError(DiagnosticCode.LAYOUT_CONSTRAINT,
                            "scroll_container requires overflow auto or scroll.", node.node_id)
        replaced = values.get("replaced", node.component == "Image")
        if type(replaced) is not bool:
            raise SFLEError(DiagnosticCode.INVALID_LENGTH,
                            "replaced must be boolean.", node.node_id)
        result[node.node_id] = _Style(
            direction=direction,
            wrap=wrap,
            justify=justify,
            align_content=content_alignment,
            align_self=self_alignment,
            margin_top=_style_length(values.get("layout_margin_top", 0), node.node_id),
            margin_right=_style_length(values.get("layout_margin_right", 0), node.node_id),
            margin_bottom=_style_length(values.get("layout_margin_bottom", 0), node.node_id),
            margin_left=_style_length(values.get("layout_margin_left", 0), node.node_id),
            max_width=_length(values, node.node_id, "layout_max_width", "max_width"),
            max_height=_length(values, node.node_id, "layout_max_height", "max_height"),
            width=_length(values, node.node_id, "layout_width", "width"),
            height=_length(values, node.node_id, "layout_height", "height"),
            flex_basis=_length(values, node.node_id, "flex_basis"),
            grow=float(grow),
            shrink=float(shrink),
            order=order,
            min_width=_length(values, node.node_id, "layout_min_width", "min_width"),
            min_height=_length(values, node.node_id, "layout_min_height", "min_height"),
            align_items=alignment,
            row_gap=_style_length(values.get('row_gap', 0), node.node_id),
            column_gap=_style_length(values.get('column_gap', 0), node.node_id),
            padding_top=_style_length(values.get('layout_padding_top', 0), node.node_id),
            padding_right=_style_length(values.get('layout_padding_right', 0), node.node_id),
            padding_bottom=_style_length(values.get('layout_padding_bottom', 0), node.node_id),
            padding_left=_style_length(values.get('layout_padding_left', 0), node.node_id),
            border_top=_style_length(values.get('layout_border_top', 0), node.node_id),
            border_right=_style_length(values.get('layout_border_right', 0), node.node_id),
            border_bottom=_style_length(values.get('layout_border_bottom', 0), node.node_id),
            border_left=_style_length(values.get('layout_border_left', 0), node.node_id),
            aspect_ratio=ratio,
            overflow=overflow,
            scroll_container=scroll_container,
            replaced=replaced,
        )
    return result


def _layout_unit(value: float) -> float:
    """Convert a used CSS length at its Blink double-round callsite."""
    return LayoutUnit.from_nearest(value).to_px()


def _sum_units(values: Iterable[float]) -> float:
    """Accumulate used geometry, saturating after each addition."""
    total = LayoutUnit.from_raw(0)
    for value in values:
        total = total + LayoutUnit.from_nearest(value)
    return total.to_px()


def _subtract_units(value: float, deductions: Iterable[float]) -> float:
    total = LayoutUnit.from_nearest(value)
    for deduction in deductions:
        total = total - LayoutUnit.from_nearest(deduction)
    return total.to_px()


def _percent_used_dimension(value: float, reference: float) -> float:
    """Floor CSS used percentage sizes to Chromium's 1/64px grid."""
    used = value * reference
    if math.isinf(used):
        return LayoutUnit.from_raw(I32_MAX if used > 0 else I32_MIN).to_px()
    return LayoutUnit.from_floor(math.nextafter(used, math.inf)).to_px()


def _percent_flex_basis_used(value: float, reference: float) -> float:
    """Percent flex base is floored when resolving the basis (Blink)."""
    used = value * reference
    if math.isinf(used):
        return LayoutUnit.from_raw(I32_MAX if used > 0 else I32_MIN).to_px()
    return LayoutUnit.from_floor(used).to_px()


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

    def finite_factor(value: float) -> float:
        if not math.isfinite(value):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Flex factor accumulation exceeds finite f64 range.",
                node_id,
            )
        return value

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
            total_factor = finite_factor(total_factor + factor)
            if growing:
                fractions[i] = finite_factor(factor / total_factor)
            else:
                weight = finite_factor(factor * base[i].to_px())
                total_scaled_shrink = finite_factor(total_scaled_shrink + weight)
                fractions[i] = (finite_factor(weight / total_scaled_shrink)
                                if total_scaled_shrink else 0.0)
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
    if length.kind in (LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT):
        # Explicit intrinsic keywords are resolved through preferred() using
        # host-provided min/max metrics, not through available-space hints.
        return None
    if length.kind == LengthKind.PERCENT:
        if reference is not None:
            assert length.value is not None
            return _percent_used_dimension(length.value, reference)
        # A percentage whose containing axis is intrinsically indefinite has
        # no used numeric value in this phase.  Flex intrinsic sizing treats
        # it as auto/content rather than fabricating zero; once a definite
        # parent size exists this function is called again with that value.
        return None
    raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                              f"Unsupported CSS {axis} length.", node_id)


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
        used = length.value * reference
        if math.isinf(used):
            return LayoutUnit.from_raw(I32_MAX if used > 0 else I32_MIN).to_px()
        return LayoutUnit.from_nearest(used).to_px()
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
            # Blink's used percentage padding follows LayoutUnit truncation,
            # not FromDoubleRound. Compensate a single f64 representational
            # ULP before flooring (e.g. 35% * 45 = 15.749999999999998).
            used = length.value * inline_reference
            if math.isinf(used):
                value = LayoutUnit.from_raw(I32_MAX if used > 0 else I32_MIN).to_px()
            else:
                value = LayoutUnit.from_floor(math.nextafter(used, math.inf)).to_px()
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


def _border(style: _Style, node_id: str) -> UsedEdges:
    """Resolve physical border widths; CSS percentage borders are invalid."""
    def edge(length: Length) -> float:
        if length.kind != LengthKind.PX or length.value is None or length.value < 0:
            raise SFLECapabilityError(
                DiagnosticCode.INVALID_LENGTH,
                "Borders require nonnegative pixel lengths.", node_id,
            )
        return _layout_unit(length.value)
    return UsedEdges(top=edge(style.border_top), right=edge(style.border_right),
                     bottom=edge(style.border_bottom), left=edge(style.border_left))


def compute_snapshot(
    request: LayoutInput, *, provisional: bool = False,
    previous_input: LayoutInput | None = None,
    previous_result: LayoutResult | None = None,
    reused_contexts: list[str] | None = None,
) -> LayoutResult:
    """Compute recursive wrapped content-box snapshots.

    Final height-for-width measurements must already be part of the immutable
    input; no callback, approximation or UI-thread measurement occurs here.
    """
    if not isinstance(request, LayoutInput):
        raise TypeError("Expected immutable LayoutInput.")
    if not request.nodes:
        return LayoutResult(1, request.generation, ())
    styles = _styles(request)
    children: dict[str, list[str]] = {node.node_id: [] for node in request.nodes}
    components = {node.node_id: node.component for node in request.nodes}
    for node in request.nodes[1:]:
        children[node.parent_id].append(node.node_id)
    measures = {box.node_id: box for box in request.measurements}

    # Approved F2 point-5 deferral: do not invent intrinsic size for an
    # unmeasured replaced ratio leaf with two auto axes and no cross stretch.
    # Definite-axis ratio transfer remains supported by the frozen alpha subset.
    for node in request.nodes[1:]:
        style = styles[node.node_id]
        if (style.replaced and style.aspect_ratio is not None
                and style.width.kind == LengthKind.AUTO
                and style.height.kind == LengthKind.AUTO
                and node.node_id not in measures):
            parent = styles[node.parent_id]
            alignment = (style.align_self if style.align_self != CrossAlign.AUTO
                         else parent.align_items)
            if alignment != CrossAlign.STRETCH:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Replaced intrinsic aspect-ratio sizing without native measurement is deferred.",
                    node.node_id,
                )

    # Resolve intrinsic constraint keywords bottom-up before flex sizing.
    # The certified recursive branch is COLUMN inline intrinsic width; its
    # width equals the maximum definite/minmax-clamped outer child width.
    # Other recursive dependency classes fail closed rather than pretending
    # a guessed intrinsic size is authoritative.
    def intrinsic_flex_width(node_id: str, minimum: bool) -> float:
        style = styles[node_id]
        if not children[node_id]:
            intrinsic = measures.get(node_id)
            if intrinsic is None:
                if components[node_id] == "Text":
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Intrinsic constraint requires measured text.", node_id,
                    )
                return 0.0
            return _layout_unit(
                intrinsic.intrinsic.min_content_width if minimum
                else intrinsic.intrinsic.max_content_width
            )
        horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        if horizontal and style.wrap != FlexWrap.NOWRAP:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Recursive row intrinsic constraint requires no-wrap.",
                node_id,
            )
        if horizontal and any(styles[c].shrink != 0 and (minimum or styles[c].width.kind != LengthKind.PX or styles[c].flex_basis.kind != LengthKind.PX or styles[c].min_width.kind != LengthKind.PX) for c in children[node_id]):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Shrinking row max-content requires definite item width, basis and minimum.",
                node_id,
            )
        outer_sizes = []
        for child_id in children[node_id]:
            child = styles[child_id]
            if child.width.kind == LengthKind.PX:
                child_width = _layout_unit(child.width.value)
            elif child.width.kind in (LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT):
                child_width = intrinsic_flex_width(child_id, minimum)
            else:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Uncertified percentage dependency in recursive intrinsic constraint.",
                    child_id,
                )
            if child.max_width.kind == LengthKind.PX:
                child_width = min(child_width, _layout_unit(child.max_width.value))
            elif child.max_width.kind != LengthKind.AUTO:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Unresolved intrinsic maximum in recursive child.", child_id,
                )
            if child.min_width.kind == LengthKind.PX:
                child_width = max(child_width, _layout_unit(child.min_width.value))
            elif child.min_width.kind != LengthKind.AUTO:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Unresolved intrinsic minimum in recursive child.", child_id,
                )
            fixed_edges = 0.0
            for edge in (
                child.padding_left, child.padding_right,
                child.border_left, child.border_right,
                child.margin_left, child.margin_right,
            ):
                if edge.kind == LengthKind.PX:
                    fixed_edges = _sum_units((fixed_edges, edge.value))
                elif edge.kind != LengthKind.AUTO:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Uncertified relative edges in recursive intrinsic constraint.",
                        child_id,
                    )
            outer_sizes.append(_sum_units((child_width, fixed_edges)))
        if horizontal:
            gap = style.column_gap
            if gap.kind != LengthKind.PX:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Recursive row intrinsic gap must be definite.",
                    node_id,
                )
            return _sum_units(
                size for i, outer in enumerate(outer_sizes)
                for size in ((gap.value, outer) if i else (outer,))
            )
        return max(outer_sizes, default=0.0)

    def intrinsic_flex_height(node_id: str, minimum: bool) -> float:
        """Recursive intrinsic block size from certified fixed child heights.

        For columns the block main contributions add, including row-gap;
        for rows the block cross contribution is the largest outer child.
        Unknown percent cycles and nonfixed flexible columns stay fail-closed.
        """
        style = styles[node_id]
        if not children[node_id]:
            intrinsic = measures.get(node_id)
            if intrinsic is not None:
                return _layout_unit(
                    intrinsic.intrinsic.min_content_height if minimum
                    else intrinsic.intrinsic.max_content_height
                )
            if components[node_id] == "Text":
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                    "Intrinsic block constraint requires measured text.", node_id,
                )
            return 0.0

        is_column = style.direction in (
            FlexDirection.COLUMN, FlexDirection.COLUMN_REVERSE,
        )
        contributions = []
        for child_id in children[node_id]:
            child = styles[child_id]
            if is_column and child.shrink != 0:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Recursive intrinsic column block sizing requires nonshrinking items.",
                    child_id,
                )
            if child.height.kind == LengthKind.PX:
                used_height = _layout_unit(child.height.value)
            elif child.height.kind in (
                LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT,
            ):
                used_height = intrinsic_flex_height(child_id, minimum)
            else:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Uncertified percentage block dependency in intrinsic constraint.",
                    child_id,
                )
            if child.max_height.kind == LengthKind.PX:
                used_height = min(used_height, _layout_unit(child.max_height.value))
            elif child.max_height.kind != LengthKind.AUTO:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Unresolved intrinsic maximum block size.", child_id,
                )
            if child.min_height.kind == LengthKind.PX:
                used_height = max(used_height, _layout_unit(child.min_height.value))
            elif child.min_height.kind != LengthKind.AUTO:
                raise SFLECapabilityError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Unresolved intrinsic minimum block size.", child_id,
                )
            edges = (
                child.padding_top, child.padding_bottom,
                child.border_top, child.border_bottom,
                child.margin_top, child.margin_bottom,
            )
            total = used_height
            for edge in edges:
                if edge.kind == LengthKind.PX:
                    total = _sum_units((total, edge.value))
                elif edge.kind != LengthKind.AUTO:
                    raise SFLECapabilityError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Uncertified relative block edges in intrinsic constraint.",
                        child_id,
                    )
            contributions.append(total)
        if not is_column:
            return max(contributions, default=0.0)
        if style.row_gap.kind != LengthKind.PX:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Recursive intrinsic column gap must be definite.", node_id,
            )
        return _sum_units(
            part for i, size in enumerate(contributions)
            for part in ((style.row_gap.value, size) if i else (size,))
        )

    for node in reversed(request.nodes):
        node_id = node.node_id
        style = styles[node_id]
        intrinsic_bounds = {}
        for prop, axis in (
            ("min_width", "width"), ("max_width", "width"),
            ("min_height", "height"), ("max_height", "height"),
        ):
            length = getattr(style, prop)
            if length.kind not in (LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT):
                continue
            is_min = length.kind == LengthKind.MIN_CONTENT
            if children[node_id]:
                value = (
                    intrinsic_flex_width(node_id, is_min) if axis == "width"
                    else intrinsic_flex_height(node_id, is_min)
                )
            else:
                measured = measures.get(node_id)
                if measured is None:
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Intrinsic min/max constraint requires measured leaf content.",
                        node_id,
                    )
                kind = "min_content" if is_min else "max_content"
                value = getattr(measured.intrinsic, f"{kind}_{axis}")
            intrinsic_bounds[prop] = Length.px(value)
        if intrinsic_bounds:
            styles[node_id] = replace(style, **intrinsic_bounds)

    parents = {node.node_id: node.parent_id for node in request.nodes}

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

    # A single definite-root row with an auto-width, no-shrink row holding
    # one definite-width leaf has a CSS-defined cyclic inline padding rule:
    # its percent padding contributes zero INTRINSICALLY, then resolves
    # against the wrapper's actual used width. Unknown cycles still fail.
    def supported_cyclic_padding(node_id: str) -> bool:
        parent = parents[node_id]
        if parent is None or parents[parent] is None:
            return False
        outer = parents[parent]
        own, wrapper, container = styles[node_id], styles[parent], styles[outer]
        def fixed_intrinsic_sibling(sibling_id: str) -> bool:
            # Each item contributes a definite PX flex basis to the auto's
            # max-content inline width. Inline percentage padding contributes
            # zero to that intrinsic sum and resolves only after sizing.
            sibling = styles[sibling_id]
            return (
                not children[sibling_id]
                and sibling.width.kind == sibling.flex_basis.kind == LengthKind.PX
                and sibling.shrink == 0
                and sibling.padding_top.kind == sibling.padding_bottom.kind == LengthKind.PX
            )

        def definite_row_ancestor_chain() -> bool:
            # Only single-child auto-row links can safely propagate the
            # definite leaf intrinsic basis to a known definite row root.
            # The immediate wrapper may have a certified fixed-basis sibling
            # group, as already checked above.
            current = parent
            while current is not None:
                node_style = styles[current]
                if (
                    node_style.width.kind != LengthKind.AUTO
                    or node_style.shrink != 0
                    or node_style.direction not in
                        (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
                ):
                    return False
                ancestor = parents[current]
                if ancestor is None:
                    return False
                ancestor_style = styles[ancestor]
                if ancestor_style.width.kind == LengthKind.PX:
                    return ancestor_style.direction in (
                        FlexDirection.ROW, FlexDirection.ROW_REVERSE,
                    )
                if children[ancestor] != [current]:
                    return False
                current = ancestor
            return False

        return (
            not children[node_id] and bool(children[parent])
            and all(fixed_intrinsic_sibling(sibling) for sibling in children[parent])
            and wrapper.width.kind == LengthKind.AUTO and wrapper.shrink == 0
            and wrapper.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
            and definite_row_ancestor_chain()
            and own.padding_top.kind == own.padding_bottom.kind == LengthKind.PX
            and any(e.kind == LengthKind.PERCENT for e in (own.padding_left, own.padding_right))
        )

    allowed_cyclic_padding = {
        node.node_id for node in request.nodes if supported_cyclic_padding(node.node_id)
    }

    for node in request.nodes:
        node_id = node.node_id
        st = styles[node_id]
        if any(edge.kind == LengthKind.PERCENT for edge in (
            st.padding_top, st.padding_right, st.padding_bottom, st.padding_left
        )) and not inline_reference_definite(node_id) and node_id not in allowed_cyclic_padding:
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted indefinite inline percentage padding dependency cycle.",
                node_id,
            )
        # An intrinsically auto-sized containing axis cannot supply a used
        # reference for a percentage min/max. Keep these dependency classes
        # fail-closed until independently certified by Chromium.
        if (st.min_width.kind == LengthKind.PERCENT and
                not inline_reference_definite(node_id)):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted percentage minimum size dependency cycle.", node_id,
            )
        if (st.min_height.kind == LengthKind.PERCENT and
                not block_reference_definite(node_id)):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted percentage minimum size dependency cycle.", node_id,
            )
        if (st.max_width.kind == LengthKind.PERCENT and
                not inline_reference_definite(node_id)):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Unlisted indefinite percentage maximum size dependency cycle.", node_id,
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

    def bounded_intrinsic(
        style: _Style, horizontal: bool, value: float,
        reference: float | None = None,
    ) -> float:
        """Apply definite min/max constraints to used/intrinsic content sizes.

        Intrinsic widths without a definite containing-block reference only
        honor PX bounds. Resolved percentage bounds use LayoutUnit and CSS
        gives the minimum precedence over an inconsistent maximum.
        """
        maximum = style.max_width if horizontal else style.max_height
        minimum = style.min_width if horizontal else style.min_height

        def bound(length: Length) -> float | None:
            if length.kind == LengthKind.PX:
                return _layout_unit(length.value)
            if length.kind == LengthKind.PERCENT and reference is not None:
                assert length.value is not None
                return _percent_used_dimension(length.value, reference)
            return None

        cap = bound(maximum)
        floor = bound(minimum)
        if cap is not None:
            value = min(value, cap)
        if floor is not None:
            value = max(value, floor)
        return _layout_unit(value)

    @lru_cache(maxsize=None)
    def preferred(node_id: str, horizontal: bool, minimum: bool = False) -> float:
        style = styles[node_id]
        length = style.width if horizontal else style.height
        if length.kind == LengthKind.PX:
            assert length.value is not None
            return bounded_intrinsic(style, horizontal, length.value)
        requested_minimum = minimum or length.kind == LengthKind.MIN_CONTENT
        if length.kind == LengthKind.MAX_CONTENT:
            requested_minimum = False
        metric = measures.get(node_id)
        if not children[node_id]:
            if metric is not None:
                if requested_minimum:
                    value = metric.intrinsic.min_content_width if horizontal else metric.intrinsic.min_content_height
                elif length.kind == LengthKind.MAX_CONTENT:
                    value = metric.intrinsic.max_content_width if horizontal else metric.intrinsic.max_content_height
                else:
                    value = metric.intrinsic.preferred_width if horizontal else metric.intrinsic.preferred_height
                return bounded_intrinsic(style, horizontal, value)
            if components[node_id] == "Text" and not minimum:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Text requires intrinsic measurement.", node_id)
            return bounded_intrinsic(style, horizontal, 0.0)
        is_row = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        # CSS auto intrinsic contributions include the child's own padding.
        # Percentage padding contributes zero during intrinsic sizing and is
        # resolved after the containing inline size reaches a fixed point.
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
                    padding_sum = _sum_units((padding_sum, edge.value))
                elif edge.kind == LengthKind.PERCENT:
                    # Cyclic percentage padding contributes zero only while
                    # establishing intrinsic size; _padding resolves it from
                    # the used container inline size in the geometry phase.
                    continue
            contribution = preferred(child, horizontal, requested_minimum)
            if is_row == horizontal:
                basis = child_style.flex_basis
                base = basis.value if basis.kind == LengthKind.PX else preferred(child, horizontal)
                if child_style.grow == 0:
                    contribution = min(contribution, _layout_unit(base))
                if child_style.shrink == 0:
                    contribution = max(contribution, _layout_unit(base))
                contribution = bounded_intrinsic(child_style, horizontal, contribution)
            margin_edges = ((child_style.margin_left, child_style.margin_right) if horizontal
                            else (child_style.margin_top, child_style.margin_bottom))
            # Cyclic percentages and auto margins contribute zero intrinsically.
            contributions.append(_sum_units((contribution, padding_sum, *(
                edge.value for edge in margin_edges if edge.kind == LengthKind.PX
            ))))
        if is_row == horizontal:
            if requested_minimum and style.wrap != FlexWrap.NOWRAP:
                return bounded_intrinsic(style, horizontal, max(contributions, default=0.0))
            gap_length = style.column_gap if is_row else style.row_gap
            gap = _layout_unit(_intrinsic_gap(gap_length, node_id))
            value = _sum_units(v for i, size in enumerate(contributions)
                               for v in ((gap, size) if i else (size,)))
            return bounded_intrinsic(style, horizontal, value)
        return bounded_intrinsic(style, horizontal, max(contributions, default=0.0))

    used: dict[str, tuple[float, float]] = {}

    # A prior result may supply used content dimensions for an unchanged,
    # definitely-sized subtree. Its current placement is still recomputed
    # by the normal margin-tree compositor. The safe subset excludes
    # percentages and intrinsic dependencies on a changed environment.
    reusable: dict[str, tuple[float, float]] = {}
    reused_subtree: dict[str, tuple[str, ...]] = {}
    if (not provisional and previous_input is not None and previous_result is not None
            and previous_input.schema_version == request.schema_version
            and previous_input.constraints == request.constraints
            and previous_input.direction == request.direction
            and previous_result.generation == previous_input.generation
            and not previous_result.diagnostics
            and previous_result.geometry_commit_error in (None, 0)):
        prior_nodes = {node.node_id: node for node in previous_input.nodes}
        prior_children: dict[str, list[str]] = {node.node_id: [] for node in previous_input.nodes}
        for old_child in previous_input.nodes:
            if old_child.parent_id is not None and old_child.parent_id in prior_children:
                prior_children[old_child.parent_id].append(old_child.node_id)
        current_nodes = {node.node_id: node for node in request.nodes}
        prior_metrics = {item.node_id: item for item in previous_input.measurements}
        current_metrics = {item.node_id: item for item in request.measurements}
        previous_boxes = dict(previous_result.boxes)
        subtree_safe: dict[str, bool] = {}
        subtree_ids: dict[str, tuple[str, ...]] = {}
        for node in reversed(request.nodes):
            old = prior_nodes.get(node.node_id)
            intrinsic_same = prior_metrics.get(node.node_id) == current_metrics.get(node.node_id)
            # Percentage styles depend on a containing-block dimension;
            # reject even if an apparently equivalent previous size exists.
            no_percent = all(
                not (isinstance(value, Length) and value.kind == LengthKind.PERCENT)
                and not (isinstance(value, str) and "%" in value)
                for _, value in node.style
            )
            direct = (old == node and intrinsic_same and no_percent
                      and prior_children.get(node.node_id) == children[node.node_id]
                      and node.node_id in previous_boxes)
            descendants = tuple(children[node.node_id])
            safe = direct and all(subtree_safe.get(child, False) for child in descendants)
            subtree_safe[node.node_id] = safe
            subtree_ids[node.node_id] = (
                (node.node_id,) + tuple(
                    descendant for child in descendants
                    for descendant in subtree_ids[child]
                ) if safe else ()
            )
            if safe:
                reusable[node.node_id] = (
                    previous_boxes[node.node_id].content.width,
                    previous_boxes[node.node_id].content.height,
                )
                reused_subtree[node.node_id] = subtree_ids[node.node_id]

    def layout(node_id: str, forced_width: float | None, forced_height: float | None,
               parent_width: float | None, parent_height: float | None) -> tuple[float, float]:
        style = styles[node_id]
        if node_id in reusable and forced_width is not None and forced_height is not None:
            old_width, old_height = reusable[node_id]
            if (abs(old_width - forced_width) <= 1 / 64
                    and abs(old_height - forced_height) <= 1 / 64):
                for descendant in reused_subtree[node_id]:
                    used[descendant] = reusable[descendant]
                if reused_contexts is not None:
                    reused_contexts.append(node_id)
                return old_width, old_height
        width = forced_width if forced_width is not None else _axis_value(
            style.width, parent_width, axis="width", node_id=node_id,
        )
        height = forced_height if forced_height is not None else _axis_value(
            style.height, parent_height, axis="height", node_id=node_id,
        )
        # A definite axis transfers through aspect-ratio for leaves and
        # containers alike. Min/max are applied below on both axes.
        if width is None and height is not None and style.aspect_ratio is not None:
            width = _layout_unit(height * style.aspect_ratio)
        if height is None and width is not None and style.aspect_ratio is not None:
            height = _layout_unit(width / style.aspect_ratio)
        if not children[node_id]:
            metrics = measures.get(node_id)
            if width is None:
                width = preferred(node_id, True)
            if height is None:
                if metrics is not None:
                    measured_width = metrics.constraints.width
                    if not provisional and measured_width.definite and abs(measured_width.value - width) > 0.01:
                        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Missing post-flex width-specific intrinsic measurement.", node_id)
                height = preferred(node_id, False)
            width = bounded_intrinsic(style, True, width, parent_width)
            height = bounded_intrinsic(style, False, height, parent_height)
            width, height = _layout_unit(width), _layout_unit(height)
            used[node_id] = (width, height)
            return width, height

        horizontal = style.direction in (FlexDirection.ROW, FlexDirection.ROW_REVERSE)
        # Flex order changes the sequence used for line collection and for
        # each line's free-space calculation.  The geometry compositor also
        # sorts items by this key, so using document order here would size a
        # different set of items per wrapped line than the one it places.
        # Python's stable sort preserves source order for equal CSS order.
        child_ids = sorted(
            children[node_id], key=lambda child: styles[child].order,
        )
        # Resolve only the main axis before flexing.  The auto cross axis is
        # determined from the resulting flex lines below.  Eagerly replacing
        # an auto column width with an intrinsic guess made wrapped columns
        # use a different cross size than their actual children.
        # Intrinsic main-axis wrap has no certified line-formation reference.
        if style.wrap != FlexWrap.NOWRAP and (
            (horizontal and width is None and style.max_width.kind != LengthKind.PX)
            or (not horizontal and height is None and style.max_height.kind != LengthKind.PX)
        ):
            raise SFLECapabilityError(
                DiagnosticCode.UNSUPPORTED_FEATURE,
                "Intrinsically auto-sized Flex wrap without definite main axis is deferred.",
                node_id,
            )
        if horizontal and width is None:
            width = preferred(node_id, True)
        if not horizontal and height is None:
            height = preferred(node_id, False)
        if width is not None:
            width = bounded_intrinsic(style, True, width, parent_width)
        if height is not None:
            height = bounded_intrinsic(style, False, height, parent_height)
        main_size = width if horizontal else height
        assert main_size is not None
        # Intrinsically auto-sized main axes are NOT percentage-definite simply
        # because the intrinsic phase produced a finite provisional number.
        main_reference = main_size
        if horizontal and style.width.kind in (LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT) and forced_width is None:
            main_reference = None
        if not horizontal and style.height.kind in (LengthKind.AUTO, LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT) and forced_height is None:
            main_reference = None

        bases = []
        for child_id in child_ids:
            child_style = styles[child_id]
            basis = child_style.flex_basis
            basis_axis = child_style.width if horizontal else child_style.height
            cross_axis = child_style.height if horizontal else child_style.width
            cross_reference = height if horizontal else width
            transfer_cross = _axis_value(
                cross_axis, cross_reference,
                axis="height" if horizontal else "width", node_id=child_id,
            )
            alignment = child_style.align_self if child_style.align_self != CrossAlign.AUTO else style.align_items
            if (transfer_cross is None and cross_reference is not None
                    and style.wrap == FlexWrap.NOWRAP and alignment == CrossAlign.STRETCH):
                transfer_cross = cross_reference
            if (transfer_cross is None and child_style.aspect_ratio is not None
                    and child_id in measures):
                metric = measures[child_id].intrinsic
                transfer_cross = (metric.preferred_height if horizontal
                                  else metric.preferred_width)
            if transfer_cross is not None:
                transfer_cross = bounded_intrinsic(
                    child_style, not horizontal, transfer_cross, cross_reference,
                )
            transferred = None
            if transfer_cross is not None and child_style.aspect_ratio is not None:
                transferred = _layout_unit(
                    transfer_cross * child_style.aspect_ratio if horizontal
                    else transfer_cross / child_style.aspect_ratio
                )
            if basis.kind == LengthKind.AUTO:
                desired = _axis_value(basis_axis, main_reference, axis="width" if horizontal else "height", node_id=child_id)
                if desired is None:
                    desired = transferred if transferred is not None else preferred(child_id, horizontal)
            elif basis.kind == LengthKind.PX:
                desired = basis.value
            elif basis.kind == LengthKind.PERCENT:
                desired = _percent_flex_basis_used(basis.value, main_reference) if main_reference is not None else preferred(child_id, horizontal)
            elif basis.kind in (LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT):
                if child_id not in measures and not children[child_id]:
                    raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                    "Intrinsic flex basis requires measured leaf content.", child_id)
                if child_id in measures and not children[child_id]:
                    intrinsic = measures[child_id].intrinsic
                    desired = (intrinsic.min_content_width if horizontal else intrinsic.min_content_height) if basis.kind == LengthKind.MIN_CONTENT else (intrinsic.max_content_width if horizontal else intrinsic.max_content_height)
                else:
                    desired = preferred(child_id, horizontal, basis.kind == LengthKind.MIN_CONTENT)
            else:
                raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE, "Unsupported flex basis keyword.", child_id)
            assert desired is not None
            min_length = child_style.min_width if horizontal else child_style.min_height
            if min_length.kind == LengthKind.PX:
                minimum = min_length.value
            elif min_length.kind == LengthKind.AUTO:
                minimum = 0.0 if child_style.scroll_container else preferred(child_id, horizontal, True)
                if transferred is not None:
                    minimum = (min(minimum, transferred) if child_style.replaced
                               else max(minimum, transferred))
                specified = _axis_value(basis_axis, main_reference,
                                        axis="width" if horizontal else "height", node_id=child_id)
                if specified is not None:
                    minimum = min(minimum, specified)
            elif min_length.kind == LengthKind.PERCENT and main_reference is not None:
                minimum = _percent_used_dimension(min_length.value, main_reference)
            elif min_length.kind == LengthKind.PERCENT:
                # CSS min-size percentages without a definite containing
                # axis remain automatic during intrinsic flex sizing.
                minimum = 0.0 if child_style.scroll_container else preferred(child_id, horizontal, True)
                if transferred is not None:
                    minimum = (min(minimum, transferred) if child_style.replaced
                               else max(minimum, transferred))
            assert minimum is not None
            max_length = child_style.max_width if horizontal else child_style.max_height
            if max_length.kind == LengthKind.PX:
                maximum = max_length.value
            elif max_length.kind == LengthKind.AUTO:
                maximum = None
            elif max_length.kind == LengthKind.PERCENT and main_reference is not None:
                maximum = _percent_used_dimension(max_length.value, main_reference)
            elif max_length.kind == LengthKind.PERCENT:
                # An indefinite percentage maximum is not a numeric cap in
                # this intrinsic pass; retain the CSS unconstrained branch.
                maximum = None
            if min_length.kind == LengthKind.AUTO and maximum is not None:
                minimum = min(minimum, maximum)
            if maximum is not None and maximum < minimum:
                maximum = minimum
            hypo = min(max(desired, minimum), maximum) if maximum is not None else max(desired,minimum)
            bases.append(FlexBasis(desired, hypo,
                                    grow=child_style.grow,shrink=child_style.shrink,
                                    min_size=minimum,max_size=maximum))
        inline_size = width if width is not None else 0.0
        main_gap = _main_gap(style,inline_size,height if height is not None else 0.0,node_id)
        edges = {
            child: UsedBoxEdges(
                padding=_padding(styles[child], inline_size, child),
                border=_border(styles[child], child),
            )
            for child in child_ids
        }
        main_size, main_gap = _layout_unit(main_size), _layout_unit(main_gap)
        def fixed_margin(length: Length) -> float:
            if length.kind == LengthKind.AUTO:
                return 0.0
            if length.kind == LengthKind.PX:
                return _layout_unit(length.value)
            if length.kind == LengthKind.PERCENT:
                used = length.value * inline_size
                if math.isinf(used):
                    return LayoutUnit.from_raw(I32_MAX if used > 0 else I32_MIN).to_px()
                return _layout_unit(used)
            raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                      "Unsupported margin length.", node_id)

        fixed_edges = []
        for child in child_ids:
            e, s = edges[child], styles[child]
            fixed_edges.append(_sum_units((e.padding.left, e.padding.right, e.border.left, e.border.right, fixed_margin(s.margin_left),
                                          fixed_margin(s.margin_right))) if horizontal else
                               _sum_units((e.padding.top, e.padding.bottom, e.border.top, e.border.bottom, fixed_margin(s.margin_top),
                                           fixed_margin(s.margin_bottom))))
        # CSS 9.3 collects outer hypothetical sizes before flexing each line.
        lines: list[list[int]] = [[]]
        occupied = 0.0
        for index, basis in enumerate(bases):
            outer = _sum_units((basis.hypothetical, fixed_edges[index]))
            candidate = _sum_units((occupied, main_gap if lines[-1] else 0.0, outer))
            if style.wrap != FlexWrap.NOWRAP and lines[-1] and candidate > main_size:
                lines.append([])
                occupied = 0.0
            occupied = _sum_units((occupied, main_gap if lines[-1] else 0.0, outer))
            lines[-1].append(index)
        targets = [0.0] * len(bases)
        for line in lines:
            available = max(0.0, _subtract_units(main_size, (fixed_edges[i] for i in line)))
            for index, target in zip(line, _blink_flex_targets(
                tuple(bases[i] for i in line), available, main_gap, node_id=node_id,
            )):
                targets[index] = target
        cross_sizes = []
        for child_id, target in zip(child_ids, targets):
            child_style = styles[child_id]
            if horizontal:
                cross = _axis_value(child_style.height,height,axis="height",node_id=child_id)
                alignment = child_style.align_self if child_style.align_self != CrossAlign.AUTO else style.align_items
                if (cross is None and height is not None and alignment == CrossAlign.STRETCH
                        and style.wrap == FlexWrap.NOWRAP
                        and child_style.margin_top.kind != LengthKind.AUTO
                        and child_style.margin_bottom.kind != LengthKind.AUTO):
                    cross = max(0.0, _subtract_units(height, (edges[child_id].padding.top,
                        edges[child_id].padding.bottom, edges[child_id].border.top, edges[child_id].border.bottom, fixed_margin(child_style.margin_top),
                        fixed_margin(child_style.margin_bottom))))
                child_width, child_height = layout(child_id,target,cross,width,height)
                # Auto cross-size contains each child outer padding box. A
                # nested column's content-only height undercounts the row.
                cross_sizes.append(max(0.0, _sum_units((child_height, edges[child_id].padding.top,
                    edges[child_id].padding.bottom, edges[child_id].border.top, edges[child_id].border.bottom, fixed_margin(child_style.margin_top),
                    fixed_margin(child_style.margin_bottom)))))
            else:
                cross = _axis_value(child_style.width,width,axis="width",node_id=child_id)
                alignment = child_style.align_self if child_style.align_self != CrossAlign.AUTO else style.align_items
                if (cross is None and width is not None and alignment == CrossAlign.STRETCH
                        and style.wrap == FlexWrap.NOWRAP
                        and child_style.margin_left.kind != LengthKind.AUTO
                        and child_style.margin_right.kind != LengthKind.AUTO):
                    cross = max(0.0, _subtract_units(width, (edges[child_id].padding.left,
                        edges[child_id].padding.right, edges[child_id].border.left, edges[child_id].border.right, fixed_margin(child_style.margin_left),
                        fixed_margin(child_style.margin_right))))
                if (cross is None and width is not None
                        and child_style.width.kind is LengthKind.AUTO
                        and alignment is not CrossAlign.STRETCH):
                    # A non-stretched column flex item's auto inline size is
                    # shrink-to-fit: min(max-content, max(min-content, available)).
                    # In particular, block <p> inside align-items:center
                    # may wrap in a narrow viewport but stays one line when
                    # its natural text width fits. Never force a fake fixed
                    # width or override an explicitly authored width.
                    available_cross = max(0.0, _subtract_units(width, (
                        edges[child_id].padding.left, edges[child_id].padding.right,
                        edges[child_id].border.left, edges[child_id].border.right,
                        fixed_margin(child_style.margin_left),
                        fixed_margin(child_style.margin_right),
                    )))
                    minimum = preferred(child_id, True, minimum=True)
                    maximum = preferred(child_id, True)
                    cross = min(maximum, max(minimum, available_cross))
                child_width, child_height = layout(child_id,cross,target,width,height)
                cross_sizes.append(max(0.0, _sum_units((child_width, edges[child_id].padding.left,
                    edges[child_id].padding.right, edges[child_id].border.left, edges[child_id].border.right, fixed_margin(child_style.margin_left),
                    fixed_margin(child_style.margin_right)))))
        if (horizontal and height is None) or (not horizontal and width is None):
            # An auto cross-size is finalized after children are laid out;
            # this is symmetric for rows (height) and columns (width), and
            # includes every wrapped line's outer cross contribution.
            line_sizes = [max((cross_sizes[i] for i in line), default=0.0) for line in lines]
            gap = _intrinsic_gap(style.row_gap if horizontal else style.column_gap, node_id)
            auto_cross = _sum_units(v for i, size in enumerate(line_sizes)
                                    for v in ((gap, size) if i else (size,)))
            if horizontal:
                height = bounded_intrinsic(style, False, auto_cross, parent_height)
            else:
                width = bounded_intrinsic(style, True, auto_cross, parent_width)
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
    if root_width is None and root_style.width.kind == LengthKind.AUTO and request.constraints.width.definite:
        root_width = request.constraints.width.value
    if root_height is None and root_style.height.kind == LengthKind.AUTO and request.constraints.height.definite:
        root_height = request.constraints.height.value
    layout(root,root_width,root_height,None,None)

    resolved = []
    def margin_value(value: Length, reference: float, node_id: str) -> UsedMargin:
        if value.kind == LengthKind.AUTO:
            return UsedMargin(None)
        if value.kind == LengthKind.PX:
            return UsedMargin(_layout_unit(value.value))
        if value.kind == LengthKind.PERCENT:
            used = value.value * reference
            if math.isinf(used):
                return UsedMargin(LayoutUnit.from_raw(
                    I32_MAX if used > 0 else I32_MIN,
                ).to_px())
            return UsedMargin(_layout_unit(used))
        raise SFLECapabilityError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                  "Unsupported margin length.", node_id)

    for node in request.nodes:
        node_id, parent_id = node.node_id,node.parent_id
        width,height = used[node_id]
        if parent_id is None:
            resolved.append(MarginTreeNode(node_id,None,width,height,
                edges=UsedBoxEdges(padding=_padding(styles[node_id], width, node_id),
                                   border=_border(styles[node_id], node_id)),
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
        item_edges = UsedBoxEdges(
            padding=_padding(styles[node_id], used[parent_id][0], node_id),
            border=_border(styles[node_id], node_id),
        )
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
            cross, edges=item_edges,
            main_start=main_start,main_end=main_end,
            cross_start=cross_start,cross_end=cross_end,
            align_self=item_st.align_self,
            order=item_st.order,
            cross_size_auto=False,
            # Native measurement owns both physical baseline axes. Passing
            # them through the immutable snapshot supports row and column
            # first-baseline groups without deriving one from widget bounds.
            baseline_from_cross_start=(
                min(cross, max(0.0, measured_baseline))
                if node_id in measures and (
                    measured_baseline := (
                        measures[node_id].intrinsic.baseline if main_horizontal
                        else measures[node_id].intrinsic.orthogonal_baseline
                    )
                ) is not None else None
            ),
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
