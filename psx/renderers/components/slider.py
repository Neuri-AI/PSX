"""Portable Slider prop normalization shared by native renderers."""

from collections.abc import Mapping

from psx.core.contracts import SLIDER_DEFAULTS, SLIDER_PROPS, validate_slider_props
from psx.core.errors import RendererCapabilityError


def slider_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_slider_props(props)
    return {**SLIDER_DEFAULTS, **props}


def updated_slider_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - SLIDER_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Slider props: {', '.join(sorted(unknown))}"
        )
    result = {k: v for k, v in current.items() if k not in removed}
    result.update(changed)
    return slider_props(result)


def clamp_value(props: Mapping[str, object]) -> float:
    """Return ``value`` clamped to the ``[min, max]`` range.

    Out-of-range values are a normal part of reconciliation: a decrement
    button that goes from 0 to -1 should not crash the app. The stored
    props keep the original value so that a subsequent update to a
    different out-of-range value is still detected as a change, but the
    widget is always shown at the closest valid position.
    """
    lo = props["min"]
    hi = props["max"]
    value = props["value"]
    if value < lo:
        return float(lo)
    if value > hi:
        return float(hi)
    return float(value)


def precision_factor(lo: float, hi: float, step: float) -> int:
    """Map a float range to an integer range for QSlider."""
    if step > 0:
        return max(1, round(1.0 / step))
    places = 0
    for v in (lo, hi):
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        if "." in s:
            places = max(places, len(s.split(".")[1]))
    return 10 ** min(places, 6) if places else 1000


# -- per-backend apply helpers ---------------------------------------------

def apply_kivy_slider(widget, props):
    widget._psx_updating = True
    widget.orientation = props["orientation"]
    widget.min = float(props["min"])
    widget.max = float(props["max"])
    widget.step = float(props["step"]) if props["step"] > 0 else 0
    widget.value = clamp_value(props)
    widget.disabled = not bool(props["enabled"])
    widget._psx_updating = False


def apply_tk_slider(widget, props):
    import tkinter as tk
    widget._psx_updating = True
    widget.configure(
        from_=float(props["min"]),
        to=float(props["max"]),
        orient=tk.HORIZONTAL if props["orientation"] == "horizontal" else tk.VERTICAL,
    )
    widget.set(clamp_value(props))
    widget.state(["!disabled"] if props["enabled"] else ["disabled"])
    widget._psx_updating = False


def apply_qt_slider(widget, props, binding):
    import importlib
    core = importlib.import_module(f"{binding}.QtCore")
    qt = core.Qt
    orientation_enum = getattr(qt, "Orientation", qt)

    factor = precision_factor(props["min"], props["max"], props["step"])
    widget._psx_factor = factor
    widget._psx_props = dict(props)

    widget.blockSignals(True)
    widget.setOrientation(
        orientation_enum.Horizontal if props["orientation"] == "horizontal"
        else orientation_enum.Vertical
    )
    widget.setMinimum(int(round(props["min"] * factor)))
    widget.setMaximum(int(round(props["max"] * factor)))
    widget.setSingleStep(
        max(1, int(round(props["step"] * factor))) if props["step"] > 0 else 1
    )
    widget.setValue(int(round(clamp_value(props) * factor)))
    widget.setEnabled(bool(props["enabled"]))
    widget.blockSignals(False)