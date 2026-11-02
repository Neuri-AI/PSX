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

from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.grid.contracts import GridPackingError
from psx.layout.grid.grid_native_plan import GridNativePlacement
from psx.layout.contracts.model import Rect


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
    kivy_window_coordinates: bool = False,
    readback_tolerance: float = 1.0,
    prior_tk_placements: Mapping[str, Mapping[str, object]] | None = None,
    prior_native_rectangles: Mapping[str, Rect] | None = None,
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
    if prior_native_rectangles is not None and backend not in (
        GridCommitBackend.QT, GridCommitBackend.KIVY,
    ):
        raise GridPackingError("Pre-captured geometry requires Qt or Kivy backend.")
    ids = tuple(p.node_id for p in placements)
    if any(not isinstance(p, GridNativePlacement) for p in placements):
        raise GridPackingError("Grid commit requires preflighted Cinnamon placements.")
    if len(set(ids)) != len(ids) or set(ids) != set(widgets) or len(ids) != len(widgets):
        raise GridPackingError("Grid native geometry identities do not match mounted widgets.")
    if prior_native_rectangles is not None and (
        set(prior_native_rectangles) != set(ids)
        or any(not isinstance(rect, Rect) for rect in prior_native_rectangles.values())
    ):
        raise GridPackingError("Pre-captured native rectangles must match the batch.")
    if parent_heights is not None and set(parent_heights) != set(ids):
        raise GridPackingError("Kivy parent heights must cover exactly the mounted placements.")
    if type(kivy_window_coordinates) is not bool or (
        kivy_window_coordinates and backend is not GridCommitBackend.KIVY
    ):
        raise GridPackingError("Window-space Grid geometry is Kivy-only.")
    target: dict[str, Rect] = {}
    pending_native: dict[int, Rect] = {}
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
        # Negative local Y is valid for content overflowing below its parent.
        # Kivy coordinates are bottom-left relative to the immediate parent;
        # clamping or rejecting the solver rectangle changes authored geometry.
        # The allocated Cinnamon rectangle and native readback remain authoritative.
        if kivy_window_coordinates:
            # Kivy's Widget canvas uses window-space coordinates even when
            # the widget belongs to a nested GridItem or semantic block.
            # Resolve parents from this same immutable batch (parents precede
            # descendants) before touching any native widget.
            widget = widgets[placement.node_id]
            owner = getattr(widget, "parent", None)
            if owner is not None:
                previous = pending_native.get(id(owner))
                px, py = ((previous.x, previous.y) if previous is not None
                          else (float(owner.x), float(owner.y)))
                x = px + placement.x
                y = py + y
            else:
                x = placement.x
        else:
            x = placement.x
        resolved = Rect(x, y, placement.width, placement.height)
        target[placement.node_id] = resolved
        if kivy_window_coordinates:
            pending_native[id(widgets[placement.node_id])] = resolved

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
            # Kivy property writes dispatch canvas/geometry observers.
            # A size-only resize should not re-notify position listeners.
            desired_pos = (rect.x, rect.y)
            desired_size = (rect.width, rect.height)
            if tuple(widget.pos) != desired_pos:
                widget.pos = desired_pos
            if tuple(widget.size) != desired_size:
                widget.size = desired_size

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
        # For a single Grid batch the outer bridge already captured these
        # native rectangles for rollback. Reuse that authoritative baseline
        # instead of repeating thousands of UI-thread property reads.
        originals = (
            dict(prior_native_rectangles)
            if prior_native_rectangles is not None else
            {node_id: read(widgets[node_id]) for node_id in ids}
        )
        unplaced = set()
    absent_headless = ({node_id for node_id in ids if widgets[node_id].geometry is None}
                       if backend is GridCommitBackend.HEADLESS else set())
    # Only native rectangles from this *same* owner-thread transaction can
    # be used as readback receipts. Qt children use absolute parent-local
    # pixels; Tk requires explicit pixel placement without relative axes.
    # Kivy stays live-read: canvas/ScrollView transforms may change geometry
    # without a direct geometry write from this committer.
    unchanged_receipts: set[str] = set()
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
                if backend is GridCommitBackend.QT:
                    unchanged_receipts.add(node_id)
                elif backend is GridCommitBackend.TK:
                    info = (
                        prior_tk_placements.get(node_id)
                        if prior_tk_placements is not None else None
                    )
                    # Without an explicit pixel placement receipt, keep
                    # native readback. Relative Tk placements can shift
                    # when their parent changes, even if no place() occurs.
                    if info and all(key in info for key in (
                        "x", "y", "width", "height",
                    )):
                        try:
                            if not any(float(info.get(key) or 0.0) for key in (
                                "relx", "rely", "relwidth", "relheight",
                            )):
                                unchanged_receipts.add(node_id)
                        except (ValueError, TypeError, OverflowError):
                            pass
                continue
            write(widgets[node_id], desired)
        if current_generation() != generation or not is_ui_thread():
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Grid invalidated before readback.")
        # The rollback baseline already holds a real native read from this
        # transaction. For unchanged, explicitly positioned Qt/Tk children
        # this is also the final rectangle. Changed children, unplaced Tk
        # nodes, relative Tk placements, Kivy and headless always read live.
        # This avoids O(N) redundant native getter calls in large Grid
        # commits while retaining a complete per-node verification receipt.
        observed = {
            node_id: (originals[node_id] if node_id in unchanged_receipts
                      else read(widgets[node_id]))
            for node_id in ids
        }
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
