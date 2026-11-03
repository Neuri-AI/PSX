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


def _no_negative_margins(node):
    pending = [node]
    while pending:
        current = pending.pop()
        source = current.source
        props = getattr(source, "props", {}) or {}
        for name, value in props.items():
            if "margin" in str(name).lower() and str(value).strip().startswith("-"):
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
    if css is not None and getattr(css, "specified", ()):
        return False
    return subtree_is_safe_for_root_culling(root) and _no_negative_margins(root)


def select_pre_measurement_deferred_flows(
    normalized, grid, accepted, workset, *,
    viewport_height, epoch, overscan=96.0,
):
    """Select previously accepted Flow cards proven below even a zero-height grid.

    Fail closed on any missing geometry receipt or uncertain CSS/layout.
    The returned values are *prior accepted Flow geometry*, NOT valid new
    width-specific solved output. Callers MUST mark them provisional and
    reconcile with full width-dependent measurement at idle.
    """
    if not _plain_root_grid(normalized, grid):
        return {}
    if not subtree_is_safe_for_root_culling(grid) or not _no_negative_margins(grid):
        return {}
    packing = _uniform_fixed_rows(grid)
    if packing is None:
        return {}
    if not isinstance(viewport_height, (int, float)) or viewport_height <= 0:
        return {}
    if (accepted is None or accepted.grid.source is not grid.source
            or workset is None):
        return {}
    per_row, row_gap = packing
    cutoff = float(viewport_height) + float(overscan)
    selected = {}
    for index, item in enumerate(grid.effective_children):
        # All real row heights are nonnegative. Even if EVERY previous row
        # collapses to zero at the target width, the row-gap lower bound
        # still proves this item remains below the viewport.
        if (index // per_row) * row_gap < cutoff:
            continue
        identifier = path_identity(item.path)
        prior = getattr(workset, "_accepted", {}).get(identifier)
        if (prior is None or prior.epoch != epoch
                or prior.native_y < cutoff):
            continue
        previous_flow = accepted.nested_flow.get(identifier)
        if previous_flow is None:
            continue
        # A text-only Flow must be free of independent native listeners or
        # paint escape. A fresh CSS or widget identity changes the shared
        # normalized tree and drops the accepted cache before this step.
        if not subtree_is_safe_for_root_culling(item):
            continue
        selected[identifier] = previous_flow
    return selected
