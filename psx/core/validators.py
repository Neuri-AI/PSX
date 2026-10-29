from __future__ import annotations

import math
import re
from urllib.parse import urlsplit
from collections.abc import Mapping
from .errors import RendererCapabilityError
from .layout_item import validate_flex_item_props
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
    FLEX_PROPS,
    FLEX_DEFAULTS,
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
    SELECT_PROPS,
    SELECT_DEFAULTS,
    SWITCH_PROPS,
    SWITCH_DEFAULTS,
    LINK_PROPS,
    LINK_DEFAULTS,
    BADGE_PROPS,
    BADGE_DEFAULTS,
    SPINBOX_PROPS,
    SPINBOX_DEFAULTS,
    SCROLL_PROPS,
    SCROLL_DEFAULTS,
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
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise RendererCapabilityError(f"Slider.{name} must be a finite number.")
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
    if not math.isfinite(font_size) or font_size <= 0:
        raise RendererCapabilityError("TextArea.font_size must be positive and finite.")

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
    if not math.isfinite(font_size) or font_size <= 0:
        raise RendererCapabilityError("Input.font_size must be positive and finite.")

    for name in ("enabled", "read_only", "password"):
        val = props.get(name, INPUT_DEFAULTS[name])
        if not isinstance(val, bool):
            raise RendererCapabilityError(f"Input.{name} must be a bool.")

    for name in ("on_change", "on_submit", "on_click"):
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
    for name in ("on_change", "on_submit", "on_click"):
        if props[name] is not None and not callable(props[name]):
            raise TypeError(f"Input '{name}' must be callable or None")


def validate_checkbox_props(props: Mapping[str, object]) -> None:
    if "label" in props and not isinstance(props["label"], str):
        raise RendererCapabilityError("Checkbox.label must be a str.")
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


def validate_flex_props(props: Mapping[str, object]) -> None:
    """Validate portable Flex syntax; SFLE later validates semantic support."""
    unknown = set(props) - FLEX_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Flex props: {', '.join(sorted(unknown))}")
    validate_flex_item_props(props, owner="Flex")
    # A Flex container's native dimensions ARE layout dimensions; other
    # controls retain their own width/height and use layout_* separately.
    for axis in ("width", "height", "min_width", "min_height", "max_width", "max_height"):
        if axis in props and f"layout_{axis}" in props:
            raise RendererCapabilityError(
                f"Conflicting Flex.{axis} and Flex.layout_{axis} declarations.")
    enums = {
        "direction": ("row", "row-reverse", "column", "column-reverse"),
        "wrap": ("nowrap", "wrap", "wrap-reverse"),
        "justify_content": ("flex-start", "flex-end", "center",
                            "space-between", "space-around", "space-evenly"),
        "align_items": ("stretch", "flex-start", "flex-end", "center", "baseline"),
        "align_content": ("normal", "stretch", "flex-start", "flex-end",
                          "center", "space-between", "space-around", "space-evenly"),
        "align_self": ("auto", "stretch", "flex-start", "flex-end", "center", "baseline"),
    }
    for name, allowed in enums.items():
        if name in props and props[name] not in allowed:
            raise RendererCapabilityError(f"Invalid Flex.{name}: {props[name]!r}.")
    from psx.sfle.lengths import parse_length, LengthKind
    def check_length(name: str, value: object, *, allow_auto: bool = False,
                     allow_none: bool = False, intrinsic: bool = False) -> None:
        try:
            parsed = parse_length(value)
        except (TypeError, ValueError) as error:
            raise RendererCapabilityError(f"Invalid Flex.{name} length.") from error
        allowed = {LengthKind.PX, LengthKind.PERCENT, LengthKind.VW, LengthKind.VH, LengthKind.VMIN, LengthKind.VMAX}
        if allow_auto:
            allowed.add(LengthKind.AUTO)
        if allow_none:
            allowed.add(LengthKind.NONE)
        if intrinsic:
            allowed.update((LengthKind.MIN_CONTENT, LengthKind.MAX_CONTENT))
        if parsed.kind not in allowed or (parsed.value is not None and parsed.value < 0):
            raise RendererCapabilityError(f"Unsupported Flex.{name} length.")
    for name in ("gap", "row_gap", "column_gap"):
        if name in props:
            check_length(name, props[name])
    for name in ("width", "height", "flex_basis", "layout_width", "layout_height",
                 "min_width", "min_height", "layout_min_width", "layout_min_height"):
        if name in props:
            check_length(name, props[name], allow_auto=True, intrinsic=True)
    for name in ("max_width", "max_height", "layout_max_width", "layout_max_height"):
        if name in props:
            check_length(name, props[name], allow_none=True, intrinsic=True)
    if "padding" in props:
        edges = props["padding"]
        if not isinstance(edges, (tuple, list)):
            edges = (edges,)
        if len(edges) not in (1, 2, 4):
            raise RendererCapabilityError("Flex.padding requires 1, 2 or 4 lengths.")
        for edge in edges:
            check_length("padding", edge)
    for name in ("flex_grow", "flex_shrink"):
        if name in props:
            value = props[name]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise RendererCapabilityError(f"Flex.{name} must be finite and >= 0.")
    if "order" in props:
        value = props["order"]
        if (isinstance(value, bool) or not isinstance(value, int)
                or not -(1 << 31) <= value < (1 << 31)):
            raise RendererCapabilityError("Flex.order must be signed 32-bit.")


