"""Commit-accepted, generation-safe reuse of solved native text subtrees.

A viewport resize must not synchronously remeasure/re-solve an offscreen or
otherwise unchanged text-only GridItem Flex/Flow context whose *effective*
containing width has already been certified. This is layout reuse, not native
widget virtualization: no widget is unmounted and every committed rectangle
continues to be projected/read back by its toolkit adapter.

Unknown/intrinsic controls, viewport-relative CSS, nested Grid/Scroll,
non-text native widgets and invalidation epochs fail closed to normal Cinnamon.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import replace

from psx.core.vnode import NodeKind
from psx.layout.contracts.lengths import Length, LengthKind


_UNSTABLE_SUFFIXES = ("vw", "vh", "vmin", "vmax", "%")
_UNSTABLE_KINDS = {
    LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX,
    LengthKind.PERCENT,
}


def _stable_values(origin) -> bool:
    def unstable(value):
        if isinstance(value, Length):
            return value.kind in _UNSTABLE_KINDS
        if isinstance(value, str):
            return value.strip().lower().endswith(_UNSTABLE_SUFFIXES)
        if isinstance(value, (tuple, list)):
            return any(unstable(item) for item in value)
        return False

    if any(unstable(value) for value in origin.props.values()):
        return False
    computed = origin.css_computed
    if computed is not None:
        properties = getattr(computed, "properties", None)
        if properties is None:
            return False
        if any(unstable(properties[name]) for name in getattr(computed, "specified", ())
               if name in properties):
            return False
    return True


def _signature(node):
    """Return immutable VNode/CSS identities for a pure Text layout only."""
    parts = []
    stack = [node]
    seen_text = False
    while stack:
        current = stack.pop()
        origin = current.source
        if current.kind is not NodeKind.HOST or not _stable_values(origin):
            return None
        if current.effective_children:
            if current.type not in ("Flex", "div", "p", "span", "h1", "h2",
                                    "h3", "h4", "h5", "h6", "section", "main",
                                    "header", "footer", "form", "label", "ul", "li"):
                return None
        elif current.type == "Text":
            seen_text = True
        else:
            return None
        parts.append((
            current.path, id(origin), id(origin.props), id(origin.css_computed),
            id(origin.css_stylesheet), id(origin.css_source),
        ))
        stack.extend(reversed(current.effective_children))
    return tuple(parts) if seen_text else None


class SolvedTextSubtreeReuse:
    """Small bounded pure-computation cache, published only after commit."""

    def __init__(self, limit=4096):
        self.limit = limit
        self._entries = OrderedDict()
        self._pending = {}
        self._generation = None
        self._epoch = None
        self.hits = 0
        self.misses = 0

    def begin(self, generation, epoch):
        if self._generation != generation or self._epoch != epoch:
            self._pending.clear()
            self._generation = generation
            self._epoch = epoch

    def _key(self, node, width, pixel_scale):
        from psx.layout.projection.native_layout_snapshot import path_identity
        return (id(node.source), path_identity(node.path),
                float(width), float(pixel_scale))

    def lookup(self, node, width, generation, epoch, *, pixel_scale=1.0):
        signature = _signature(node)
        if signature is None or self._epoch != epoch:
            return None
        key = self._key(node, width, pixel_scale)
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        old_root, old_signature, old_epoch, old = entry
        if (old_root is not node.source or old_signature != signature
                or old_epoch != epoch):
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        previous = old.prepared
        # Rebind all public generation contracts; no stale result is ever
        # returned to an outer current-generation commit.
        prepared = replace(
            previous, snapshot=replace(
                previous.snapshot, generation=generation,
            ),
        )
        computed = replace(old.result, generation=generation,
                           geometry_commit_error=None)
        if hasattr(old, "root"):
            return replace(old, root=node, prepared=prepared, result=computed)
        return replace(old, prepared=prepared, result=computed)

    def stage(self, node, width, epoch, solved, *, pixel_scale=1.0):
        signature = _signature(node)
        if signature is None or self._epoch != epoch:
            return
        if getattr(solved, "nested_grids", None):
            return
        key = self._key(node, width, pixel_scale)
        self._pending[key] = (node.source, signature, epoch, solved)

    def accept(self, generation, epoch):
        if generation != self._generation or epoch != self._epoch:
            self._pending.clear()
            return
        for key, entry in self._pending.items():
            self._entries[key] = entry
            self._entries.move_to_end(key)
        while len(self._entries) > self.limit:
            self._entries.popitem(last=False)
        self._pending.clear()

    def discard(self):
        self._pending.clear()
