"""Internal, backend-independent contracts for portable PSX components.

Contracts are the single source of truth for portable property names,
defaults, validation, events and child policy.  The legacy public builders
retain their established signatures and delegate here.
"""

from __future__ import annotations

from .props import *
from .defaults import *

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from .validators import (
    validate_button_props,
    validate_checkbox_props,
    validate_column_props,
    validate_input_props,
    validate_row_props,
    validate_slider_props,
    validate_text_props,
    validate_textarea_props,
    validate_spacer_props,
    validate_divider_props,
    validate_image_props,
    validate_progressbar_props,
    validate_radio_props,
    validate_radiogroup_props,
    validate_select_props,
    validate_switch_props,
    validate_link_props,
    validate_spinbox_props,
    validate_scroll_props,
)
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


TEXT_CONTRACT = ComponentContract(
    "Text",
    TEXT_PROPS,
    TEXT_DEFAULTS,
    frozenset(),
    "text-only",
    validate_text_props,
    content_property="value"
)
BUTTON_CONTRACT = ComponentContract(
    "Button", BUTTON_PROPS,
    BUTTON_DEFAULTS,
    frozenset({"on_click"}),
    "text-only",
    validate_button_props,
    content_property="label"
)

CHECKBOX_CONTRACT = ComponentContract(
    "Checkbox",
    CHECKBOX_PROPS,
    CHECKBOX_DEFAULTS,
    frozenset({"on_change"}),
    "none",
    validate_checkbox_props
)

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
ROW_CONTRACT = ComponentContract(
    "Row", ROW_PROPS, ROW_DEFAULTS, frozenset(), "multiple", validate_row_props,
)
SLIDER_CONTRACT = ComponentContract(
    "Slider",
    SLIDER_PROPS,
    SLIDER_DEFAULTS,
    frozenset({"on_change"}),
    "none",
    validate_slider_props,
)

SPACER_CONTRACT = ComponentContract(
    "Spacer",
    SPACER_PROPS,
    SPACER_DEFAULTS,
    frozenset(),
    "none",
    validate_spacer_props,
)

DIVIDER_CONTRACT = ComponentContract(
    "Divider",
    DIVIDER_PROPS,
    DIVIDER_DEFAULTS,
    frozenset(),
    "none-or-single",
    validate_divider_props,
)

IMAGE_CONTRACT = ComponentContract(
    "Image",
    IMAGE_PROPS,
    IMAGE_DEFAULTS,
    frozenset(),
    "none",
    validate_image_props,
)

PROGRESSBAR_CONTRACT = ComponentContract(
    "ProgressBar",
    PROGRESSBAR_PROPS,
    PROGRESSBAR_DEFAULTS,
    frozenset(),
    "none",
    validate_progressbar_props,
)

RADIO_CONTRACT = ComponentContract(
    "Radio",
    RADIO_PROPS,
    RADIO_DEFAULTS,
    frozenset(),
    "none",
    validate_radio_props,
)
RADIOGROUP_CONTRACT = ComponentContract(
    "RadioGroup",
    RADIOGROUP_PROPS,
    RADIOGROUP_DEFAULTS,
    frozenset({"on_change"}),
    "multiple",
    validate_radiogroup_props,
)
SELECT_CONTRACT = ComponentContract(
    "Select", SELECT_PROPS, SELECT_DEFAULTS,
    frozenset({"on_change"}), "none", validate_select_props,
)

SWITCH_CONTRACT = ComponentContract(
    "Switch", SWITCH_PROPS, SWITCH_DEFAULTS,
    frozenset({"on_change"}), "none", validate_switch_props,
)

LINK_CONTRACT = ComponentContract(
    "Link", LINK_PROPS, LINK_DEFAULTS,
    frozenset({"on_click"}), "text-only",
    validate_link_props, content_property="label",
)

SPINBOX_CONTRACT = ComponentContract(
    "SpinBox", SPINBOX_PROPS, SPINBOX_DEFAULTS,
    frozenset({"on_change"}), "none", validate_spinbox_props,
)

SCROLL_CONTRACT = ComponentContract(
    "Scroll", SCROLL_PROPS, SCROLL_DEFAULTS,
    frozenset(), "multiple", validate_scroll_props,
)