def validate_progressbar_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - PROGRESSBAR_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported ProgressBar props: {', '.join(sorted(unknown))}"
        )

    for name in ("value", "min", "max"):
        v = props.get(name, PROGRESSBAR_DEFAULTS[name])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise RendererCapabilityError(f"ProgressBar.{name} must be a finite number.")

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

def validate_select_props(props: Mapping[str, object]) -> None:
    """Validate a controlled Select without coercing option values."""
    unknown = set(props) - SELECT_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Select props: {', '.join(sorted(unknown))}"
        )

    options = props.get("options", SELECT_DEFAULTS["options"])
    if not isinstance(options, (tuple, list)):
        raise RendererCapabilityError("Select.options must be a list or tuple.")

    values: set[str | int] = set()
    labels: set[str] = set()
    for option in options:
        if isinstance(option, str):
            label, value = option, option
        elif isinstance(option, Mapping) and set(option) == {"label", "value"}:
            label, value = option["label"], option["value"]
        else:
            raise RendererCapabilityError(
                "Select options must be strings or mappings with label/value."
            )
        if not isinstance(label, str):
            raise RendererCapabilityError("Select option labels must be strings.")
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise RendererCapabilityError("Select option values must be str or int.")
        if label in labels or value in values:
            raise RendererCapabilityError("Select option labels and values must be unique.")
        labels.add(label)
        values.add(value)

    selected = props.get("value", SELECT_DEFAULTS["value"])
    if selected is not None and (
        isinstance(selected, bool) or not isinstance(selected, (str, int))
    ):
        raise RendererCapabilityError("Select.value must be str, int, or None.")

    placeholder = props.get("placeholder", SELECT_DEFAULTS["placeholder"])
    if not isinstance(placeholder, str):
        raise RendererCapabilityError("Select.placeholder must be a str.")
    if placeholder in labels:
        raise RendererCapabilityError("Select.placeholder must differ from option labels.")

    enabled = props.get("enabled", SELECT_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("Select.enabled must be a bool.")

    callback = props.get("on_change", SELECT_DEFAULTS["on_change"])
    if callback is not None and not callable(callback):
        raise RendererCapabilityError("Select.on_change must be callable or None.")


def validate_switch_props(props: Mapping[str, object]) -> None:
    """Validate portable controlled Switch props."""
    unknown = set(props) - SWITCH_PROPS - {"key", "ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Switch props: {', '.join(sorted(unknown))}"
        )
    for name in ("checked", "enabled"):
        if not isinstance(props.get(name, SWITCH_DEFAULTS[name]), bool):
            raise RendererCapabilityError(f"Switch.{name} must be a bool.")
    if not isinstance(props.get("label", SWITCH_DEFAULTS["label"]), str):
        raise RendererCapabilityError("Switch.label must be a str.")
    if props.get("size", SWITCH_DEFAULTS["size"]) not in ("small", "medium", "large"):
        raise RendererCapabilityError(
            "Switch.size must be 'small', 'medium', or 'large'."
        )
    color = props.get("color", SWITCH_DEFAULTS["color"])
    if not isinstance(color, str) or _HEX_COLOR_RE.fullmatch(color) is None:
        raise RendererCapabilityError("Switch.color must be a #RRGGBB string.")
    callback = props.get("on_change", SWITCH_DEFAULTS["on_change"])
    if callback is not None and not callable(callback):
        raise RendererCapabilityError("Switch.on_change must be callable or None.")


def validate_link_props(props: Mapping[str, object]) -> None:
    """Require exactly one navigation mechanism at a time."""
    unknown = set(props) - LINK_PROPS - {"ref", "key"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Link props: {', '.join(sorted(unknown))}"
        )

    label = props.get("label", LINK_DEFAULTS["label"])
    if not isinstance(label, str):
        raise RendererCapabilityError("Link.label must be a str.")

    href = props.get("href", LINK_DEFAULTS["href"])
    callback = props.get("on_click", LINK_DEFAULTS["on_click"])
    if href is not None:
        if not isinstance(href, str) or not href.strip():
            raise RendererCapabilityError("Link.href must be a nonempty URL string or None.")
        try:
            parsed = urlsplit(href)
            valid = parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)
        except ValueError:
            valid = False
        if not valid:
            raise RendererCapabilityError(
                "Link.href must be an absolute http:// or https:// URL."
            )
    if callback is not None and not callable(callback):
        raise RendererCapabilityError("Link.on_click must be callable or None.")
    if href is not None and callback is not None:
        raise RendererCapabilityError("Link.href and Link.on_click are mutually exclusive.")

    color = props.get("color", LINK_DEFAULTS["color"])
    if color is not None and (
        not isinstance(color, str) or _HEX_COLOR_RE.fullmatch(color) is None
    ):
        raise RendererCapabilityError("Link.color must be a #RRGGBB string or None.")
    for name in ("underline", "enabled"):
        if not isinstance(props.get(name, LINK_DEFAULTS[name]), bool):
            raise RendererCapabilityError(f"Link.{name} must be a bool.")


