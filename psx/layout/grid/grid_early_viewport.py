"""Conservative pre-measurement P2 selection for a uniform root Grid.

Unlike post-solve native culling, this runs *before* measuring nested Flow
cards or invoking the Grid solver. The sole permitted shortcut is to carry
forward a previously committed, immutable Flow subtree as a temporary
intrinsic-size receipt when BOTH of these facts are proven:

* its existing native rect lies below the clipped application viewport; and
* even the mathematical *minimum* new Grid row Y lies below the viewport.

The minimum row bound is derived from nonnegative row gaps (and optionally
strictly positive static card edges), never from an estimated text height.
No negative margins, transforms, Scroll hosts, interactive/native nodes,
overlays or responsive row packing are allowed. Offscreen outputs are marked
provisional and MUST be fully solved at resize idle or scroll reentry.
"""
from __future__ import annotations

import re
from math import isfinite

from psx.core.grid_contract import (
    normalize_grid_props, normalize_grid_item_props,
)
from psx.core.vnode import NodeKind
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.layout.adapters.grid_viewport_workset import (
    subtree_is_safe_for_root_culling,
)
from psx.layout.contracts.lengths import parse_length, LengthKind, Length
from psx.layout.projection.native_layout_snapshot import path_identity


_NEGATIVE_MARGIN = re.compile(
    r"\bmargin(?:-top|-bottom|-left|-right)?\s*:\s*-\d", re.I,
)


