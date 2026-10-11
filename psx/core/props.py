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

# Metadata is not part of the native widget/property namespace.
FLEX_ITEM_PROPS = frozenset({
    "flex_grow", "flex_shrink", "flex_basis", "align_self", "order",
    "layout_width", "layout_height", "layout_min_width", "layout_min_height",
    "layout_max_width", "layout_max_height",
    *(f"layout_margin_{edge}" for edge in ("top", "right", "bottom", "left")),
    *(f"layout_padding_{edge}" for edge in ("top", "right", "bottom", "left")),
    *(f"layout_border_{edge}" for edge in ("top", "right", "bottom", "left")),
})

FLEX_PROPS = frozenset({
    "direction", "wrap", "justify_content", "align_items", "align_content",
    "gap", "row_gap", "column_gap", "width", "height", "min_width", "min_height",
    "max_width", "max_height", "padding", "flex_grow", "flex_shrink",
    "flex_basis", "align_self", "order", "layout_width", "layout_height",
    "layout_min_width", "layout_min_height", "layout_max_width", "layout_max_height",
}) | FLEX_ITEM_PROPS

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

BADGE_PROPS = frozenset({"label", "variant", "appearance", "size", "shape", "enabled"})

SPINBOX_PROPS = frozenset({"value", "min", "max", "step", "decimals", "enabled", "on_change"})

SCROLL_PROPS = frozenset({
    "direction", "content_direction", "scrollbar", "width", "height",
    "spacing", "padding", "enabled",
})