def validate_badge_props(props: Mapping[str, object]) -> None:
    """Validate the closed portable Badge presentation contract."""
    unknown = set(props) - BADGE_PROPS - {"key", "ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Badge props: {', '.join(sorted(unknown))}"
        )
    if not isinstance(props.get("label", BADGE_DEFAULTS["label"]), str):
        raise RendererCapabilityError("Badge.label must be a str.")
    choices = {
        "variant": ("neutral", "success", "warning", "danger", "info"),
        "appearance": ("filled", "outline"),
        "size": ("small", "medium", "large"),
        "shape": ("rounded", "pill"),
    }
    for name, allowed in choices.items():
        if props.get(name, BADGE_DEFAULTS[name]) not in allowed:
            raise RendererCapabilityError(
                f"Badge.{name} must be one of: {', '.join(allowed)}."
            )
    if not isinstance(props.get("enabled", BADGE_DEFAULTS["enabled"]), bool):
        raise RendererCapabilityError("Badge.enabled must be a bool.")


def validate_spinbox_props(props: Mapping[str, object]) -> None:
    """Validate numeric configuration independently of any UI backend."""
    from decimal import Decimal

    unknown = set(props) - SPINBOX_PROPS - {"key", "ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported SpinBox props: {', '.join(sorted(unknown))}"
        )

    decimals = props.get("decimals", SPINBOX_DEFAULTS["decimals"])
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 9:
        raise RendererCapabilityError("SpinBox.decimals must be an int between 0 and 9.")

    numbers: dict[str, Decimal] = {}
    for name in ("value", "min", "max", "step"):
        value = props.get(name, SPINBOX_DEFAULTS[name])
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RendererCapabilityError(f"SpinBox.{name} must be a finite int or float.")
        if not math.isfinite(value):
            raise RendererCapabilityError(f"SpinBox.{name} must be finite.")
        numbers[name] = Decimal(str(value))

    if numbers["min"] > numbers["max"]:
        raise RendererCapabilityError("SpinBox.min cannot exceed SpinBox.max.")
    if numbers["step"] <= 0:
        raise RendererCapabilityError("SpinBox.step must be positive.")

    quantum = Decimal(1).scaleb(-decimals)
    if numbers["step"] < quantum or numbers["step"] % quantum != 0:
        raise RendererCapabilityError(
            "SpinBox.step must be a multiple of the selected decimal precision."
        )
    # Clamping must always result in an exactly representable boundary.
    for name in ("min", "max"):
        if numbers[name] % quantum != 0:
            raise RendererCapabilityError(
                f"SpinBox.{name} must fit within decimals={decimals} precision."
            )

    enabled = props.get("enabled", SPINBOX_DEFAULTS["enabled"])
    if not isinstance(enabled, bool):
        raise RendererCapabilityError("SpinBox.enabled must be a bool.")

    callback = props.get("on_change", SPINBOX_DEFAULTS["on_change"])
    if callback is not None and not callable(callback):
        raise RendererCapabilityError("SpinBox.on_change must be callable or None.")


def validate_scroll_props(props: Mapping[str, object]) -> None:
    """Validate portable scroll viewport, content flow and visibility options."""
    unknown = set(props) - SCROLL_PROPS - {"key", "ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Scroll props: {', '.join(sorted(unknown))}"
        )
    variants = {
        "direction": ("vertical", "horizontal", "both"),
        "content_direction": ("vertical", "horizontal"),
        "scrollbar": ("auto", "always", "hidden"),
    }
    for name, allowed in variants.items():
        if props.get(name, SCROLL_DEFAULTS[name]) not in allowed:
            raise RendererCapabilityError(
                f"Scroll.{name} must be one of {', '.join(allowed)}."
            )
    for name in ("width", "height"):
        value = props.get(name, SCROLL_DEFAULTS[name])
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0
        ):
            raise RendererCapabilityError(
                f"Scroll.{name} must be None or a positive finite number."
            )
    spacing = props.get("spacing", SCROLL_DEFAULTS["spacing"])
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise RendererCapabilityError("Scroll.spacing must be a non-negative integer.")
    padding = props.get("padding", SCROLL_DEFAULTS["padding"])
    values = (padding,) if isinstance(padding, int) else padding
    if not isinstance(values, (tuple, list)) or len(values) not in (1, 2, 4) or any(
        isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values
    ):
        raise RendererCapabilityError(
            "Scroll.padding must be a non-negative int or a 2-/4-int tuple."
        )
    if not isinstance(props.get("enabled", SCROLL_DEFAULTS["enabled"]), bool):
        raise RendererCapabilityError("Scroll.enabled must be a bool.")
