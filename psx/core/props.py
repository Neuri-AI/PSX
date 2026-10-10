TEXT_PROPS = frozenset({
    "value",
    "font_size",
    "bold",
    "italic",
    "color",
    "align",
    "enabled"
})

BUTTON_PROPS = frozenset({
    "label",
    "font_size",
    "on_click",
    "enabled"
})

INPUT_PROPS = frozenset({
    "value",
    "placeholder",
    "font_size",
    "enabled",
    "read_only",
    "password",
    "on_change",
    "on_submit",
})

CHECKBOX_PROPS = frozenset({
    "checked",
    "enabled",
    "on_change"
})

TEXTAREA_PROPS = frozenset({
    "value", "placeholder", "font_size", "enabled",
    "read_only", "on_change",
})

COLUMN_PROPS = frozenset({
    "spacing",
    "padding",
    "align",
    "expand",
    "enabled"
})

ROW_PROPS = frozenset({
    "spacing",
    "padding",
    "align",
    "expand",
    "enabled"
})

SLIDER_PROPS = frozenset({
    "value",
    "min_value",
    "max_value",
    "step",
    "orientation",
    "enabled",
    "on_change",
})

SPACER_PROPS = frozenset()

DIVIDER_PROPS = frozenset({
    "orientation",
    "thickness",
    "color"
})

IMAGE_PROPS = frozenset({
    "source",
    "fit",
    "width",
    "height",
    "alt",
    "enabled"
})
