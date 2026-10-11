"""Portable generation-scoped SFLE worker/UI transaction.

The toolkit supplies an UI-owned scheduling callback, intrinsic measurement,
geometry application and an independently read-back geometry source. Neither
native handles nor measurement callbacks are touched by the compute worker.
"""

from __future__ import annotations

import math
import queue
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from .errors import DiagnosticCode, SFLEError
from .adapter_contract import SFLEAdapterPorts, ScrollViewport, validate_adapter_commit
from .model import IntrinsicSizes, LayoutInput, LayoutResult
from .remeasure_session import compute_with_width_measurements


@dataclass(slots=True)
class _MeasureRequest:
    node_id: str
    width: float
    ready: threading.Event = field(default_factory=threading.Event)
    value: IntrinsicSizes | None = None
    error: Exception | None = None


class NativeWorkerLayoutHandle:
    """Lifetime and cancellation ownership for a single pure computation."""

    def __init__(self, pool: ThreadPoolExecutor, generation: int) -> None:
        self._pool = pool
        self._generation = generation
        self._cancelled = threading.Event()
        self._finished = False

    def done(self) -> bool:
        """Whether the UI dispatcher delivered its single completion callback."""
        return self._finished

    def cancel(self) -> None:
        """Prevent a pending transaction from committing any geometry."""
        self._cancelled.set()


def _observed_error(
    result: LayoutResult, observed: Mapping[str, Mapping[str, float]],
) -> float:
    """Compare *read-back* applied native coordinates to computed borders.

    A missing observation is not zero error. Root/window rectangles that are not
    native-managed do not have to appear in the observed mapping.
    """
    boxes = dict(result.boxes)
    if not observed:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Native geometry was not independently observed.")
    deviations: list[float] = []
    for node_id, coordinates in observed.items():
        if node_id not in boxes:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Observed geometry has an unknown SFLE node.", node_id)
        rect = boxes[node_id].border
        for axis in ("x", "y", "width", "height"):
            try:
                actual = coordinates[axis]
            except (KeyError, TypeError) as exc:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Native geometry observation is incomplete.", node_id) from exc
            if type(actual) not in (int, float) or not math.isfinite(actual):
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Native geometry observation is not finite.", node_id)
            deviations.append(abs(actual - getattr(rect, axis)))
    return max(deviations)


