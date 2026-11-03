"""Indexed exact Cinnamon tracks for certified repeated block-flow cards.

This is a compressed representation of the existing Rust Grid output, not a
layout solver. Rust supplies quantized column rectangles, row stride and the
validated document extent. Python resolves only requested logical identities
and materializes detailed Flow rectangles for the current native workset.
"""
from collections import ChainMap
from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import ceil, floor, isfinite
from types import MappingProxyType

from psx.layout.grid.contracts import GridConstrainedRect
from psx.layout.grid.grid_native_plan import GridNativePlacement
from psx.layout.grid.grid_tree_measurement import PreparedGridMeasurement
from psx.layout.contracts.fixed_point import I32_MAX


@dataclass(frozen=True, slots=True)
class IndexedGridPlacements(Sequence):
    identities: tuple
    indices: object
    columns: tuple
    stride: int
    extent: int

    def __len__(self):
        return len(self.identities)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        x, width, height = self.columns[index % len(self.columns)]
        y = index // len(self.columns) * self.stride
        return GridNativePlacement(self.identities[index], x / 64, y / 64,
            width / 64, height / 64, width / 64, height / 64, False, False)

    def selected(self, identities):
        return tuple(self[self.indices[key]] for key in identities)

    def visible_roots(self, bottom):
        # A row beginning exactly on the outer overscan edge has zero
        # intersection. Partial rows beginning before it are always included.
        rows = (len(self.identities) // len(self.columns) if self.stride == 0
                else max(0, ceil(bottom * 64 / self.stride)))
        return self.identities[:min(len(self), rows * len(self.columns))]


@dataclass(frozen=True, slots=True)
class IndexedGridRows(Sequence):
    placements: IndexedGridPlacements

    def __len__(self):
        return len(self.placements) // len(self.placements.columns)

    def __getitem__(self, row):
        if isinstance(row, slice):
            return tuple(self[i] for i in range(*row.indices(len(self))))
        if row < 0:
            row += len(self)
        if not 0 <= row < len(self):
            raise IndexError(row)
        result = []
        for column in range(len(self.placements.columns)):
            index = row * len(self.placements.columns) + column
            placement = self.placements[index]
            x, y, width, height = (round(value * 64) for value in (
                placement.x, placement.y, placement.width, placement.height))
            result.append(GridConstrainedRect(placement.node_id,
                x, y, width, height, width, height, False, False))
        return tuple(result)


@dataclass(frozen=True, slots=True)
class IndexedMeasurementRevisions(Sequence):
    identities: tuple
    generation: int

    def __len__(self):
        return len(self.identities)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple((key, self.generation) for key in self.identities[index])
        return self.identities[index], self.generation


@dataclass(frozen=True, slots=True)
class UniformFlowProof:
    base: object
    per_row: int
    row_gap: float
    column_gap: float
    height: float
    threshold: float
    indices: dict
    source_ids: dict
    blueprints: dict
    items: tuple
    minimum_height: float


def certify_uniform_flows(base, plan):
    if base is None or plan is None or not plan[3] or base.provisional_ids:
        return None
    per_row, row_gap, identifiers, _normal, column_gap = plan
    if not identifiers or len(identifiers) % per_row or column_gap is None:
        return None
    if base.nested or base.nested_flex or base.nested_scroll:
        return None
    height, threshold, minimum_height = None, 0.0, float("inf")
    for identifier in identifiers:
        flow = base.nested_flow.get(identifier)
        minimum = getattr(flow, "unwrapped_at_width", None)
        if (flow is None or not isinstance(minimum, (float, int))
                or not isfinite(minimum) or flow.nested_grids):
            return None
        if height is None:
            height = flow.content_height
        if flow.content_height != height:
            return None
        threshold = max(threshold, minimum)
        minimum_height = min(minimum_height, flow.minimum_content_height)
    items = base.grid.effective_children
    return UniformFlowProof(base, per_row, row_gap, column_gap, height, threshold,
        MappingProxyType({key: index for index, key in enumerate(identifiers)}),
        MappingProxyType({id(item.source): identifiers[index]
         for index, item in enumerate(items)}), {}, items, minimum_height)


@dataclass(frozen=True, slots=True)
class DeferredGridPlacements(Sequence):
    """Exact visible prefix followed by explicitly dirty structural receipts."""
    prefix: tuple
    tail: IndexedGridPlacements
    shift: float

    @property
    def identities(self):
        return self.tail.identities

    @property
    def columns(self):
        return self.tail.columns

    def __len__(self):
        return len(self.tail)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if index < len(self.prefix):
            return self.prefix[index]
        placement = self.tail[index]
        return replace(placement, y=placement.y + self.shift)

    def selected(self, identities):
        return tuple(self[self.tail.indices[key]] for key in identities)


