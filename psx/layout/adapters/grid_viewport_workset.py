"""Conservative viewport worksets for a mounted application-root Grid.

This module never changes Cinnamon's solved rectangles or deallocates nodes.
It defers *native writes* only if a group was already committed outside the
clipped window, remains outside with 96 CSS px overscan, and contains no
unknown positioning, transforms or independently scrolled native widgets.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from psx.core.vnode import NodeKind

_OVERSCAN = 96.0
_UNSAFE_COMPONENTS = frozenset((
    "Scroll", "WebView", "Canvas", "Video", "WebEngine", "Native",
))
_UNSAFE_STYLES = frozenset((
    "transform", "filter", "backdrop-filter", "clip-path", "mask",
    "position", "top", "bottom", "left", "right", "inset",
    "translate", "rotate", "scale", "perspective", "mix-blend-mode",
    "overflow", "z-index", "opacity", "will-change", "contain",
    "box-shadow", "text-shadow", "outline",
))

def subtree_is_safe_for_root_culling(node: object) -> bool:
    """Never infer invisibility from overlap, transparency or z-order."""
    stack = [node]
    while stack:
        current = stack.pop()
        if current.kind is NodeKind.NATIVE or current.type in _UNSAFE_COMPONENTS:
            return False
        source = getattr(current, "source", None)
        props = getattr(source, "props", {}) or {}
        style = props.get("style")
        computed = getattr(source, "css_computed", None)
        css = getattr(computed, "properties", None)
        if computed is not None and not isinstance(css, Mapping):
            # Unknown CSS dependency: never infer native paint bounds.
            return False
        for mapping in (props, style, css):
            if not isinstance(mapping, Mapping):
                continue
            for key, value in mapping.items():
                normalized = str(key).replace("_", "-").lower()
                if normalized in _UNSAFE_STYLES:
                    # Computed styles contain CSS *defaults* even when the
                    # developer never authored the property. Rejecting all
                    # defaults would accidentally disable every workset.
                    benign = {
                        "position": ("static", None),
                        "overflow": ("visible", "hidden", "clip", None),
                        "opacity": (1, 1.0, "1", None),
                        "z-index": ("auto", 0, "0", None),
                        "box-shadow": ("none", None),
                        "text-shadow": ("none", None),
                        "outline": ("none", 0, "0", "0px", None),
                        "transform": ("none", None),
                        "filter": ("none", None),
                        "backdrop-filter": ("none", None),
                        "clip-path": ("none", None),
                        "mask": ("none", None),
                        "mix-blend-mode": ("normal", None),
                        "will-change": ("auto", None),
                        "contain": ("none", None),
                        "top": ("auto", None),
                        "bottom": ("auto", None),
                        "left": ("auto", None),
                        "right": ("auto", None),
                        "inset": ("auto", None),
                        "translate": ("none", None),
                        "rotate": ("none", None),
                        "scale": ("none", None),
                        "perspective": ("none", None),
                        "margin-top": (0, "0", "0px", None),
                        "margin-left": (0, "0", "0px", None),
                    }
                    if value in benign.get(normalized, (None,)):
                        continue
                    return False
        if isinstance(style, str) and any(k in style.lower() for k in _UNSAFE_STYLES):
            return False
        stack.extend(getattr(current, "effective_children", ()))
    return True

@dataclass(frozen=True, slots=True)
class _AcceptedGroup:
    # The last actually applied native Y remains unchanged on deferred work.
    native_y: float
    viewport_height: float
    tokens: tuple[tuple[str, int], ...]
    epoch: int
    # Opaque ancestor placement/identity proof, supplied by flow callers.
    # A moving ancestor changes a widget's effective screen coordinate
    # even when the child was not written.
    context: object = None

class GridViewportWorkset:
    """Keeps only widget identities; no handles or CSS geometry are retained."""

    def __init__(self) -> None:
        self._accepted: dict[str, _AcceptedGroup] = {}
        self._backend: object = None

    @staticmethod
    def _groups(root_ids, batch, widgets):
        roots = set(root_ids)
        groups = {}
        current = None
        for placement in batch:
            if placement.node_id in roots:
                current = placement.node_id
                if current in groups:
                    return {}
                groups[current] = []
            if current is None or placement.node_id not in widgets:
                return {}
            groups[current].append(placement)
        return groups if set(groups) == roots else {}

    def plan(self, *, root_ids, batch, widgets, viewport_height,
             epoch, backend, safe_ids, viewport_top=0.0, contexts=None):
        if (not isinstance(viewport_height, (int, float))
                or not isfinite(viewport_height) or viewport_height <= 0
                or not isinstance(viewport_top, (int, float))
                or not isfinite(viewport_top)):
            return frozenset()
        if self._backend is not None and self._backend != backend:
            self._accepted.clear()
        groups = self._groups(root_ids, batch, widgets)
        skipped = set()
        for root_id, descendants in groups.items():
            prior = self._accepted.get(root_id)
            anchor = descendants[0]
            tokens = tuple((p.node_id, id(widgets[p.node_id])) for p in descendants)
            geometry_safe = all(
                isfinite(p.y) and p.y >= 0 and isfinite(p.height)
                for p in descendants
            )
            if (root_id in safe_ids and geometry_safe and prior is not None
                    and prior.epoch == epoch and prior.tokens == tokens
                    and prior.context == (
                        contexts.get(root_id) if contexts is not None else None
                    )
                    # Test both the last *actually committed* geometry and
                    # Cinnamon's current target against the CURRENT scroll
                    # viewport. A formerly hidden item entering by scroll
                    # becomes active before native readback acceptance.
                    and prior.native_y >= viewport_top + viewport_height + _OVERSCAN
                    and anchor.y >= viewport_top + viewport_height + _OVERSCAN):
                skipped.update(p.node_id for p in descendants)
        return frozenset(skipped)

    def accept(self, *, root_ids, batch, widgets, viewport_height,
               epoch, backend, skipped, safe_ids=None, viewport_top=0.0,
               contexts=None):
        # safe_ids/viewport_top are plan-time hints. Acceptance records
        # only actually committed geometry after full native validation.
        groups = self._groups(root_ids, batch, widgets)
        if not groups:
            self._accepted.clear()
            return
        accepted = {}
        for root_id, descendants in groups.items():
            tokens = tuple((p.node_id, id(widgets[p.node_id])) for p in descendants)
            if root_id in skipped:
                prior = self._accepted.get(root_id)
                if (prior is None or prior.epoch != epoch or prior.tokens != tokens
                        or prior.context != (
                            contexts.get(root_id) if contexts is not None else None
                        )):

                    raise RuntimeError("Cannot accept unproven deferred Grid geometry.")
                accepted[root_id] = prior
            else:
                accepted[root_id] = _AcceptedGroup(
                    float(descendants[0].y), float(viewport_height), tokens, epoch,
                    contexts.get(root_id) if contexts is not None else None,
                )
        self._accepted = accepted
        self._backend = backend
