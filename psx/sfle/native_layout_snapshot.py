"""Native SFLE: translate the already-normalized declarative tree to SFLE v1.

This is a lossless *style/identity* adapter, not a Flexbox implementation.
The engine alone distributes space; widgets supply intrinsic measurements
and native adapters apply immutable rectangles. Structural PSX boundaries
never turn into invisible SFLE layout boxes.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from psx.core.layout_tree import LayoutPath, NormalizedLayoutNode
from psx.core.props import FLEX_ITEM_PROPS
from psx.core.vnode import NodeKind, VNode

from .canonical_box_style import CanonicalItemBoxStyle, normalize_item_box_style
from .errors import DiagnosticCode, SFLECapabilityError, SFLEError
from .lengths import Length
from .model import LayoutConstraints, LayoutInput, LayoutNode, MeasuredBox, WritingDirection

_ITEM_STYLE = FLEX_ITEM_PROPS
_FLEX_STYLE = frozenset({
    "direction", "wrap", "justify_content", "align_items", "align_content",
    "width", "height", "min_width", "min_height", "max_width", "max_height",
    "row_gap", "column_gap",
})
_SIDE_NAMES = ("top", "right", "bottom", "left")
_SKIP_DEFAULT = {"auto", "none"}


def path_identity(path: LayoutPath) -> str:
    """Deterministic key-aware ID; no Python object address is serialized."""
    if not path:
        raise ValueError("A normalized layout path must not be empty.")
    return repr(path)


@dataclass(frozen=True, slots=True)
class PreparedNativeLayoutSnapshot:
    """Immutable SFLE input plus the exact originating PSX node identities."""

    snapshot: LayoutInput
    identities: tuple[tuple[str, VNode], ...]
    box_styles: tuple[tuple[str, CanonicalItemBoxStyle], ...] = ()
    viewport_constraints: LayoutConstraints | None = None

    def _resolve_viewport_units(self, snapshot: LayoutInput) -> LayoutInput:
        """Convert viewport lengths at Cinnamon's input boundary.

        The window content dimensions are the reference, not the size of each
        descendant box. Neither the stylesheet nor the VNode is mutated.
        """
        from .lengths import Length, LengthKind, parse_length, resolve_viewport_length
        viewport_kinds = {LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX}
        window = self.viewport_constraints or self.snapshot.constraints
        w = window.width.value
        h = window.height.value
        converted = []
        changed = False
        for node in snapshot.nodes:
            # Most Grid/Flex layouts contain no viewport units. Avoid
            # allocating a style dict, sorted tuple and LayoutNode for every
            # such node on every width-dependent measurement.
            style = None
            for name, original in node.style:
                value = original
                if isinstance(value, str) and value.strip().lower().endswith(("vw", "vh", "vmin", "vmax")):
                    value = parse_length(value)
                if isinstance(value, Length) and value.kind in viewport_kinds:
                    if w is None or h is None:
                        raise SFLECapabilityError(
                            DiagnosticCode.LAYOUT_CONSTRAINT,
                            "Viewport units require known window content dimensions.",
                        )
                    if style is None:
                        style = dict(node.style)
                    style[name] = resolve_viewport_length(value, w, h)
            if style is None:
                converted.append(node)
            else:
                converted.append(replace(node, style=tuple(sorted(style.items()))))
                changed = True
        return replace(snapshot, nodes=tuple(converted)) if changed else snapshot

    def css_geometry_snapshot(self, *, pixel_scale: float = 1.0) -> LayoutInput:
        """Project computed CSS geometry into typed Cinnamon input, opt-in.

        Explicit layout_* metadata always wins; CSS never overwrites native
        widget-owned props. This returns new immutable input, never a native
        geometry write, and remains independent of renderer backends.
        """
        from psx.css.geometry import css_layout_overrides

        from math import isfinite
        if isinstance(pixel_scale, bool) or not isinstance(pixel_scale, (int, float)) or not isfinite(pixel_scale) or pixel_scale <= 0:
            raise ValueError("CSS pixel scale must be finite and positive.")
        # Scale authored PX before resolving vw/vh against native drawable bounds;
        # scaling after viewport resolution would multiply viewport units twice.
        baseline = (self.canonical_snapshot() if pixel_scale == 1.0
                    else self.canonical_snapshot(resolve_viewport=False))
        originals = dict(self.identities)
        converted: list[LayoutNode] = []
        for node in baseline.nodes:
            original = originals[node.node_id]
            computed = original.css_computed
            overrides = css_layout_overrides(computed) if computed is not None else {}
            explicit = set(original.props)
            style = dict(node.style)
            for key, value in overrides.items():
                if key not in explicit:
                    style[key] = value
            if computed is not None:
                for css, target in (
                    ("flex-grow", "flex_grow"),
                    ("flex-shrink", "flex_shrink"),
                    ("flex-basis", "flex_basis"),
                    ("align-self", "align_self"),
                    ("order", "order"),
                ):
                    if css in computed.specified and target not in explicit:
                        style[target] = computed.properties[css]
            component = node.component
            if computed is not None and original.kind is NodeKind.HOST:
                from psx.markup.html_aliases import FORMATTING_TAGS
                if original.type in FORMATTING_TAGS:
                    specified = computed.specified
                    display = (computed.properties["display"] if "display" in specified
                               else original.props.get("display", "block"))
                    if display in ("flex", "inline-flex"):
                        component = "Flex"
                        style.pop("display", None)
                        for css, target in (
                            ("flex-direction", "direction"),
                            ("flex-wrap", "wrap"),
                            ("justify-content", "justify_content"),
                            ("align-items", "align_items"),
                            ("align-content", "align_content"),
                        ):
                            if css in specified:
                                style[target] = computed.properties[css]
                        if "flex-direction" not in specified:
                            style.setdefault("direction", "row")
                        if "gap" in specified:
                            style["row_gap"] = computed.properties["gap"]
                            style["column_gap"] = computed.properties["gap"]
                        if "row-gap" in specified:
                            style["row_gap"] = computed.properties["row-gap"]
                        if "column-gap" in specified:
                            style["column_gap"] = computed.properties["column-gap"]
                    elif "display" in specified:
                        style["display"] = display
            converted.append(replace(node, component=component,
                                     style=tuple(sorted(style.items()))))
        # A CSS flex item keeps its *own* inner formatting context. In
        # particular, a block-level <div> may contain inline-level native
        # controls (<button>, <input>, ...) whose default visual flow is
        # horizontal, even when the div itself is a child of a column Flex.
        # Pure native-control inline runs are projected as a wrapping row
        # while the HTML Block/Inline compositor is integrated with nested
        # Flex contexts. Do not rewrite explicitly authored display:flex
        # containers: their own flex-direction remains authoritative.
        from psx.markup.html_aliases import FORMATTING_TAGS
        inline_controls = frozenset({
            "Button", "Input", "TextArea", "Select", "Checkbox",
            "Radio", "Link", "Badge", "SpinBox", "Switch",
        })
        children_by_parent: dict[str, list[LayoutNode]] = {}
        for item in converted:
            if item.parent_id is not None:
                children_by_parent.setdefault(item.parent_id, []).append(item)

        def native_inline_run(parent_id: str) -> bool:
            direct = children_by_parent.get(parent_id, ())
            if not direct:
                return False
            for child in direct:
                origin = originals[child.node_id]
                if origin.kind is not NodeKind.HOST or origin.type not in inline_controls:
                    return False
                computed = origin.css_computed
                # An explicit display:block declaration makes a control a
                # block participant rather than an inline-level box.
                if (computed is not None and "display" in computed.specified
                        and computed.properties["display"] != "inline"):
                    return False
            return True

        mapped: dict[str, LayoutNode] = {}
        normalized = []
        for node in converted:
            parent = mapped.get(node.parent_id)
            origin = originals[node.node_id]
            style = dict(node.style)
            if (parent is not None and parent.component == "Flex"
                    and node.component != "Flex"
                    and origin.kind is NodeKind.HOST
                    and origin.type in FORMATTING_TAGS):
                display = style.get("display", origin.props.get("display"))
                if display in ("block", "inline"):
                    style.pop("display", None)
                    # CSS block children that are purely an inline control
                    # run receive row wrapping, preserving browser-like
                    # Button intrinsic widths instead of column stacking.
                    inline_run = display == "block" and native_inline_run(node.node_id)
                    style.setdefault("direction", "row" if (display == "inline" or inline_run) else "column")
                    if inline_run:
                        style.setdefault("wrap", "wrap")
                        style.setdefault("align_items", "flex-start")
                    node = replace(node, component="Flex",
                                   style=tuple(sorted(style.items())))
            normalized.append(node)
            mapped[node.node_id] = node
        constraints = baseline.constraints
        if normalized and normalized[0].component == "Flex":
            root_source = originals[normalized[0].node_id]
            from psx.markup.html_aliases import FORMATTING_TAGS
            root_style = dict(normalized[0].style)
            if (root_source.kind is NodeKind.HOST
                    and root_source.type in FORMATTING_TAGS
                    and "layout_height" not in root_style
                    and "height" not in root_style):
                # A CSS flex div has auto content height. The native window
                # remains viewport-sized, but its flex formatting context
                # must not inherit the viewport as a definite block size.
                from psx.sfle.model import AvailableSize, LayoutConstraints
                constraints = LayoutConstraints(
                    constraints.width, AvailableSize(None, False),
                )
        if pixel_scale != 1.0:
            from psx.sfle.lengths import Length, LengthKind, parse_length
            # CSS-computed edges are typed Length values, but native Flex
            # props can still enter as strings ("16px") or numeric CSS px.
            # All three representations must use the same drawable space.
            # Never scale dimensionless values such as flex-grow or order.
            length_keys = {
                "row_gap", "column_gap", "gap",
                "width", "height", "min_width", "min_height",
                "max_width", "max_height", "flex_basis",
            }

            def project_pixel_length(key: str, value: object) -> object:
                if isinstance(value, Length):
                    return (Length.px(value.value * pixel_scale)
                            if value.kind is LengthKind.PX else value)
                if not (key in length_keys or key.startswith("layout_")):
                    return value
                if type(value) in (int, float):
                    return Length.px(float(value) * pixel_scale)
                if isinstance(value, str):
                    try:
                        parsed = parse_length(value)
                    except (TypeError, ValueError):
                        return value
                    if parsed.kind is LengthKind.PX:
                        return Length.px(parsed.value * pixel_scale)
                return value

            normalized = [replace(node, style=tuple(sorted(
                (key, project_pixel_length(key, value))
                for key, value in node.style
            ))) for node in normalized]
        return self._resolve_viewport_units(replace(baseline, nodes=tuple(normalized), constraints=constraints))

    def canonical_snapshot(self, *, resolve_viewport: bool = True) -> LayoutInput:
        """Build engine-ready typed item lengths without changing source props.

        This is an explicit opt-in integration path. Existing native renderer
        callers continue to receive the same specified snapshot until the
        differential geometry and backend acceptance checks are certified.
        """
        if len(self.box_styles) != len(self.snapshot.nodes):
            raise ValueError("Every participating layout node needs one canonical box style.")
        origins = dict(self.identities)
        nodes: list[LayoutNode] = []
        for node, (identifier, box_style) in zip(self.snapshot.nodes, self.box_styles):
            if node.node_id != identifier or identifier not in origins:
                raise ValueError("Canonical box styles must follow snapshot node identities.")
            source_props = origins[identifier].props
            normalized = dict(node.style)
            for name, length in box_style.dimensions:
                if name in source_props and name in normalized:
                    normalized[name] = length
            for prefix, edges in (
                ("layout_margin_", box_style.margin),
                ("layout_padding_", box_style.padding),
                ("layout_border_", box_style.border),
            ):
                for side in _SIDE_NAMES:
                    name = prefix + side
                    if name in source_props and name in normalized:
                        normalized[name] = getattr(edges, side)
            nodes.append(replace(node, style=tuple(sorted(normalized.items()))))
        result = replace(self.snapshot, nodes=tuple(nodes))
        return self._resolve_viewport_units(result) if resolve_viewport else result


# Retain the old class name for existing internal imports during migration.
PreparedF3Snapshot = PreparedNativeLayoutSnapshot


def _edges(value: object) -> tuple[object, object, object, object]:
    """CSS shorthand: one / vertical-horizontal / top-right-bottom-left."""
    parts = tuple(value) if isinstance(value, (list, tuple)) else (value,)
    if len(parts) == 1:
        return parts * 4
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 4:
        return parts
    raise SFLEError(DiagnosticCode.INVALID_LENGTH, "Flex.padding needs 1, 2 or 4 edges.")


def _style(node: VNode) -> tuple[tuple[str, object], ...]:
    result: dict[str, object] = {}
    props = node.props
    for name in _ITEM_STYLE:
        if name in props:
            value = props[name]
            if name.startswith("layout_max_") and value == "none":
                continue  # CSS unbounded default: no SFLE max constraint.
            if name == "flex_basis" and value == "auto":
                continue
            if name.startswith("layout_min_") and value == "auto":
                continue
            if name in ("layout_width", "layout_height") and value == "auto":
                continue
            result[name] = value
    if node.kind is NodeKind.HOST and node.type == "Flex":
        for name in _FLEX_STYLE:
            if name not in props:
                continue
            value = props[name]
            if name in ("width", "height", "min_width", "min_height",
                        "max_width", "max_height") and value in _SKIP_DEFAULT:
                continue
            if name == "align_content" and value == "normal":
                continue  # The layout engine treats normal alignment as stretch.
            result[name] = value
        if "gap" in props:
            result.setdefault("row_gap", props["gap"])
            result.setdefault("column_gap", props["gap"])
        if "padding" in props:
            for side, value in zip(_SIDE_NAMES, _edges(props["padding"])):
                result.setdefault(f"layout_padding_{side}", value)
    from psx.markup.html_aliases import FORMATTING_TAGS
    if node.kind is NodeKind.HOST and node.type in FORMATTING_TAGS:
        result["display"] = props["display"]
    if node.kind is NodeKind.HOST and node.type == "Scroll":
        result["direction"] = (
            "row" if props["content_direction"] == "horizontal" else "column"
        )
        for axis in ("width", "height"):
            if props[axis] is not None and f"layout_{axis}" not in result:
                result[axis] = f"{props[axis]}px"
        result["align_items"] = "flex-start"
    if node.kind is NodeKind.HOST and node.type in ("Box", "RadioGroup", "Divider"):
        if node.type == "Box":
            result.setdefault("direction", "column")
            result.setdefault("width", "100%")
            result.setdefault("height", "100%")
        elif node.type == "RadioGroup":
            result["direction"] = (
                "row" if props["orientation"] == "horizontal" else "column"
            )
            result["row_gap"] = props["spacing"]
            result["column_gap"] = props["spacing"]
            for side, value in zip(_SIDE_NAMES, _edges(props["padding"])):
                result[f"layout_padding_{side}"] = value
        else:
            result["direction"] = (
                "row" if props["orientation"] == "horizontal" else "column"
            )
            result["justify_content"] = "center"
            result["align_items"] = "center"
    return tuple(sorted(result.items()))


def prepare_native_layout_snapshot(
    normalized: NormalizedLayoutNode,
    constraints: LayoutConstraints,
    *,
    generation: int,
    direction: WritingDirection = WritingDirection.LTR,
    measurements: Iterable[MeasuredBox] = (),
    viewport_constraints: LayoutConstraints | None = None,
) -> PreparedNativeLayoutSnapshot:
    """Create SFLE v1 input without native imports or implicit measurement.

    The effective root must be an explicit Flex or a bounded div Block root. Components/Fragments are
    transparent. Scroll is excluded pending the native viewport/content
    binding; fail closed rather than fabricating a layout root.
    Consumers must supply real measured leaf metrics as MeasuredBox values.
    No guess of an intrinsic size is permitted.
    """
    if not isinstance(normalized, NormalizedLayoutNode):
        raise TypeError("Expected a normalized layout tree.")
    roots = normalized._participating_roots()
    from psx.markup.html_aliases import FORMATTING_TAGS
    if len(roots) != 1 or roots[0].kind is not NodeKind.HOST or roots[0].type not in ({"Flex"} | FORMATTING_TAGS):
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            "Native SFLE requires one explicit Flex or supported Block root."
        )
    nodes: list[LayoutNode] = []
    origins: list[tuple[str, VNode]] = []
    box_styles: list[tuple[str, CanonicalItemBoxStyle]] = []
    seen: set[str] = set()

    def visit(node: NormalizedLayoutNode, parent_id: str | None) -> None:
        identifier = path_identity(node.path)
        if identifier in seen:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate normalized node identity.", identifier)
        if node.kind not in (NodeKind.HOST, NodeKind.NATIVE):
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Unresolved structural layout boundary.", identifier)
        if node.kind is NodeKind.HOST and node.type == "Scroll":
            from psx.sfle.native_scroll_viewport import require_scroll_content_root
            require_scroll_content_root(node)
        seen.add(identifier)
        name = str(node.type) if node.kind is NodeKind.HOST else "Native"
        # These hosts now participate as SFLE containers. Their native
        # adapters retain painting/selection, never place PSX children.
        if name in ("Box", "RadioGroup", "Scroll") or (
            name == "Divider" and node.effective_children
        ):
            name = "Flex"
        # A block formatting host nested in a Flex tree participates as a
        # column-sized item. Preserve its original VNode/native identity;
        # only the solver-facing formatting context changes. The dedicated
        # measured Block/Inline kernel still owns semantic flow roots.
        from psx.sfle.display_context import resolve_display, OuterDisplay, InnerDisplay
        nested_block = (
            roots[0].type == "Flex"
            and node.source.kind is NodeKind.HOST
            and node.source.type in FORMATTING_TAGS
            and resolve_display(node.source.type, node.source.props.get("display")).outer is OuterDisplay.BLOCK
            and resolve_display(node.source.type, node.source.props.get("display")).inner is InnerDisplay.FLOW
        )
        if nested_block:
            name = "Flex"
        # Preserve specified snapshot values for both layout engines while
        # carrying an immutable, typed box representation alongside them.
        box_props = (
            {key: val for key, val in node.source.props.items()
             if key != "display"}
            if node.source.kind is NodeKind.HOST and node.source.type in FORMATTING_TAGS
            else node.source.props
        )
        box_style = normalize_item_box_style(box_props, owner=str(node.type))
        style = dict(_style(node.source))
        if nested_block:
            style.pop("display", None)
            style["direction"] = "column"
        nodes.append(LayoutNode(identifier, parent_id, name, tuple(sorted(style.items()))))
        box_styles.append((identifier, box_style))
        origins.append((identifier, node.source))
        # A Grid participates in the enclosing Flex solver as one measured
        # leaf. Its descendants are resolved by Cinnamon Grid at the actual
        # width assigned to this box, never by the Flex solver or a toolkit.
        if name != "Grid":
            for child in node.effective_children:
                visit(child, identifier)

    visit(roots[0], None)
    snapshot = LayoutInput(
        1, generation, direction, constraints, tuple(nodes), tuple(measurements)
    )
    return PreparedNativeLayoutSnapshot(snapshot, tuple(origins), tuple(box_styles), viewport_constraints)
