from __future__ import annotations

import math
import re
from collections.abc import Mapping
from .errors import RendererCapabilityError
from .contracts import (
    TEXTAREA_PROPS,
    TEXTAREA_DEFAULTS,
    TEXT_PROPS,
    TEXT_DEFAULTS,
    BUTTON_PROPS,
    BUTTON_DEFAULTS,
    INPUT_PROPS,
    INPUT_DEFAULTS,
    CHECKBOX_PROPS,
    ROW_PROPS,
    ROW_DEFAULTS,
    COLUMN_PROPS,
    COLUMN_DEFAULTS,
    SLIDER_PROPS,
    SLIDER_DEFAULTS,
    IMAGE_PROPS,
    IMAGE_DEFAULTS,
    PROGRESSBAR_PROPS,
    PROGRESSBAR_DEFAULTS,
    RADIO_PROPS,
    RADIO_DEFAULTS,
    RADIOGROUP_PROPS,
    RADIOGROUP_DEFAULTS,
)

_VALID_ALIGN = frozenset({"start", "center", "end", "stretch"})
_VALID_ORIENTATIONS = frozenset({"horizontal", "vertical"})
_VALID_DIVIDER_ORIENTATIONS = frozenset({"horizontal", "vertical"})
_VALID_IMAGE_FITS = frozenset({"contain", "cover", "fill", "none"})
_VALID_RADIOGROUP_ORIENTATIONS = frozenset({"vertical", "horizontal"})
_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")

def validate_image_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - IMAGE_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Image props: {', '.join(sorted(unknown))}"
        )

    source = props.get("source")
    if not isinstance(source, str) or not source:
        raise RendererCapabilityError("Image.source must be a non-empty str.")

    fit = props.get("fit", IMAGE_DEFAULTS["fit"])
    if fit not in _VALID_IMAGE_FITS:
        raise RendererCapabilityError(
            f"Image.fit must be one of {sorted(_VALID_IMAGE_FITS)}."
        )

    for name in ("width", "height"):
        value = props.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RendererCapabilityError(
                f"Image.{name} must be a positive int or None."
            )

    alt = props.get("alt", IMAGE_DEFAULTS["alt"])
    if not isinstance(alt, str):
        raise RendererCapabilityError("Image.alt must be a str.")

    enabled = props.get("enabled", IMAGE_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Image.enabled must be a bool.")

def validate_divider_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - {"orientation", "thickness", "color", "ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Divider props: {', '.join(sorted(unknown))}"
        )

    orientation = props.get("orientation", "horizontal")
    if orientation not in _VALID_DIVIDER_ORIENTATIONS:
        raise RendererCapabilityError(
            f"Divider.orientation must be one of {sorted(_VALID_DIVIDER_ORIENTATIONS)}."
        )

    thickness = props.get("thickness", 1)
    if isinstance(thickness, bool) or not isinstance(thickness, int) or thickness < 1:
        raise RendererCapabilityError("Divider.thickness must be an int >= 1.")

    color = props.get("color")
    if color is not None and (
        not isinstance(color, str) or _HEX_COLOR_RE.fullmatch(color) is None
    ):
        raise RendererCapabilityError(
            "Divider.color must be None or use #RRGGBB format."
        )


def validate_spacer_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Spacer props: {', '.join(sorted(unknown))}"
        )


