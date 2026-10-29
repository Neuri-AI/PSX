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

from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import LayoutConstraints

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
        self.projections = 0
        self.projection_hits = 0
        self.clear()

    def clear(self):
        self._root = None
        self._stamp = None
        self._epoch = None
        self._normalized = None
        self._prepared = None
        self._css_projection = None
        self._css_viewport_independent = False

    @staticmethod
    def _can_reuse_css_projection(prepared):
        """Only skip CSS reprojection if no participating style uses vw/vh."""
        viewport = {LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX}
        suffixes = ("vw", "vh", "vmin", "vmax")

        def dependent(value):
            if isinstance(value, Length):
                return value.kind in viewport
            if isinstance(value, str):
                # Conservative on purpose: false positives cost performance,
                # whereas missing a viewport unit would change CSS pixels.
                return any(unit in value.lower() for unit in suffixes)
            if isinstance(value, (tuple, list)):
                return any(dependent(child) for child in value)
            return False

        for wire in prepared.snapshot.nodes:
            if any(dependent(value) for _, value in wire.style):
                return False
        for _, source in prepared.identities:
            computed = source.css_computed
            if computed is not None:
                properties = getattr(computed, "properties", None)
                specified = getattr(computed, "specified", ())
                if properties is not None and any(
                    dependent(properties[key])
                    for key in specified if key in properties
                ):
                    return False
        return True

    def project_css(self, prepared):
        """Rebind unchanged CSS *styles*, never cached geometry/measurements."""
        cached = self._css_projection
        if cached is not None and self._css_viewport_independent:
            # A CSS Flex root with auto block-size deliberately makes its
            # containing height indefinite. Reproduce that root transform
            # while rebinding today's viewport width and generation.
            initial = self._prepared.snapshot.constraints
            current = prepared.snapshot.constraints
            old = cached.constraints
            height = old.height if old.height != initial.height else current.height
            constraints = LayoutConstraints(current.width, height)
            self.projection_hits += 1
            return replace(
                cached, generation=prepared.snapshot.generation,
                constraints=constraints,
                measurements=prepared.snapshot.measurements,
            )
        projected = prepared.css_geometry_snapshot()
        self.projections += 1
        if self._css_viewport_independent:
            self._css_projection = projected
        return projected


    def normalize(self, root, components, stamp, epoch):
        """Validate once per mounted structure, including direct Grid roots."""
        token = tuple(stamp)
        if (self._root is root and self._stamp == token
                and self._epoch == epoch and self._normalized is not None):
            self.hits += 1
            return self._normalized
        normalized = normalize_flex_tree(root, component_roots=components)
        self.builds += 1
        self._root = root
        self._stamp = token
        self._epoch = epoch
        self._normalized = normalized
        # A new mounted tree invalidates both the canonical projection
        # and its CSS projection, including any cached auto-height root.
        self._prepared = None
        self._css_projection = None
        self._css_viewport_independent = False
        return normalized

    def prepare(self, root, components, stamp, constraints, generation, epoch):
        normalized = self.normalize(root, components, stamp, epoch)
        if self._prepared is not None:
            # Canonical metadata can be rebound, but intrinsic/solver values
            # are always rebuilt on the calling UI thread.
            rebound = replace(
                self._prepared,
                snapshot=replace(
                    self._prepared.snapshot,
                    generation=generation,
                    constraints=constraints,
                ),
            )
            return normalized, rebound
        prepared = prepare_native_layout_snapshot(
            normalized, constraints, generation=generation,
        )
        self._prepared = prepared
        self._css_projection = None
        self._css_viewport_independent = self._can_reuse_css_projection(prepared)
        return normalized, prepared
