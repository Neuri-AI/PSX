"""F2.2.3 resolved non-stretch cross-axis item alignment.

Auto cross margins override align-items/align-self and are handled by the
existing margin solver. Stretch and baseline require separate sizing and
measurement contracts; this slice explicitly rejects those values.
"""

from __future__ import annotations

from enum import Enum

from .errors import DiagnosticCode, SFLECapabilityError
from .flex_math import _number


class CrossAlign(str, Enum):
    AUTO = "auto"
    FLEX_START = "flex-start"
    FLEX_END = "flex-end"
    CENTER = "center"
    STRETCH = "stretch"
    BASELINE = "baseline"


def resolve_cross_alignment(
    align_items: CrossAlign,
    align_self: CrossAlign,
    border_cross_size: float,
    line_cross_size: float,
    fixed_start_margin: float,
    fixed_end_margin: float,
    *,
    cross_forward: bool = True,
) -> float:
    """Return physical border-start offset relative to the line's top/left.

    Inputs are fixed used margins: callers must bypass this calculation
    when either cross margin is AUTO. Negative free space preserves unsafe
    overflow for center/flex-end. Reverse cross-axis mapping occurs last.
    """
    if not isinstance(align_items, CrossAlign) or not isinstance(align_self, CrossAlign):
        raise TypeError("align_items/align_self must be CrossAlign.")
    if align_items == CrossAlign.AUTO:
        raise ValueError("align-items cannot be auto.")
    if type(cross_forward) is not bool:
        raise TypeError("cross_forward must be bool.")
    border = _number(border_cross_size, "border_cross_size")
    line = _number(line_cross_size, "line_cross_size")
    start = _number(fixed_start_margin, "fixed_start_margin")
    end = _number(fixed_end_margin, "fixed_end_margin")
    if border < 0 or line < 0:
        raise ValueError("Cross-axis box sizes must be nonnegative.")
    chosen = align_items if align_self == CrossAlign.AUTO else align_self
    if chosen in (CrossAlign.STRETCH, CrossAlign.BASELINE):
        raise SFLECapabilityError(
            DiagnosticCode.UNSUPPORTED_FEATURE,
            f"{chosen.value} needs a dedicated sizing/baseline stage.",
        )
    free = line - border - start - end
    if chosen == CrossAlign.FLEX_START:
        logical = start
    elif chosen == CrossAlign.FLEX_END:
        logical = start + free
    else:
        logical = start + free / 2.0
    return logical if cross_forward else line - logical - border
