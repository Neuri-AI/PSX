"""UI-thread-only reuse of immutable PSX structure between viewport resizes.

Unlike solver result/intrinsic caches, this contains *no native geometry* and
does not freeze CSS viewport units. Fresh generation/constraint bindings and
CSS geometry projection happen on every transaction.

The mounted signature is constructed while adapters already validate/live-walk
their widgets. It covers mounted identity, resolved components, child order,
VNode props, and immutable CSS snapshots. This is one bounded cache entry.
"""
from __future__ import annotations

from dataclasses import replace

from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot


def mounted_structural_token(instance):
    """Identity-only token: never hash or stringify an entire CSS subtree."""
    node = instance.node
    return (
        id(instance), id(node), id(instance.handle),
        id(node.props), id(node.css_computed), id(node.css_stylesheet),
        id(node.css_source), id(node.markup_meta),
        tuple(id(child) for child in instance.children),
    )


class NativeStructuralSnapshotReuse:
    """A single pure tree projection, retained until the next structural edit."""

    def __init__(self):
        self.hits = 0
        self.builds = 0
        self.clear()

    def clear(self):
        self._root = None
        self._stamp = None
        self._epoch = None
        self._normalized = None
        self._prepared = None

    def prepare(self, root, components, stamp, constraints, generation, epoch):
        token = tuple(stamp)
        if (self._root is root and self._stamp == token
                and self._epoch == epoch and self._prepared is not None):
            # Rebinding only the wire metadata is safe. It is *not* safe to
            # reuse CSS geometry, native measurements, or solver rectangles.
            self.hits += 1
            rebound = replace(
                self._prepared,
                snapshot=replace(
                    self._prepared.snapshot,
                    generation=generation,
                    constraints=constraints,
                ),
            )
            return self._normalized, rebound
        normalized = normalize_flex_tree(root, component_roots=components)
        self.builds += 1
        prepared = prepare_native_layout_snapshot(
            normalized, constraints, generation=generation,
        )
        self._root = root
        self._stamp = token
        self._epoch = epoch
        self._normalized = normalized
        self._prepared = prepared
        return normalized, prepared