def _negative(value):
    """True if a margin might be negative under *any* target viewport.

    Unknown expressions and auto margins are not safe proof inputs. The
    selector is free to miss a culling opportunity, never to guess safety.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return not isfinite(value) or value < 0
    if isinstance(value, (tuple, list)):
        return any(_negative(item) for item in value)
    try:
        length = parse_length(value)
    except (ValueError, TypeError):
        return True
    numeric = getattr(length, "value", None)
    if (length.kind not in (LengthKind.PX, LengthKind.PERCENT)
            or not isinstance(numeric, (int, float))):
        return True
    return not isfinite(numeric) or numeric < 0


def _no_negative_margins(node):
    pending = [node]
    while pending:
        current = pending.pop()
        source = current.source
        props = getattr(source, "props", {}) or {}
        for name, value in props.items():
            if "margin" in str(name).lower() and _negative(value):
                return False
            if str(name) == "style" and isinstance(value, str):
                for declaration in value.split(";"):
                    if ":" not in declaration:
                        continue
                    property_name, specified = declaration.split(":", 1)
                    if "margin" in property_name.strip().lower():
                        if any(_negative(token) for token in specified.split()):
                            return False
            if isinstance(value, str) and _NEGATIVE_MARGIN.search(value):
                return False
        css = getattr(getattr(source, "css_computed", None), "properties", None)
        if css is not None:
            for name, value in css.items():
                if "margin" in str(name).lower() and _negative(value):
                    return False
        pending.extend(current.effective_children)
    return True


def _uniform_fixed_rows(grid):
    """Return items-per-row and guaranteed nonnegative row-gap, or None.

    A fixed nonresponsive span, no offset, and a complete 12-column packing
    are mandatory. Variable GridItem placement/row spans require a general
    dependency solver and are handled by the existing full path.
    """
    items = grid.effective_children
    if not items:
        return None
    try:
        grid_props = normalize_grid_props(grid.source.props)
        gap = parse_length(grid_props["row_gap"])
        if gap.kind is not LengthKind.PX or gap.value < 0:
            return None
        span = None
        for item in items:
            props = normalize_grid_item_props(item.source.props)
            if type(props["span"]) is not int or props["offset"] != 0:
                return None
            if span is None:
                span = props["span"]
            elif props["span"] != span:
                return None
        if span is None or 12 % span:
            return None
        return 12 // span, float(gap.value)
    except (TypeError, ValueError, KeyError):
        return None


def _plain_root_grid(normalized, grid):
    """Only a Grid at the window root or inside an unstyled sole block child."""
    roots = normalized._participating_roots()
    if len(roots) != 1:
        return False
    root = roots[0]
    if root is grid:
        return True
    if (root.type not in FORMATTING_TAGS
            or len(root.effective_children) != 1
            or root.effective_children[0] is not grid):
        return False
    # Do not let a positioned/translated/negative-margin ancestor invalidate
    # the row-gap lower bound in window coordinates.
    props = getattr(root.source, "props", {}) or {}
    if any(key != "display" for key in props):
        return False
    if props.get("display", "block") != "block":
        return False
    css = getattr(root.source, "css_computed", None)
    if css is not None:
        specified = set(getattr(css, "specified", ()))
        # The HTML constructor authors display:block by default. That
        # declaration is not a geometry escape or an external dependency.
        if specified - {"display"}:
            return False
        properties = getattr(css, "properties", {}) or {}
        if "display" in specified and properties.get("display") != "block":
            return False
    return subtree_is_safe_for_root_culling(root) and _no_negative_margins(root)


def build_early_viewport_plan(normalized, grid):
    """Pure structural CSS/row proof, cacheable under mounted-tree identity."""
    if normalized is None or not _plain_root_grid(normalized, grid):
        return None
    # ``_plain_root_grid`` has already certified the sole root subtree.
    # Both predicates are hereditary (they reject on the first unsafe
    # descendant), so re-walking the Grid and each of its cards repeats the
    # same CSS scan O(cards) times during the first resize.
    packing = _uniform_fixed_rows(grid)
    if packing is None:
        return None
    per_row, row_gap = packing
    safe_ids = tuple(path_identity(item.path) for item in grid.effective_children)
    props = normalize_grid_props(grid.source.props)
    column_gap = parse_length(props["column_gap"])
    return (per_row, row_gap, safe_ids, _monotonic_normal_flow(grid),
            float(column_gap.value) if column_gap.kind is LengthKind.PX else None)


def _monotonic_normal_flow(grid):
    """Prove shrinking a normal text card cannot move later rows upward."""
    allowed = {"GridItem", "div", "p", "Text"}
    stack = list(grid.effective_children)
    while stack:
        node = stack.pop()
        if node.kind is not NodeKind.HOST or node.type not in allowed:
            return False
        props = getattr(node.source, "props", {}) or {}
        if any(name in props for name in (
            "width", "height", "layout_width", "layout_height",
            "min_width", "max_width", "min_height", "max_height",
        )):
            return False
        computed = getattr(node.source, "css_computed", None)
        if computed is not None:
            properties = getattr(computed, "properties", {})
            specified = getattr(computed, "specified", ())
            for name in specified:
                value = properties.get(name)
                key = str(name).replace("_", "-")
                if (isinstance(value, Length)
                        and value.kind not in (LengthKind.PX, LengthKind.AUTO, LengthKind.NONE)):
                    return False
                if key == "display" and value not in ("block", None):
                    return False
                if key in ("width", "height", "min-width", "max-width",
                           "min-height", "max-height", "aspect-ratio"):
                    return False
                if any(part in key for part in ("margin", "padding", "border")):
                    if key.endswith(("color", "style", "radius")):
                        continue
                    try:
                        length = parse_length(value)
                    except (TypeError, ValueError):
                        return False
                    if length.kind is not LengthKind.PX or length.value < 0:
                        return False
                if isinstance(value, str) and any(unit in value.lower()
                                                  for unit in ("%", "vw", "vh", "vmin", "vmax")):
                    return False
        stack.extend(node.effective_children)
    return True


def select_pre_measurement_deferred_flows(
    normalized, grid, accepted, workset, *,
    viewport_height, epoch, overscan=96.0,
    static_plan=None, content_width=None,
):
    """Select previously accepted Flow cards proven below even a zero-height grid.

    Fail closed on any missing geometry receipt or uncertain CSS/layout.
    The returned values are *prior accepted Flow geometry*, NOT valid new
    width-specific solved output. Callers MUST mark them provisional and
    reconcile with full width-dependent measurement at idle.
    """
    if not isinstance(viewport_height, (int, float)) or (
        not isfinite(viewport_height) or viewport_height <= 0
    ):
        return {}
    if (accepted is None or accepted.grid.source is not grid.source
            or workset is None):
        return {}
    plan = (static_plan if static_plan is not None
            else build_early_viewport_plan(normalized, grid))
    if plan is None:
        return {}
    per_row, row_gap, safe_ids, normal_flow, _column_gap = plan
    cutoff = float(viewport_height) + float(overscan)
    prior_width = getattr(accepted, "content_width", 0.0)
    monotonic_shrink = (
        isinstance(content_width, (int, float)) and isfinite(content_width)
        and isinstance(prior_width, (int, float)) and isfinite(prior_width)
        and prior_width > 0 and content_width <= prior_width
        and normal_flow
    )
    # Only a contiguous *tail of complete Grid rows* can be provisional.
    # Otherwise one structurally dependent later row could receive a Y based
    # on stale heights of an earlier P2 row, rather than true Cinnamon data.
    # All P0/P1 groups, including structurally unsafe cards, remain before
    # the first deferred row.
    proven = []
    receipts = getattr(workset, "_accepted", {})
    minimum_y = 0.0
    previous_row_floor = 0.0
    for index, identifier in enumerate(safe_ids):
        if index % per_row == 0:
            if index:
                minimum_y += previous_row_floor + row_gap
            previous_row_floor = 0.0
        flow = accepted.nested_flow.get(identifier)
        if normal_flow and flow is not None:
            previous_row_floor = max(
                previous_row_floor, getattr(flow, "minimum_content_height", 0.0))
        # Even zero-height earlier rows retain this minimum Y via row gaps.
        if identifier is None:
            proven.append(False)
            continue
        prior = receipts.get(identifier)
        if monotonic_shrink and prior is not None:
            proven.append(bool(
                prior.epoch == epoch and prior.native_y >= cutoff
                and identifier in accepted.nested_flow
            ))
            continue
        if minimum_y < cutoff:
            proven.append(False)
            continue
        proven.append(bool(
            prior is not None and prior.epoch == epoch
            and prior.native_y >= cutoff
            and identifier in accepted.nested_flow
        ))
    last_structural = max(
        (index for index, ok in enumerate(proven) if not ok), default=-1,
    )
    first_row = (last_structural // per_row + 1) * per_row
    return {
        safe_ids[index]: accepted.nested_flow[safe_ids[index]]
        for index in range(first_row, len(safe_ids))
        if proven[index]
    }


def select_wider_unwrapped_flows(grid, accepted, *, content_width, static_plan=None):
    """Return exact Flow receipts that remain unwrapped at a wider width.

    This is intentionally separate from viewport P2 selection.  It is valid
    for visible cards too: every terminal native leaf previously reported a
    preferred width that fitted its definite probe, and ordinary block-flow
    width can only increase here.  A missing proof simply keeps the existing
    full measurement path.
    """
    if (accepted is None or accepted.grid.source is not grid.source
            or not isinstance(content_width, (int, float))
            or not isfinite(content_width)):
        return {}
    reusable = {}
    if static_plan is not None:
        per_row, _row_gap, safe_ids, normal_flow, column_gap = static_plan
        if not normal_flow or column_gap is None:
            return {}
        identifiers = safe_ids
    else:
        packing = _uniform_fixed_rows(grid)
        if packing is None or not _monotonic_normal_flow(grid):
            return {}
        per_row, _row_gap = packing
        gap = parse_length(normalize_grid_props(grid.source.props)["column_gap"])
        if gap.kind is not LengthKind.PX:
            return {}
        column_gap = gap.value
        identifiers = tuple(path_identity(item.path) for item in grid.effective_children)
    # Use a lower bound on Cinnamon's per-track rounding, not the entire
    # Grid width, when proving a text card cannot wrap.
    allocated_width = max(0.0, (content_width - (per_row - 1) * column_gap) / per_row - 1 / 64)
    for identifier in identifiers:
        flow = accepted.nested_flow.get(identifier)
        if (flow is not None
                and isinstance(getattr(flow, "unwrapped_at_width", None), (int, float))
                and flow.unwrapped_at_width <= allocated_width):
            reusable[identifier] = flow
    # A partial set is still exact for its own GridItems, but keeping a single
    # proof boundary makes future changes easier to audit and never masks a
    # structural child which needs current measurement.
    return reusable if len(reusable) == len(grid.effective_children) else {}
