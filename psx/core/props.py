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
    "min",
    "max",
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

PROGRESSBAR_PROPS = frozenset({
    "value", "min", "max",
    "indeterminate", "orientation", "enabled",
})

RADIO_PROPS = frozenset({"value", "label", "enabled"})

RADIOGROUP_PROPS = frozenset({
    "value", "on_change", "orientation", "spacing", "padding", "enabled",
})
SELECT_PROPS = frozenset({"options", "value", "placeholder", "enabled", "on_change"})

SWITCH_PROPS = frozenset({"checked", "enabled", "label", "size", "color", "on_change"})

LINK_PROPS = frozenset({"href", "label", "on_click", "color", "underline", "enabled"})

SPINBOX_PROPS = frozenset({"value", "min", "max", "step", "decimals", "enabled", "on_change"})

SCROLL_PROPS = frozenset({
    "direction", "content_direction", "scrollbar", "width", "height",
    "spacing", "padding", "enabled",
})
