"""Asynchronous Qt GUI-owned measurements with worker-only SFLE computation.

QTimer pump is constructed on Qt's GUI thread; worker never handles QWidget.
All requests are fulfilled on GUI thread. Stale generations cannot commit.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from .errors import DiagnosticCode, SFLEError
from .model import IntrinsicSizes, LayoutInput, LayoutResult
from .remeasure_session import compute_with_width_measurements


@dataclass
class _Request:
    node_id: str
    width: float
    ready: threading.Event = field(default_factory=threading.Event)
    value: IntrinsicSizes | None = None
    error: Exception | None = None


class QtLayoutHandle:
    """Owns the UI pump and worker until the single completion callback."""

    def __init__(self, timer: object, pool: ThreadPoolExecutor,
                 future: Future[LayoutResult], cancel_flag: threading.Event) -> None:
        self._timer = timer
        self._pool = pool
        self._future = future
        self._finished = False
        self._cancel_flag = cancel_flag

    def done(self) -> bool:
        return self._finished

    def cancel(self) -> None:
        """Invalidate the transaction before any pending UI measurement or commit."""
        self._cancel_flag.set()


def start_qt_worker_layout(
    snapshot: LayoutInput,
    *,
    qtcore: object,
    compute: Callable[[LayoutInput], LayoutResult],
    provisional: Callable[[LayoutInput], LayoutResult],
    measure_on_ui: Callable[[str, float], IntrinsicSizes],
    current_generation: Callable[[], int],
    commit_on_ui: Callable[[LayoutResult], None],
    initial_widths: dict[str, float],
    on_finished: Callable[[LayoutResult | None, Exception | None], None],
) -> QtLayoutHandle:
    """Return immediately; schedule the worker and pump requests from Qt UI."""
    if qtcore.QThread.currentThread() != qtcore.QCoreApplication.instance().thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Qt asynchronous dispatcher must be started on the UI thread.")
    generation = snapshot.generation
    if current_generation() != generation:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale generation at start.")
    pending: queue.Queue[_Request] = queue.Queue()
    cancel_flag = threading.Event()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sfle-qt-compute")

    def worker_measure(node_id: str, width: float) -> IntrinsicSizes:
        if cancel_flag.is_set() or current_generation() != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Cancelled or stale Qt measurement.")
        request = _Request(node_id, width)
        pending.put(request)
        if not request.ready.wait(timeout=10):
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt GUI measurement request timed out.")
        if request.error is not None:
            raise request.error
        if current_generation() != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Generation changed during Qt measurement.")
        assert request.value is not None
        return request.value

    future = pool.submit(
        compute_with_width_measurements, snapshot, compute, worker_measure,
        compute_provisional=provisional, initial_widths=initial_widths,
    )
    timer = qtcore.QTimer()
    timer.setInterval(1)
    handle = QtLayoutHandle(timer, pool, future, cancel_flag)

    def tick() -> None:
        # QObject timer fires exclusively on the GUI thread.
        if qtcore.QThread.currentThread() != qtcore.QCoreApplication.instance().thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT, "Qt UI pump crossed threads.")
        while True:
            try:
                request = pending.get_nowait()
            except queue.Empty:
                break
            try:
                if cancel_flag.is_set() or current_generation() != generation:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Cancelled or stale Qt measurement request.")
                request.value = measure_on_ui(request.node_id, request.width)
                if current_generation() != generation:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Qt generation changed during native measurement.")
            except Exception as exc:
                request.error = exc
            finally:
                request.ready.set()
        if future.done() and pending.empty() and not handle._finished:
            handle._finished = True
            timer.stop()
            pool.shutdown(wait=False)
            try:
                result = future.result()
                if cancel_flag.is_set() or current_generation() != generation or result.generation != generation:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Stale Qt worker layout cannot commit.")
                commit_on_ui(result)
                on_finished(result, None)
            except Exception as exc:
                on_finished(None, exc)

    timer.timeout.connect(tick)
    timer.start()
    return handle
