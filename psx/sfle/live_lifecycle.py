"""Atomic renderer lifecycle for active width-sensitive F2 transactions.

Provisional measurements must never be committed; final geometry requires
UI-thread checks, a live generation and observed native widget rectangles.
"""
from __future__ import annotations
from collections.abc import Callable, Mapping
from .model import IntrinsicSizes, LayoutInput, LayoutResult


def layout_measure_and_commit(
    snapshot: LayoutInput,
    *,
    compute: Callable[[LayoutInput], LayoutResult],
    provisional: Callable[[LayoutInput], LayoutResult],
    measure_fn: Callable[[str,float],IntrinsicSizes],
    is_ui_thread: Callable[[],bool],
    current_generation: Callable[[],int],
    apply_geometry: Callable[[LayoutResult],None],
    observed_geometry: Callable[[],Mapping[str,Mapping[str,float]]],
    initial_widths: dict[str,float],
) -> LayoutResult:
    raise NotImplementedError("F2 production active measurement lifecycle not integrated")
