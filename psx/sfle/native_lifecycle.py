"""Generation-safe renderer lifecycle bridge for SFLE native measurements.

Adapters own native widget creation, scheduling and geometry application. This
coordinator makes the lifecycle boundary explicit: measurement must occur on
the UI thread, and an obsolete generation must never commit rectangles.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .errors import DiagnosticCode, SFLEError
from .margin_tree import MarginTreeNode
from .model import LayoutInput, MeasuredBox
from .native_measurement import NativeMeasurementPort
from .recursive_measurement import RecursiveMeasurementResult, measure_resolved_margin_tree
from .constraint_propagation import ChildSizing
from .auto_cross_tree import AutoCrossSize
from .intrinsic_tree import IntrinsicLeafStyle
from .recursive_pipeline import compute_recursive_pipeline


@dataclass(frozen=True, slots=True)
class NativeLayoutLifecycle:
    """Renderer-owned functions, invoked synchronously on its UI thread."""

    generation: Callable[[], int]
    measurement: NativeMeasurementPort
    apply_geometry: Callable[[RecursiveMeasurementResult], None]

    def __post_init__(self) -> None:
        if not callable(self.generation) or not callable(self.apply_geometry):
            raise TypeError("Lifecycle needs generation and commit callbacks.")
        if not isinstance(self.measurement, NativeMeasurementPort):
            raise TypeError("Lifecycle measurement must be a native port.")


def layout_and_commit(
    snapshot: LayoutInput,
    nodes: tuple[MarginTreeNode, ...],
    lifecycle: NativeLayoutLifecycle,
    *,
    child_sizing: tuple[tuple[str, ChildSizing], ...],
    revisions: tuple[tuple[str, int], ...] = (),
    intrinsic_leaves: tuple[IntrinsicLeafStyle, ...] = (),
    auto_cross: tuple[AutoCrossSize, ...] = (),
) -> RecursiveMeasurementResult:
    """Compute, measure and atomically guard a renderer geometry commit.

    The generation is checked before native measurement and again immediately
    before geometry commit. No framework event loop or worker scheduling is
    performed here. Renderers must call this function from their UI scheduler.
    """
    if not isinstance(snapshot, LayoutInput) or not isinstance(lifecycle, NativeLayoutLifecycle):
        raise TypeError("Expected LayoutInput and NativeLayoutLifecycle.")
    generation = lifecycle.generation()
    if type(generation) is not int or generation != snapshot.generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Layout generation became stale before measurement.")
    if not lifecycle.measurement.is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Layout lifecycle requires UI thread.")
    if intrinsic_leaves or auto_cross:
        result = compute_recursive_pipeline(
            snapshot, nodes, child_sizing=child_sizing, revisions=revisions,
            native_port=lifecycle.measurement, current_generation=generation,
            intrinsic_leaves=intrinsic_leaves, auto_cross=auto_cross,
        )
    else:
        result = measure_resolved_margin_tree(
            snapshot, nodes, child_sizing=child_sizing, revisions=revisions,
            port=lifecycle.measurement, current_generation=generation,
        )
    if lifecycle.generation() != generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Layout generation became stale before commit.")
    if not lifecycle.measurement.is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Geometry commit requires UI thread.")
    # Deferring unresolved axes until the CSS sizing phase prevents the
    # renderer from applying known-incomplete geometry as final layout.
    if result.deferred:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "Cannot commit geometry while CSS dimensions remain deferred.",
        )
    lifecycle.apply_geometry(result)
    return result
