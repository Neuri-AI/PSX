"""Execute Grid intrinsic measurement through the existing toolkit UI-thread ports.

Grid's pure Cinnamon projection determines each child's definite width before
measuring width-dependent text. Native sources own real widget measurement;
this coordinator owns stable identities, generation and atomic acceptance.
No widget is created, moved or committed here.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from collections.abc import Callable
from threading import get_ident
from dataclasses import dataclass
from collections import OrderedDict

from psx.core.grid_contract import (GRID_BREAKPOINTS, normalize_grid_props,
    normalize_grid_item_props, resolve_grid_item_props, validate_grid_breakpoints,
    _at_breakpoint)
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind
from psx.markup.html_aliases import FORMATTING_TAGS

from psx.layout.grid.contracts import GridSlot, GridPackingError
from psx.layout.grid.solver import grid_widths
from psx.layout.grid.grid_tree_measurement import PreparedGridMeasurement, _pixel, prepare_grid_measurement
from psx.layout.runtime.measurement_plan import MeasurementRequest
from psx.layout.runtime.measurement_round import MeasurementRound
from psx.layout.contracts.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from psx.layout.projection.native_layout_snapshot import path_identity
from psx.layout.runtime.native_measurement import NativeMeasurementPort, fulfill_native_round


class GridNativeMeasurementSource(Protocol):
    """Implemented by existing Qt/Tk/Kivy measurement sources."""
    def port(self) -> NativeMeasurementPort: ...
    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes: ...


@dataclass(frozen=True, slots=True)
class GridMeasurementStructure:
    grid: NormalizedLayoutNode
    props: Mapping[str, object]
    slots: tuple[GridSlot, ...]
    ids: tuple[str, ...]
    children: Mapping[str, NormalizedLayoutNode]
    width_pattern: tuple[GridSlot, ...] | None = None
    width_identities: Mapping[str, str] | None = None


class GridStructureReuse:
    """Cache immutable packing input per Grid and responsive interval.

    This retains no measurements or rectangles: Cinnamon still computes all
    widths and tracks. Native measurement and final Grid preparation share
    this one validated structural projection instead of normalizing the same
    thousands of GridItems repeatedly inside a resize transaction.
    """

    def __init__(self, limit=16):
        self.limit = limit
        self.entries = OrderedDict()
        self._metadata = OrderedDict()

    def clear(self):
        self.entries.clear()
        self._metadata.clear()

    def prepare(self, grid, content_width, breakpoints, pixel_scale):
        responsive_width = content_width / pixel_scale
        validate_grid_breakpoints(breakpoints)
        metadata = self._metadata.get(id(grid))
        if metadata is None or metadata[0] is not grid:
            items, responsive = [], False
            for item in grid.effective_children:
                if item.kind is not NodeKind.HOST or item.type != "GridItem":
                    raise GridPackingError("Grid composition requires direct GridItem children.")
                effective = item.effective_children
                if len(effective) != 1:
                    raise GridPackingError("GridItem requires exactly one content root.")
                values = normalize_grid_item_props(item.source.props)
                responsive |= any(isinstance(values[name], Mapping)
                                  for name in ("span", "offset"))
                items.append((path_identity(item.path), values, effective[0]))
            metadata = (grid, tuple(items), responsive)
            self._metadata[id(grid)] = metadata
            while len(self._metadata) > self.limit:
                self._metadata.popitem(last=False)
        interval = tuple(name for name, value in breakpoints.items()
                         if value <= responsive_width)
        key = (id(grid), tuple(breakpoints.items()),
               interval if metadata[2] else None, pixel_scale)
        cached = self.entries.get(key)
        if cached is not None and cached.grid is grid:
            self.entries.move_to_end(key)
            return cached
        props = normalize_grid_props(grid.source.props)
        ids, slots, children = [], [], {}
        active = next(name for name in reversed(GRID_BREAKPOINTS)
                      if breakpoints[name] <= responsive_width)
        for identifier, values, child in metadata[1]:
            ids.append(identifier)
            slots.append(GridSlot(identifier, _at_breakpoint(values["span"], active),
                                  _at_breakpoint(values["offset"], active)))
            children[identifier] = child
        if len(set(ids)) != len(ids):
            raise GridPackingError("Duplicate Grid child identities.")
        pattern = None
        width_identities = None
        if slots and type(slots[0].span) is int and 12 % slots[0].span == 0:
            span = slots[0].span
            if all(slot.span == span and slot.offset == 0 and slot.order == 0
                   for slot in slots):
                per_row = 12 // span
                first = tuple(slots[:per_row])
                remainder = len(slots) % per_row
                tail = tuple(slots[-remainder:]) if remainder and len(slots) > per_row else ()
                # Cinnamon distributes available gutters per packed row.
                # A final partial row therefore has a different track width;
                # retain that pattern rather than reusing a complete row.
                pattern = first + tail
                tail_ids = {slot.id for slot in tail}
                width_identities = {
                    slot.id: slot.id if slot.id in tail_ids else first[index % len(first)].id
                    for index, slot in enumerate(slots)}
        prepared = GridMeasurementStructure(
            grid, props, tuple(slots), tuple(ids), children, pattern, width_identities)
        self.entries[key] = prepared
        while len(self.entries) > self.limit:
            self.entries.popitem(last=False)
        return prepared


def measure_grid_native(
    grid: NormalizedLayoutNode,
    *,
    content_width: float,
    source: GridNativeMeasurementSource,
    mounted_ids: tuple[str, ...],
    revisions: Mapping[str, int],
    generation: int,
    current_generation: int,
    constraints: Mapping[str, object] | None = None,
    rtl: bool = False,
    allow_nested: bool = False,
    breakpoints: Mapping[str, object] = GRID_BREAKPOINTS,
    pixel_scale: float = 1.0,
    engine: object | None = None,
    structure: GridMeasurementStructure | None = None,
    structural_heights: Mapping[str, float] | None = None,
) -> PreparedGridMeasurement:
    """Perform real width-aware native measurement, then run Cinnamon Grid.

    Every GridItem identity must map to its *actual mounted leaf widget* in
    the supplied source. A GridItem with a composite subtree is not yet
    supported; nested container measurement belongs to the next lifecycle
    integration and must fail closed, not return guessed dimensions.
    """
    if not isinstance(grid, NormalizedLayoutNode) or grid.kind is not NodeKind.HOST or grid.type != "Grid":
        raise GridPackingError("Native measurement requires a normalized Grid.")
    if type(generation) is not int or type(current_generation) is not int or generation != current_generation:
        raise GridPackingError("Stale native Grid measurement generation.")
    if not isinstance(revisions, Mapping):
        raise GridPackingError("Grid measurement revisions must be a mapping.")
    if not isinstance(mounted_ids, tuple):
        raise GridPackingError("Grid mounted identities must be an immutable tuple.")
    from math import isfinite
    from psx.layout.contracts.fixed_point import I32_MAX
    if type(content_width) not in (int, float) or not isfinite(content_width) or content_width < 0 or content_width * 64 > I32_MAX:
        raise GridPackingError("Grid content width must be definite and representable.")
    if type(pixel_scale) not in (int, float) or not isfinite(pixel_scale) or pixel_scale <= 0:
        raise GridPackingError("Grid native pixel scale must be finite and positive.")
    props = structure.props if structure is not None else normalize_grid_props(grid.source.props)
    children = grid.effective_children if structure is None else ()
    slots = list(structure.slots) if structure is not None else []
    ids = list(structure.ids) if structure is not None else []
    if structure is not None and structure.grid is not grid:
        raise GridPackingError("Grid structural receipt belongs to a different tree.")
    for child in children:
        if child.kind is not NodeKind.HOST or child.type != "GridItem":
            raise GridPackingError("Grid native measurement requires direct GridItem children.")
        effective = child.effective_children
        if len(effective) != 1 or effective[0].kind not in (NodeKind.HOST, NodeKind.NATIVE):
            raise GridPackingError("GridItem native measurement requires one mounted leaf.")
        if effective[0].effective_children and not (
            allow_nested and effective[0].kind is NodeKind.HOST
            and (effective[0].type in ("Grid", "Flex", "Scroll")
                 or effective[0].type in FORMATTING_TAGS)
        ):
            raise GridPackingError("Composite GridItem measurement is not yet supported.")
        identifier = path_identity(child.path)
        values = resolve_grid_item_props(
            normalize_grid_item_props(child.source.props), content_width / pixel_scale,
            breakpoints=breakpoints,
        )
        slots.append(GridSlot(identifier, values["span"], values["offset"]))
        ids.append(identifier)
    if len(set(ids)) != len(ids) or set(revisions) != set(ids):
        raise GridPackingError("Grid measurement revision identities do not match the tree.")
    if any(type(value) is not int or value < 0 for value in revisions.values()):
        raise GridPackingError("Grid revisions must be nonnegative integers.")
    if len(mounted_ids) != len(ids) or set(mounted_ids) != set(ids):
        raise GridPackingError("Grid native widget identities do not match the tree.")
    port = source.port()
    if not isinstance(port, NativeMeasurementPort) or not callable(getattr(source, "measure_width", None)):
        raise GridPackingError("Grid source must expose an existing native measurement port and width-aware measurement.")
    if not port.is_ui_thread():
        from psx.layout.contracts.errors import DiagnosticCode, SFLEError
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Grid measurement requires the native UI thread.")

    # Project without fabricating heights: row membership and horizontal
    # allocation are independent of vertical intrinsic measurements.
    width_slots = (structure.width_pattern
                   if structure is not None and structure.width_pattern else slots)
    widths = grid_widths(
        width_slots, content_width,
        _pixel(props["column_gap"], "Grid.column_gap") * pixel_scale,
        engine=engine,
    )
    retained = structural_heights or {}
    if retained and (structure is None or not set(retained) <= set(ids)):
        raise GridPackingError("Structural heights require matching Grid receipts.")
    requests = tuple(MeasurementRequest(
        identifier,
        LayoutConstraints(AvailableSize(widths[
            structure.width_identities[identifier]
            if structure is not None and structure.width_identities else identifier], True),
            AvailableSize(None, False)),
        generation, revisions[identifier],
    ) for identifier in ids if identifier not in retained)
    round_ = MeasurementRound(generation, requests, (), ())

    def measure(request: MeasurementRequest) -> MeasuredBox:
        intrinsic = source.measure_width(request.node_id, request.constraints.width.value)
        return MeasuredBox(request.node_id, intrinsic, request.constraints, request.revision)

    receipts = fulfill_native_round(
        round_, NativeMeasurementPort(port.is_ui_thread, measure),
        current_generation=current_generation,
    )
    return prepare_grid_measurement(
        grid, content_width=content_width, measurements=receipts,
        mounted_ids=mounted_ids, generation=generation,
        current_generation=current_generation, constraints=constraints, rtl=rtl,
        breakpoints=breakpoints,
        pixel_scale=pixel_scale, engine=engine,
        structure=structure,
        structural_heights=retained,
    )


class HeadlessGridMeasurementSource:
    """Use HeadlessRenderer's explicit intrinsic callback, never a size guess.

    The supplied callback receives the actual mounted leaf VNode and its
    Cinnamon allocated width. It must return IntrinsicSizes; unknown native
    controls are unsupported rather than assigned arbitrary default sizes.
    """

    def __init__(
        self, nodes: Mapping[str, object],
        measure_intrinsic: Callable[[object, float], IntrinsicSizes],
    ) -> None:
        from psx.core.vnode import VNode
        if any(not isinstance(node, VNode) for node in nodes.values()):
            raise TypeError("Headless Grid measurements require mounted VNodes.")
        if not callable(measure_intrinsic):
            raise TypeError("Headless Grid requires an explicit intrinsic callback.")
        self._nodes = dict(nodes)
        self._measure_intrinsic = measure_intrinsic
        self._owner_thread = get_ident()

    def is_ui_thread(self) -> bool:
        return get_ident() == self._owner_thread

    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes:
        from psx.layout.contracts.errors import DiagnosticCode, SFLEError
        if not self.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Headless Grid measured off owner thread.")
        node = self._nodes.get(node_id)
        if node is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Unknown Headless Grid leaf.")
        intrinsic = self._measure_intrinsic(node, width)
        if not isinstance(intrinsic, IntrinsicSizes):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Headless Grid requires real intrinsic metrics.")
        return intrinsic

    def port(self) -> NativeMeasurementPort:
        def measure(request: MeasurementRequest) -> MeasuredBox:
            width = request.constraints.width.value
            return MeasuredBox(
                request.node_id, self.measure_width(request.node_id, width),
                request.constraints, request.revision,
            )
        return NativeMeasurementPort(self.is_ui_thread, measure)