def start_native_worker_layout(
    snapshot: LayoutInput,
    *,
    compute: Callable[[LayoutInput], LayoutResult],
    provisional: Callable[[LayoutInput], LayoutResult],
    measure_on_ui: Callable[[str, float], IntrinsicSizes],
    is_ui_thread: Callable[[], bool],
    current_generation: Callable[[], int],
    apply_geometry: Callable[[LayoutResult], None],
    observed_geometry: Callable[[], Mapping[str, Mapping[str, float]]],
    restore_geometry: Callable[[Mapping[str, Mapping[str, float]]], None],
    initial_widths: dict[str, float],
    post_to_ui: Callable[[Callable[[], None]], None],
    on_finished: Callable[[LayoutResult | None, Exception | None], None],
    nodes_alive: Callable[[tuple[str, ...]], bool] | None = None,
    scroll_viewports: tuple[ScrollViewport, ...] = (),
) -> NativeWorkerLayoutHandle:
    """Start real OS-worker computation, with *only* UI-owned native operations.

    ``post_to_ui`` is invoked solely from its owning UI thread: the callback
    pumps worker measurement requests and reposts itself until completion.
    This makes it compatible with schedulers whose posting operation is not
    thread-safe (including Tk/Kivy host schedulers). The host must run queued
    callbacks fairly; computation never runs in one of those callbacks.
    """
    if not isinstance(snapshot, LayoutInput):
        raise TypeError("Expected an immutable LayoutInput snapshot.")
    if not isinstance(scroll_viewports, tuple) or not all(
        isinstance(viewport, ScrollViewport) for viewport in scroll_viewports
    ):
        raise TypeError("scroll_viewports must be an immutable ScrollViewport tuple.")
    if not is_ui_thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Portable SFLE dispatcher must start on the UI thread.")
    generation = snapshot.generation
    if current_generation() != generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale SFLE generation at start.")

    pending: queue.Queue[_MeasureRequest] = queue.Queue()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sfle-native-pure")
    handle = NativeWorkerLayoutHandle(pool, generation)

    def request_measure(node_id: str, width: float) -> IntrinsicSizes:
        if handle._cancelled.is_set():
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Cancelled SFLE measurement.")
        request = _MeasureRequest(node_id, width)
        pending.put(request)
        if not request.ready.wait(timeout=10.0):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Native UI measurement request timed out.", node_id)
        if request.error is not None:
            raise request.error
        if request.value is None:
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Native measurement returned no intrinsic result.", node_id)
        return request.value

    future: Future[LayoutResult] = pool.submit(
        compute_with_width_measurements, snapshot, compute, request_measure,
        compute_provisional=provisional, initial_widths=initial_widths,
    )

    def validate_live() -> None:
        if handle._cancelled.is_set() or current_generation() != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Stale or cancelled SFLE generation; no geometry committed.")
        if not is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Native measurement and geometry commit require UI thread.")

    def finish(result: LayoutResult | None, error: Exception | None) -> None:
        handle._finished = True
        pool.shutdown(wait=False)
        on_finished(result, error)

    def tick() -> None:
        if handle._finished:
            return
        # The callback must never examine or mutate toolkit objects off-UI.
        if not is_ui_thread():
            handle._cancelled.set()
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "SFLE UI dispatcher was invoked off its owner thread.")
        while True:
            try:
                request = pending.get_nowait()
            except queue.Empty:
                break
            try:
                validate_live()
                request.value = measure_on_ui(request.node_id, request.width)
                if not isinstance(request.value, IntrinsicSizes):
                    raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                    "Native measurement must return IntrinsicSizes.", request.node_id)
                validate_live()
            except Exception as exc:
                request.error = exc
            finally:
                request.ready.set()

        if not future.done() or not pending.empty():
            post_to_ui(tick)
            return
        try:
            result = future.result()
            validate_live()
            if result.generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Worker returned an obsolete SFLE generation.")
            ids = tuple(dict(result.boxes))
            validate_adapter_commit(
                snapshot, result,
                SFLEAdapterPorts(
                    current_generation=current_generation,
                    nodes_alive=nodes_alive or (lambda _: True),
                    apply_rectangles=apply_geometry,
                    read_rectangles=observed_geometry,
                ),
                scroll_viewports=scroll_viewports,
            )
            if nodes_alive is not None and not nodes_alive(ids):
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Native SFLE geometry references disposed nodes.")
            original = {node_id: dict(rect) for node_id, rect in observed_geometry().items()}
            if not original:
                raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                "Cannot commit without a native geometry observation port.")
            try:
                validate_live()
                apply_geometry(result)
                validate_live()
                if nodes_alive is not None and not nodes_alive(ids):
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Native node disposed during SFLE geometry application.")
                # A disappearing native observation is not successful geometry.
                # Preserve the exact set of UI-managed nodes across this commit.
                # Root/window nodes may be absent from both observations.
                observed_after = observed_geometry()
                if set(observed_after) != set(original):
                    raise SFLEError(
                        DiagnosticCode.INVALID_SNAPSHOT,
                        "Native geometry observation set changed during SFLE commit.",
                    )
                error = _observed_error(result, observed_after)
                if error > 1.0:
                    raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                                    "Native geometry commit exceeds 1.0 logical px.")
            except Exception:
                restore_geometry(original)
                raise
            finish(replace(result, geometry_commit_error=error), None)
        except Exception as exc:
            finish(None, exc)

    try:
        post_to_ui(tick)
    except Exception:
        handle.cancel()
        pool.shutdown(wait=False)
        raise
    return handle
