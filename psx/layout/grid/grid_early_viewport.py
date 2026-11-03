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
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.layout.adapters.grid_viewport_workset import (
    subtree_is_safe_for_root_culling,
)
from psx.layout.contracts.lengths import parse_length, LengthKind
from psx.layout.projection.native_layout_snapshot import path_identity


_NEGATIVE_MARGIN = re.compile(
    r"\bmargin(?:-top|-bottom|-left|-right)?\s*:\s*-\d", re.I,
)


def _negative(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return not isfinite(value) or value < 0
    if getattr(value, "kind", None) is not None:
        numeric = getattr(value, "value", None)
        return (isinstance(numeric, (int, float))
                and (not isfinite(numeric) or numeric < 0))
    if isinstance(value, str):
        return value.lstrip().startswith("-")
    if isinstance(value, (tuple, list)):
        return any(_negative(item) for item in value)
    return False


def _no_negative_margins(node):
    pending = [node]
    while pending:
        current = pending.pop()
        source = current.source
        props = getattr(source, "props", {}) or {}
        for name, value in props.items():
            if "margin" in str(name).lower() and _negative(value):
                return False
            if isinstance(value, str) and _NEGATIVE_MARGIN.search(value):
                return False
        css = getattr(getattr(source, "css_computed", None), "properties", None)
        if css is not None:
            for name, value in css.items():
                if "margin" in str(name).lower() and str(value).strip().startswith("-"):
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
    if (not subtree_is_safe_for_root_culling(grid)
            or not _no_negative_margins(grid)):
        return None
    packing = _uniform_fixed_rows(grid)
    if packing is None:
        return None
    per_row, row_gap = packing
    safe_ids = tuple(
        path_identity(item.path)
        if subtree_is_safe_for_root_culling(item) else None
        for item in grid.effective_children
    )
    return per_row, row_gap, safe_ids


def select_pre_measurement_deferred_flows(
    normalized, grid, accepted, workset, *,
    viewport_height, epoch, overscan=96.0,
    static_plan=None,
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
    per_row, row_gap, safe_ids = plan
    cutoff = float(viewport_height) + float(overscan)
    # Only a contiguous *tail of complete Grid rows* can be provisional.
    # Otherwise one structurally dependent later row could receive a Y based
    # on stale heights of an earlier P2 row, rather than true Cinnamon data.
    # All P0/P1 groups, including structurally unsafe cards, remain before
    # the first deferred row.
    proven = []
    receipts = getattr(workset, "_accepted", {})
    for index, identifier in enumerate(safe_ids):
        # Even zero-height earlier rows retain this minimum Y via row gaps.
        if ((index // per_row) * row_gap < cutoff or identifier is None):
            proven.append(False)
            continue
        prior = receipts.get(identifier)
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
