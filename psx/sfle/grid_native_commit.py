"""Atomic native geometry transaction for already-mounted Grid children.

Cinnamon owns the allocation; backend ports only translate coordinates and
perform real widget geometry writes/readback. Grid creation and reconciliation
are separate responsibilities of renderer adapters.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .errors import DiagnosticCode, SFLEError
from .grid_math import GridPackingError
from .grid_native_plan import GridNativePlacement
from .model import Rect


class GridCommitBackend(str, Enum):
    QT = "qt"
    TK = "tk"
    KIVY = "kivy"
    HEADLESS = "headless"


@dataclass(frozen=True, slots=True)
class GridNativeCommitReceipt:
    generation: int
    node_ids: tuple[str, ...]
    max_readback_error: float


def commit_grid_native_geometry(
    placements: tuple[GridNativePlacement, ...],
    *,
    backend: GridCommitBackend,
    widgets: Mapping[str, object],
    generation: int,
    current_generation: Callable[[], int],
    is_ui_thread: Callable[[], bool],
    parent_height: float | None = None,
    parent_heights: Mapping[str, float] | None = None,
    readback_tolerance: float = 1.0,
    prior_tk_placements: Mapping[str, Mapping[str, object]] | None = None,
) -> GridNativeCommitReceipt:
    """Commit a complete mounted Grid batch, verifying every native readback.

    The rollback is best effort if a toolkit itself raises during restoration.
    This function never changes parentage or creates widgets. Kivy receives
    bottom-left local coordinates; all other backends use top-left coordinates.
    """
    if not isinstance(backend, GridCommitBackend) or not isinstance(placements, tuple):
        raise TypeError("Expected GridCommitBackend and immutable placements.")
    if type(generation) is not int or generation < 0 or not callable(current_generation):
        raise GridPackingError("Grid commit requires a valid generation.")
    if not callable(is_ui_thread) or not is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Grid native geometry requires UI thread.")
    if current_generation() != generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Grid geometry commit.")
    if type(readback_tolerance) not in (int, float) or not isfinite(readback_tolerance) or readback_tolerance < 0:
        raise GridPackingError("Grid readback tolerance must be finite and nonnegative.")
    if backend is GridCommitBackend.KIVY and (
        type(parent_height) not in (int, float) or not isfinite(parent_height) or parent_height < 0
    ):
        raise GridPackingError("Kivy Grid requires a definite parent height.")

    if parent_heights is not None and backend is not GridCommitBackend.KIVY:
        raise GridPackingError("Per-widget parent heights are only valid for Kivy.")
    if prior_tk_placements is not None and backend is not GridCommitBackend.TK:
        raise GridPackingError("Prior Tk placements require the Tk backend.")
    ids = tuple(p.node_id for p in placements)
    if any(not isinstance(p, GridNativePlacement) for p in placements):
        raise GridPackingError("Grid commit requires preflighted Cinnamon placements.")
    if len(set(ids)) != len(ids) or set(ids) != set(widgets) or len(ids) != len(widgets):
        raise GridPackingError("Grid native geometry identities do not match mounted widgets.")
    if parent_heights is not None and set(parent_heights) != set(ids):
        raise GridPackingError("Kivy parent heights must cover exactly the mounted placements.")
    target: dict[str, Rect] = {}
    for placement in placements:
        values = (placement.x, placement.y, placement.width, placement.height)
        if any(type(v) not in (int, float) or not isfinite(v) or v < 0 for v in values):
            raise GridPackingError("Grid native geometry requires finite nonnegative rectangles.")
        if placement.overflow_x != (placement.used_width > placement.width) or (
            placement.overflow_y != (placement.used_height > placement.height)
        ):
            raise GridPackingError("Grid overflow receipt is inconsistent.")
        local_height = (parent_heights[placement.node_id]
                        if parent_heights is not None else parent_height)
        if backend is GridCommitBackend.KIVY and (
            type(local_height) not in (int, float) or not isfinite(local_height) or local_height < 0
        ):
            raise GridPackingError("Kivy parent height must be finite and nonnegative.")
        y = (local_height - placement.y - placement.height
             if backend is GridCommitBackend.KIVY else placement.y)
        if y < 0:
            raise GridPackingError("Grid rectangle exceeds Kivy parent content height.")
        target[placement.node_id] = Rect(placement.x, y, placement.width, placement.height)

    def read(widget: object) -> Rect:
        if backend is GridCommitBackend.HEADLESS:
            value = widget.geometry
            return value if value is not None else Rect(0, 0, 0, 0)
        if backend is GridCommitBackend.QT:
            rect = widget.geometry()
            return Rect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()))
        if backend is GridCommitBackend.TK:
            info = widget.place_info()
            if not info:
                return Rect(0, 0, 0, 0)
            return Rect(*(float(info[k]) for k in ("x", "y", "width", "height")))
        return Rect(float(widget.pos[0]), float(widget.pos[1]), float(widget.size[0]), float(widget.size[1]))

    def write(widget: object, rect: Rect, *, restore_unplaced: bool = False) -> None:
        if backend is GridCommitBackend.HEADLESS:
            widget.geometry = rect
        elif backend is GridCommitBackend.QT:
            widget.setGeometry(*(round(v) for v in (rect.x, rect.y, rect.width, rect.height)))
        elif backend is GridCommitBackend.TK:
            if restore_unplaced:
                widget.place_forget()
            else:
                widget.place(**{k: round(getattr(rect, k)) for k in ("x", "y", "width", "height")})
        else:
            widget.pos = (rect.x, rect.y)
            widget.size = (rect.width, rect.height)

    # Capture all original native states before the first mutation.
    if backend is GridCommitBackend.TK:
        # Capture the original rectangle and unplaced status in one Tcl
        # round trip. Both belong to the same pre-mutation snapshot.
        originals = {}
        unplaced = set()
        for node_id in ids:
            info = (
                prior_tk_placements[node_id]
                if prior_tk_placements is not None
                   and node_id in prior_tk_placements
                else widgets[node_id].place_info()
            )
            if info:
                originals[node_id] = Rect(*(
                    float(info[k]) for k in ("x", "y", "width", "height")
                ))
            else:
                originals[node_id] = Rect(0, 0, 0, 0)
                unplaced.add(node_id)
    else:
        originals = {node_id: read(widgets[node_id]) for node_id in ids}
        unplaced = set()
    absent_headless = ({node_id for node_id in ids if widgets[node_id].geometry is None}
                       if backend is GridCommitBackend.HEADLESS else set())
    if current_generation() != generation or not is_ui_thread():
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated before native mutation.")
    try:
        for node_id in ids:
            if current_generation() != generation or not is_ui_thread():
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated during native commit.")
            before = originals[node_id]
            desired = target[node_id]
            # Qt and Tk project logical rectangles to integral native pixels.
            # Avoid triggering redundant geometry/change events on unchanged widgets.
            if backend in (GridCommitBackend.QT, GridCommitBackend.TK):
                unchanged = all(
                    getattr(before, axis) == round(getattr(desired, axis))
                    for axis in ("x", "y", "width", "height")
                )
            else:
                unchanged = before == desired
            if (unchanged and node_id not in absent_headless
                    and node_id not in unplaced):
                continue
            write(widgets[node_id], desired)
        if current_generation() != generation or not is_ui_thread():
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated before readback.")
        # Read each native rectangle once. Repeating read() inside the axis
        # loop performs four full Tcl place_info() round trips per widget,
        # although all four axes describe the same committed rectangle.
        observed = {node_id: read(widgets[node_id]) for node_id in ids}
        error = max((
            abs(getattr(observed[node_id], axis) - getattr(target[node_id], axis))
            for node_id in ids for axis in ("x", "y", "width", "height")
        ), default=0.0)
        if error > readback_tolerance:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid native geometry readback exceeded tolerance.")
        if current_generation() != generation or not is_ui_thread():
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated after readback.")
    except BaseException:
        for node_id in reversed(ids):
            try:
                if node_id in absent_headless:
                    widgets[node_id].geometry = None
                else:
                    write(widgets[node_id], originals[node_id], restore_unplaced=node_id in unplaced)
            except Exception:
                pass
        raise
    return GridNativeCommitReceipt(generation, ids, error)
