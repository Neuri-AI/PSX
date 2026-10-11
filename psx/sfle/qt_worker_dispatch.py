"""Asynchronous Qt worker compute with GUI-owned measurement and commit (RED contract).

The Qt event loop must remain responsive while an SFLE worker requests
height-for-width measurements; all QWidget calls stay on the GUI thread.
"""
from __future__ import annotations
from collections.abc import Callable
from .model import IntrinsicSizes, LayoutInput, LayoutResult


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
) -> object:
    raise NotImplementedError("Qt worker/UI measurement dispatcher not implemented")
