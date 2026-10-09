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


def precision_factor(min_value: float, max_value: float, step: float) -> int:
    """Mapea floats → enteros para QSlider."""
    if step > 0:
        return max(1, round(1.0 / step))
    places = 0
    for v in (min_value, max_value):
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        if "." in s:
            places = max(places, len(s.split(".")[1]))
    return 10 ** min(places, 6) if places else 1000


# ── apply_* por backend (igual que Input/TextArea) ──

def apply_kivy_slider(widget, props):
    widget._psx_updating = True
    widget.orientation = props["orientation"]
    widget.min = float(props["min_value"])
    widget.max = float(props["max_value"])
    widget.step = float(props["step"]) if props["step"] > 0 else 0
    widget.value = float(props["value"])
    widget.disabled = not bool(props["enabled"])
    widget._psx_updating = False


def apply_tk_slider(widget, props):
    import tkinter as tk
    widget._psx_updating = True
    widget.configure(
        from_=float(props["min_value"]),
        to=float(props["max_value"]),
        orient=tk.HORIZONTAL if props["orientation"] == "horizontal" else tk.VERTICAL,
    )
    widget.set(float(props["value"]))
    widget.state(["!disabled"] if props["enabled"] else ["disabled"])
    widget._psx_updating = False


def apply_qt_slider(widget, props, binding):
    import importlib
    core = importlib.import_module(f"{binding}.QtCore")
    qt = core.Qt
    orientation_enum = getattr(qt, "Orientation", qt)

    factor = precision_factor(props["min_value"], props["max_value"], props["step"])
    widget._psx_factor = factor
    widget._psx_props = dict(props)

    widget.blockSignals(True)
    widget.setOrientation(
        orientation_enum.Horizontal if props["orientation"] == "horizontal"
        else orientation_enum.Vertical
    )
    widget.setMinimum(int(round(props["min_value"] * factor)))
    widget.setMaximum(int(round(props["max_value"] * factor)))
    widget.setSingleStep(
        max(1, int(round(props["step"] * factor))) if props["step"] > 0 else 1
    )
    widget.setValue(int(round(props["value"] * factor)))
    widget.setEnabled(bool(props["enabled"]))
    widget.blockSignals(False)