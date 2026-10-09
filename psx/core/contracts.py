"""Internal, backend-independent contracts for portable PSX components.

Contracts are the single source of truth for portable property names,
defaults, validation, events and child policy.  The legacy public builders
retain their established signatures and delegate here.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .errors import RendererCapabilityError

Validator = Callable[[Mapping[str, object]], None]


@dataclass(frozen=True, slots=True)
class ComponentContract:
    """Portable component semantics without renderer dependencies.

    ``builder_validator`` is intentionally distinct where a legacy public
    builder has historically exposed different error types/messages than a
    renderer-side validation path.  This keeps the migration compatible while
    making that difference explicit and contained.
    """

    name: str
    properties: frozenset[str]
    defaults: Mapping[str, object]
    events: frozenset[str]
    child_policy: str
    validator: Validator
    builder_validator: Validator | None = None
    content_property: str | None = None

    def validate(self, props: Mapping[str, object]) -> None:
        self.validator(props)

    def validate_builder(self, props: Mapping[str, object]) -> None:
        (self.builder_validator or self.validator)(props)

    def with_defaults(self, props: Mapping[str, object]) -> dict[str, object]:
        self.validate(props)
        return {**self.defaults, **props}


TEXT_PROPS = frozenset({"value", "font_size", "bold",
                       "italic", "color", "align", "enabled"})
TEXT_DEFAULTS = MappingProxyType({"font_size": 16, "bold": False, "italic": False,
                                  "color": None, "align": "left", "enabled": True})
BUTTON_PROPS = frozenset({"label", "font_size", "on_click", "enabled"})
BUTTON_DEFAULTS = MappingProxyType(
    {"font_size": 14, "enabled": True, "on_click": None})
INPUT_PROPS = frozenset({
    "value", "placeholder", "font_size", "enabled",
    "read_only", "password", "on_change", "on_submit",
})
INPUT_DEFAULTS = MappingProxyType({
    "value": "",
    "placeholder": "",
    "font_size": 14,
    "enabled": True,
    "read_only": False,
    "password": False,
    "on_change": None,
    "on_submit": None,
})
CHECKBOX_PROPS = frozenset({"checked", "enabled", "on_change"})
CHECKBOX_DEFAULTS = MappingProxyType(
    {"checked": False, "enabled": True, "on_change": None})


TEXTAREA_PROPS = frozenset({
    "value", "placeholder", "font_size", "enabled",
    "read_only", "on_change",
})
TEXTAREA_DEFAULTS = MappingProxyType({
    "value": "",
    "placeholder": "",
    "font_size": 14,
    "enabled": True,
    "read_only": False,
    "on_change": None,
})
COLUMN_PROPS = frozenset({"spacing", "padding", "align", "expand", "enabled"})
COLUMN_DEFAULTS = MappingProxyType({
    "spacing": 0,
    "padding": 0,
    "align": "stretch",
    "expand": False,
    "enabled": True,
})

_VALID_ALIGN = frozenset({"start", "center", "end", "stretch"})

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
        raise RendererCapabilityError("TextArea.font_size must be a positive finite number.")
    if font_size <= 0:
        raise RendererCapabilityError("TextArea.font_size must be positive.")

    for name in ("enabled", "read_only"):
        val = props.get(name, TEXTAREA_DEFAULTS[name])
        if not isinstance(val, bool):
            raise RendererCapabilityError(f"TextArea.{name} must be a bool.")

    cb = props.get("on_change", TEXTAREA_DEFAULTS["on_change"])
    if cb is not None and not callable(cb):
        raise RendererCapabilityError("TextArea.on_change must be callable or None.")


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
        raise RendererCapabilityError("Input.font_size must be a positive finite number.")
    if font_size <= 0:
        raise RendererCapabilityError("Input.font_size must be positive.")

    for name in ("enabled", "read_only", "password"):
        val = props.get(name, INPUT_DEFAULTS[name])
        if not isinstance(val, bool):
            raise RendererCapabilityError(f"Input.{name} must be a bool.")

    for name in ("on_change", "on_submit"):
        cb = props.get(name, INPUT_DEFAULTS[name])
        if cb is not None and not callable(cb):
            raise RendererCapabilityError(f"Input.{name} must be callable or None.")


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
        raise RendererCapabilityError("Column.spacing must be a non-negative int.")

    _validate_padding(props.get("padding", COLUMN_DEFAULTS["padding"]), "Column.padding")

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


TEXT_CONTRACT = ComponentContract("Text", TEXT_PROPS, TEXT_DEFAULTS, frozenset(
), "text-only", validate_text_props, content_property="value")
BUTTON_CONTRACT = ComponentContract("Button", BUTTON_PROPS, BUTTON_DEFAULTS, frozenset(
    {"on_click"}), "text-only", validate_button_props, content_property="label")

CHECKBOX_CONTRACT = ComponentContract("Checkbox", CHECKBOX_PROPS, CHECKBOX_DEFAULTS, frozenset({
                                      "on_change"}), "none", validate_checkbox_props)


# Inputs
TEXTAREA_CONTRACT = ComponentContract(
    "TextArea",
    TEXTAREA_PROPS,
    TEXTAREA_DEFAULTS,
    frozenset({"on_change"}),
    "text",   # acepta un child string como valor inicial
    validate_textarea_props,
)

INPUT_CONTRACT = ComponentContract(
    "Input",
    INPUT_PROPS,
    INPUT_DEFAULTS,
    frozenset({"on_change", "on_submit"}),
    "none",
    validate_input_props,
)
COLUMN_CONTRACT = ComponentContract(
    "Column",
    COLUMN_PROPS,
    COLUMN_DEFAULTS,
    frozenset(),
    "multiple",
    validate_column_props,
)