def validate_slider_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - SLIDER_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Slider props: {', '.join(sorted(unknown))}"
        )

    for name in ("value", "min", "max", "step"):
        v = props.get(name, SLIDER_DEFAULTS[name])
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise RendererCapabilityError(f"Slider.{name} must be a number.")
        if name == "step" and v < 0:
            raise RendererCapabilityError("Slider.step must be >= 0.")

    lo = props.get("min", SLIDER_DEFAULTS["min"])
    hi = props.get("max", SLIDER_DEFAULTS["max"])
    if lo >= hi:
        raise RendererCapabilityError("Slider.min must be < max.")

    # NOTE: Slider.value is deliberately NOT range-checked here. During
    # reconciliation, a transient state (for example, a decrement that
    # briefly goes below min) would otherwise crash the app. The widget
    # clamps the value to [min, max] when it is applied.

    orientation = props.get("orientation", SLIDER_DEFAULTS["orientation"])
    if orientation not in _VALID_ORIENTATIONS:
        raise RendererCapabilityError(
            f"Slider.orientation must be one of {sorted(_VALID_ORIENTATIONS)}."
        )

    enabled = props.get("enabled", SLIDER_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Slider.enabled must be a bool.")

    cb = props.get("on_change", SLIDER_DEFAULTS["on_change"])
    if cb is not None and not callable(cb):
        raise RendererCapabilityError("Slider.on_change must be callable or None.")

def validate_textarea_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - TEXTAREA_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported TextArea props: {', '.join(sorted(unknown))}"
        )

    value = props.get("value", TEXTAREA_DEFAULTS["value"])
    if not isinstance(value, str):
        raise RendererCapabilityError("TextArea.value must be a str.")

    placeholder = props.get("placeholder", TEXTAREA_DEFAULTS["placeholder"])
    if not isinstance(placeholder, str):
        raise RendererCapabilityError("TextArea.placeholder must be a str.")

    font_size = props.get("font_size", TEXTAREA_DEFAULTS["font_size"])
    if isinstance(font_size, bool) or not isinstance(font_size, (int, float)):
        raise RendererCapabilityError(
            "TextArea.font_size must be a positive finite number.")
    if font_size <= 0:
        raise RendererCapabilityError("TextArea.font_size must be positive.")

    for name in ("enabled", "read_only"):
        val = props.get(name, TEXTAREA_DEFAULTS[name])
        if not isinstance(val, bool):
            raise RendererCapabilityError(f"TextArea.{name} must be a bool.")

    cb = props.get("on_change", TEXTAREA_DEFAULTS["on_change"])
    if cb is not None and not callable(cb):
        raise RendererCapabilityError(
            "TextArea.on_change must be callable or None.")


