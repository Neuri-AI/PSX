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

from psx.core.grid_contract import GRID_BREAKPOINTS, normalize_grid_props, normalize_grid_item_props, resolve_grid_item_props
from psx.core.layout_tree import NormalizedLayoutNode
from psx.core.vnode import NodeKind

from .grid_math import GridSlot, GridPackingError, pack_grid_rows, project_grid_rows
from .grid_tree_measurement import PreparedGridMeasurement, _pixel, prepare_grid_measurement
from .measurement_plan import MeasurementRequest
from .measurement_round import MeasurementRound
from .model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox
from .native_layout_snapshot import path_identity
from .native_measurement import NativeMeasurementPort, fulfill_native_round


class GridNativeMeasurementSource(Protocol):
    """Implemented by existing Qt/Tk/Kivy measurement sources."""
    def port(self) -> NativeMeasurementPort: ...
    def measure_width(self, node_id: str, width: float) -> IntrinsicSizes: ...


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
    from .fixed_point import I32_MAX
    if type(content_width) not in (int, float) or not isfinite(content_width) or content_width < 0 or content_width * 64 > I32_MAX:
        raise GridPackingError("Grid content width must be definite and representable.")
    props = normalize_grid_props(grid.source.props)
    children = grid.effective_children
    slots: list[GridSlot] = []
    ids: list[str] = []
    for child in children:
        if child.kind is not NodeKind.HOST or child.type != "GridItem":
            raise GridPackingError("Grid native measurement requires direct GridItem children.")
        effective = child.effective_children
        if len(effective) != 1 or effective[0].kind not in (NodeKind.HOST, NodeKind.NATIVE):
            raise GridPackingError("GridItem native measurement requires one mounted leaf.")
        if effective[0].effective_children and not (
            allow_nested and effective[0].kind is NodeKind.HOST
            and effective[0].type in ("Grid", "Flex", "div", "main", "section", "article", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "p")
        ):
            raise GridPackingError("Composite GridItem measurement is not yet supported.")
        identifier = path_identity(child.path)
        values = resolve_grid_item_props(
            normalize_grid_item_props(child.source.props), content_width,
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
        from .errors import DiagnosticCode, SFLEError
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Grid measurement requires the native UI thread.")

    # Project without fabricating heights: row membership and horizontal
    # allocation are independent of vertical intrinsic measurements.
    packed = pack_grid_rows(slots)
    projected = project_grid_rows(packed, content_width, _pixel(props["column_gap"], "Grid.column_gap"))
    widths = {item.id: item.width_raw / 64 for row in projected for item in row.items}
    requests = tuple(MeasurementRequest(
        identifier,
        LayoutConstraints(AvailableSize(widths[identifier], True), AvailableSize(None, False)),
        generation, revisions[identifier],
    ) for identifier in ids)
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
        from .errors import DiagnosticCode, SFLEError
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