def prepare_deferred_grid_window(proof, *, width, viewport, generation, engine,
                                 native_instances, compose_prefix):
    """Solve indispensable rows and keep a plain-window P2 tail dirty.

    No Scroll or following sibling may consume this provisional extent.
    Minimum heights and nonnegative gaps prove the entire deferred tail below
    overscan, independently of how wrapping changes its still-pending height.
    """
    if proof is None:
        return None
    bottom = viewport.height.value
    stride_min = floor(proof.minimum_height * 64) + floor(proof.row_gap * 64)
    if (not isinstance(bottom, (float, int)) or not isfinite(bottom)
            or bottom <= 0 or stride_min <= 0):
        return None
    identities = proof.base.prepared.child_ids
    count = ceil((bottom + 96.0) * 64 / stride_min) * proof.per_row
    for instance in native_instances:
        identifier = proof.source_ids.get(id(instance.node))
        if identifier is not None:
            count = max(count, (proof.indices[identifier] // proof.per_row + 1) * proof.per_row)
    if count >= len(identities):
        return None
    method = getattr(engine, "compute_uniform_grid_template", None)
    if not callable(method):
        return None
    template = method(12 // proof.per_row, len(identities), width,
                      proof.column_gap, proof.row_gap, proof.height)
    if template is None:
        return None
    columns, stride, old_extent = template
    tail = IndexedGridPlacements(identities, proof.indices,
        tuple(tuple(column) for column in columns), stride, old_extent)
    prefix_grid = replace(proof.base.grid, children=proof.items[:count])
    prefix = compose_prefix(prefix_grid)
    # Only Cinnamon's exact prefix sets visible positions. Nothing in the
    # speculative tail can feed back into earlier fixed-span Grid rows.
    next_row = prefix.content_height + (stride - columns[0][2]) / 64
    shift = next_row - count // proof.per_row * stride / 64
    extent = old_extent / 64 + shift
    if extent * 64 > I32_MAX or extent < prefix.content_height:
        return None
    placements = DeferredGridPlacements(prefix.prepared.placements, tail, shift)
    prepared = PreparedGridMeasurement(proof.base.prepared.grid_id, generation, identities,
        IndexedMeasurementRevisions(identities, generation), IndexedGridRows(placements), placements)
    pending = frozenset(identities[count:])
    return replace(proof.base, prepared=prepared,
        nested_flow=ChainMap(prefix.nested_flow, proof.base.nested_flow),
        content_height=extent, content_width=width, provisional_ids=pending,
        native_deferred_flows=frozenset(), viewport_roots=identities[:count])


def prepare_uniform_grid(proof, *, width, viewport, generation, engine,
                         native_instances, pixel_scale=1.0, report_fallback=None,
                         allow_dirty_tail=False):
    def fallback(reason):
        if report_fallback is not None:
            report_fallback(reason)
        return None

    if proof is None:
        return fallback("uncertified-height-or-packing")
    if pixel_scale != 1.0:
        return fallback("device-scale")
    method = getattr(engine, "compute_uniform_grid_template", None)
    if not callable(method):
        return fallback("indexed-grid-transport-unavailable")
    allocated = (width - (proof.per_row - 1) * proof.column_gap) / proof.per_row - 1 / 64
    dirty_tail = allocated < proof.threshold
    if dirty_tail:
        if not allow_dirty_tail:
            return fallback("text-width-dependency")
        if report_fallback is not None:
            report_fallback("text-width-dependency")
    bottom = viewport.height.value
    if not isinstance(bottom, (float, int)) or not isfinite(bottom) or bottom <= 0:
        return fallback("indefinite-viewport")
    base = proof.base
    identities = base.prepared.child_ids
    template = method(12 // proof.per_row, len(identities), width,
                      proof.column_gap, proof.row_gap, proof.height)
    if template is None:
        return fallback("indexed-grid-transport-unavailable")
    columns, stride, extent = template
    placements = IndexedGridPlacements(identities, proof.indices,
        tuple(tuple(column) for column in columns), stride, extent)
    # Include live resources even when a viewport shrink puts them in P2.
    # Their final shared-workset transition is still subject to focus/pin and
    # native acceptance, rather than being silently omitted from retirement.
    detailed = set(placements.visible_roots(bottom + 96.0))
    detailed.update(proof.source_ids[id(instance.node)] for instance in native_instances
                    if id(instance.node) in proof.source_ids)
    detailed = tuple(sorted(detailed, key=proof.indices.__getitem__))
    flows = {}
    from psx.layout.contracts.model import AvailableSize, LayoutConstraints
    for identifier in detailed:
        placement = placements[proof.indices[identifier]]
        prior = base.nested_flow[identifier]
        if prior.unwrapped_at_width > placement.width:
            return fallback("visible-text-width-dependency")
        constraints = LayoutConstraints(AvailableSize(placement.width, True), AvailableSize(None, False))
        prepared = replace(prior.prepared, snapshot=replace(
            prior.prepared.snapshot, constraints=constraints, generation=generation),
            viewport_constraints=viewport)
        blueprint = proof.blueprints.get(identifier)
        if blueprint is None:
            blueprint = prior.prepared.css_geometry_snapshot(pixel_scale=pixel_scale)
            proof.blueprints[identifier] = blueprint
        snapshot = replace(blueprint, constraints=constraints, generation=generation,
            measurements=tuple(replace(receipt, constraints=constraints, revision=generation)
                               for receipt in prior.intrinsic_receipts))
        solved = engine.compute(snapshot)
        root_id = snapshot.nodes[0].node_id
        if dict(solved.boxes)[root_id].border.height != proof.height:
            return fallback("structural-height-changed")
        flows[identifier] = replace(prior, prepared=prepared, result=solved)
    pending = frozenset(identities) - frozenset(detailed)
    prepared = PreparedGridMeasurement(base.prepared.grid_id, generation, identities,
        IndexedMeasurementRevisions(identities, generation), IndexedGridRows(placements), placements)
    return replace(base, prepared=prepared, nested_flow=ChainMap(flows, base.nested_flow),
        content_height=extent / 64, content_width=width,
        provisional_ids=pending if dirty_tail else frozenset(),
        native_deferred_flows=frozenset() if dirty_tail else pending, viewport_roots=detailed)