def validate_text_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - TEXT_PROPS - {"ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Text props: {', '.join(sorted(unknown))}")
    value = props.get("value")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise RendererCapabilityError("Text.value must be str, int, or float.")
    size = props.get("font_size", TEXT_DEFAULTS["font_size"])
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
        raise RendererCapabilityError(
            "Text.font_size must be a positive finite number.")
    for name in ("bold", "italic", "enabled"):
        if name in props and not isinstance(props[name], bool):
            raise RendererCapabilityError(f"Text.{name} must be a bool.")
    color = props.get("color", TEXT_DEFAULTS["color"])
    if color is not None and (not isinstance(color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", color) is None):
        raise RendererCapabilityError(
            "Text.color must be None or use #RRGGBB format.")
    align = props.get("align", TEXT_DEFAULTS["align"])
    if not isinstance(align, str) or align not in {"left", "center", "right"}:
        raise RendererCapabilityError(
            "Text.align must be left, center, or right.")


def validate_button_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - BUTTON_PROPS - {"ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Button props: {', '.join(sorted(unknown))}")
    label = props.get("label")
    if isinstance(label, bool) or not isinstance(label, (str, int, float)):
        raise RendererCapabilityError(
            "Button label must be str, int, or float, not bool.")
    size = props.get("font_size", BUTTON_DEFAULTS["font_size"])
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0:
        raise RendererCapabilityError(
            "Button.font_size must be a positive finite number.")
    enabled = props.get("enabled", BUTTON_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Button.enabled must be a bool.")
    on_click = props.get("on_click", BUTTON_DEFAULTS["on_click"])
    if on_click is not None and not callable(on_click):
        raise RendererCapabilityError(
            "Button.on_click must be callable or None.")


def validate_input_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - INPUT_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Input props: {', '.join(sorted(unknown))}"
        )

    value = props.get("value", INPUT_DEFAULTS["value"])
    if not isinstance(value, str):
        raise RendererCapabilityError("Input.value must be a str.")

    placeholder = props.get("placeholder", INPUT_DEFAULTS["placeholder"])
    if not isinstance(placeholder, str):
        raise RendererCapabilityError("Input.placeholder must be a str.")

    font_size = props.get("font_size", INPUT_DEFAULTS["font_size"])
    if isinstance(font_size, bool) or not isinstance(font_size, (int, float)):
        raise RendererCapabilityError(
            "Input.font_size must be a positive finite number.")
    if font_size <= 0:
        raise RendererCapabilityError("Input.font_size must be positive.")

    for name in ("enabled", "read_only", "password"):
        val = props.get(name, INPUT_DEFAULTS[name])
        if not isinstance(val, bool):
            raise RendererCapabilityError(f"Input.{name} must be a bool.")

    for name in ("on_change", "on_submit"):
        cb = props.get(name, INPUT_DEFAULTS[name])
        if cb is not None and not callable(cb):
            raise RendererCapabilityError(
                f"Input.{name} must be callable or None.")


def validate_input_builder(props: Mapping[str, object]) -> None:
    unknown = set(props) - INPUT_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Input received unsupported properties: {', '.join(sorted(unknown))}")
    value = props["value"]
    placeholder = props["placeholder"]
    font_size = props["font_size"]
    if not isinstance(value, str):
        raise TypeError(
            f"Input 'value' must be a str, got {type(value).__name__}")
    if not isinstance(placeholder, str):
        raise TypeError(
            f"Input 'placeholder' must be a str, got {type(placeholder).__name__}")
    if isinstance(font_size, bool) or not isinstance(font_size, (int, float)):
        raise TypeError(
            f"Input 'font_size' must be a positive number, got {type(font_size).__name__}")
    if math.isnan(font_size) or math.isinf(font_size) or font_size <= 0:
        raise ValueError("Input 'font_size' must be a positive finite number")
    for name in ("enabled", "read_only", "password"):
        if not isinstance(props[name], bool):
            raise TypeError(
                f"Input '{name}' must be a bool, got {type(props[name]).__name__}")
    for name in ("on_change", "on_submit"):
        if props[name] is not None and not callable(props[name]):
            raise TypeError(f"Input '{name}' must be callable or None")


def validate_checkbox_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - CHECKBOX_PROPS - {"ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Checkbox props: {', '.join(sorted(unknown))}")
    for name in ("checked", "enabled"):
        if name in props and not isinstance(props[name], bool):
            raise RendererCapabilityError(f"Checkbox.{name} must be a bool.")
    if props.get("on_change") is not None and not callable(props["on_change"]):
        raise RendererCapabilityError(
            "Checkbox.on_change must be callable or None.")


def _validate_padding(value: object, name: str) -> None:
    if isinstance(value, bool):
        raise RendererCapabilityError(f"{name} must not be a bool.")
    if isinstance(value, int):
        if value < 0:
            raise RendererCapabilityError(f"{name} must be >= 0.")
        return
    if isinstance(value, (tuple, list)):
        if len(value) not in (2, 4):
            raise RendererCapabilityError(
                f"{name} must be int, (h, v), or (l, t, r, b)."
            )
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int) or item < 0:
                raise RendererCapabilityError(
                    f"{name} tuple elements must be ints >= 0."
                )
        return
    raise RendererCapabilityError(f"{name} must be int or tuple of ints.")


def validate_column_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - COLUMN_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Column props: {', '.join(sorted(unknown))}"
        )

    spacing = props.get("spacing", COLUMN_DEFAULTS["spacing"])
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise RendererCapabilityError(
            "Column.spacing must be a non-negative int.")

    _validate_padding(
        props.get("padding", COLUMN_DEFAULTS["padding"]), "Column.padding")

    align = props.get("align", COLUMN_DEFAULTS["align"])
    if align not in _VALID_ALIGN:
        raise RendererCapabilityError(
            f"Column.align must be one of {sorted(_VALID_ALIGN)}."
        )

    expand = props.get("expand", COLUMN_DEFAULTS["expand"])
    if isinstance(expand, bool):
        pass
    elif isinstance(expand, (tuple, list)):
        if not all(isinstance(x, bool) for x in expand):
            raise RendererCapabilityError(
                "Column.expand tuple must contain only bools."
            )
    else:
        raise RendererCapabilityError(
            "Column.expand must be bool or tuple of bool."
        )

    enabled = props.get("enabled", COLUMN_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Column.enabled must be a bool.")


def validate_row_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - ROW_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Row props: {', '.join(sorted(unknown))}")
    spacing = props.get("spacing", ROW_DEFAULTS["spacing"])
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise RendererCapabilityError(
            "Row.spacing must be a non-negative int.")
    _validate_padding(
        props.get("padding", ROW_DEFAULTS["padding"]), "Row.padding")
    align = props.get("align", ROW_DEFAULTS["align"])
    if align not in _VALID_ALIGN:
        raise RendererCapabilityError(
            f"Row.align must be one of {sorted(_VALID_ALIGN)}.")
    expand = props.get("expand", ROW_DEFAULTS["expand"])
    if not isinstance(expand, bool) and not (
        isinstance(expand, (tuple, list)) and all(
            isinstance(item, bool) for item in expand)
    ):
        raise RendererCapabilityError(
            "Row.expand must be bool or tuple of bool.")
    enabled = props.get("enabled", ROW_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Row.enabled must be a bool.")

def validate_progressbar_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - PROGRESSBAR_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported ProgressBar props: {', '.join(sorted(unknown))}"
        )

    for name in ("value", "min", "max"):
        v = props.get(name, PROGRESSBAR_DEFAULTS[name])
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise RendererCapabilityError(f"ProgressBar.{name} must be a number.")

    lo = props.get("min", PROGRESSBAR_DEFAULTS["min"])
    hi = props.get("max", PROGRESSBAR_DEFAULTS["max"])
    if lo >= hi:
        raise RendererCapabilityError("ProgressBar.min must be < max.")

    indeterminate = props.get("indeterminate", PROGRESSBAR_DEFAULTS["indeterminate"])
    if not isinstance(indeterminate, bool):
        raise RendererCapabilityError("ProgressBar.indeterminate must be a bool.")

    orientation = props.get("orientation", PROGRESSBAR_DEFAULTS["orientation"])
    if orientation not in _VALID_ORIENTATIONS:
        raise RendererCapabilityError(
            f"ProgressBar.orientation must be one of {sorted(_VALID_ORIENTATIONS)}."
        )

    enabled = props.get("enabled", PROGRESSBAR_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("ProgressBar.enabled must be a bool.")


def validate_radio_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - RADIO_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Radio props: {', '.join(sorted(unknown))}"
        )

    value = props.get("value")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise RendererCapabilityError("Radio.value must be a str or int.")

    label = props.get("label", RADIO_DEFAULTS["label"])
    if not isinstance(label, str):
        raise RendererCapabilityError("Radio.label must be a str.")

    enabled = props.get("enabled", RADIO_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Radio.enabled must be a bool.")


def validate_radiogroup_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - RADIOGROUP_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported RadioGroup props: {', '.join(sorted(unknown))}"
        )

    value = props.get("value")
    if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
        raise RendererCapabilityError("RadioGroup.value must be a str, int, or None.")

    orientation = props.get("orientation", RADIOGROUP_DEFAULTS["orientation"])
    if orientation not in _VALID_RADIOGROUP_ORIENTATIONS:
        raise RendererCapabilityError(
            f"RadioGroup.orientation must be one of "
            f"{sorted(_VALID_RADIOGROUP_ORIENTATIONS)}."
        )

    spacing = props.get("spacing", RADIOGROUP_DEFAULTS["spacing"])
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise RendererCapabilityError("RadioGroup.spacing must be a non-negative int.")

    _validate_padding(
        props.get("padding", RADIOGROUP_DEFAULTS["padding"]), "RadioGroup.padding"
    )

    enabled = props.get("enabled", RADIOGROUP_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("RadioGroup.enabled must be a bool.")

    cb = props.get("on_change", RADIOGROUP_DEFAULTS["on_change"])
    if cb is not None and not callable(cb):
        raise RendererCapabilityError("RadioGroup.on_change must be callable or None.")