"""Portable ProgressBar prop normalization and shared helpers.

Backends that do not accept arbitrary float ranges shift the value into a
zero-based range using ``relative_value`` and ``relative_max``. Backends
with int-only ranges use ``precision_factor`` from the Slider helpers to
map floats to ints without losing meaningful precision.
"""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import (
    PROGRESSBAR_DEFAULTS,
    PROGRESSBAR_PROPS,
    validate_progressbar_props,
)
from psx.core.errors import RendererCapabilityError


def progressbar_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_progressbar_props(props)
    return {**PROGRESSBAR_DEFAULTS, **props}


def updated_progressbar_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - PROGRESSBAR_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported ProgressBar props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return progressbar_props(result)


def relative_value(props: Mapping[str, object]) -> float:
    """``value`` shifted to a zero-based range and clamped to [0, max-min]."""
    lo = props["min"]
    hi = props["max"]
    span = hi - lo
    v = props["value"] - lo
    if v < 0:
        return 0.0
    if v > span:
        return float(span)
    return float(v)


def relative_max(props: Mapping[str, object]) -> float:
    """Total span of the bar, i.e. ``max - min``."""
    return float(props["max"] - props["min"])


# -- per-backend apply helpers ---------------------------------------------

def apply_qt_progressbar(widget: object, props: Mapping[str, object], binding: str) -> None:
    import importlib
    from psx.renderers.components.slider import precision_factor

    core = importlib.import_module(f"{binding}.QtCore")
    qt = core.Qt
    orientation_enum = getattr(qt, "Orientation", qt)

    p = progressbar_props(props)
    widget.setEnabled(bool(p["enabled"]))
    widget.setOrientation(
        orientation_enum.Horizontal if p["orientation"] == "horizontal"
        else orientation_enum.Vertical
    )

    if p["indeterminate"]:
        # Qt's idiomatic indeterminate mode: a range of (0, 0) makes the
        # bar animate continuously until the range is set again.
        widget.setRange(0, 0)
        return

    factor = precision_factor(p["min"], p["max"], 0.0)
    rel = relative_value(p)
    widget.setRange(
        int(round(p["min"] * factor)),
        int(round(p["max"] * factor)),
    )
    widget.setValue(int(round((p["min"] + rel) * factor)))

def apply_tk_progressbar(widget: object, props: Mapping[str, object]) -> None:
    p = progressbar_props(props)
    widget.configure(orient=p["orientation"])

    if p["indeterminate"]:
        widget.configure(mode="indeterminate")
        if not getattr(widget, "_psx_running", False):
            widget.start()
            widget._psx_running = True
    else:
        if getattr(widget, "_psx_running", False):
            widget.stop()
            widget._psx_running = False
        widget.configure(mode="determinate")
        widget.configure(maximum=relative_max(p))
        widget.configure(value=relative_value(p))

    widget.state(("!disabled",) if p["enabled"] else ("disabled",))