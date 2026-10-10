from types import MappingProxyType

TEXT_DEFAULTS = MappingProxyType({
    "font_size": 16,
    "bold": False,
    "italic": False,
    "color": None,
    "align": "left",
    "enabled": True
})

BUTTON_DEFAULTS = MappingProxyType({
    "font_size": 14,
    "enabled": True,
    "on_click": None
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
CHECKBOX_DEFAULTS = MappingProxyType(
    {"checked": False, "enabled": True, "on_change": None})


TEXTAREA_DEFAULTS = MappingProxyType({
    "value": "",
    "placeholder": "",
    "font_size": 14,
    "enabled": True,
    "read_only": False,
    "on_change": None,
})
COLUMN_DEFAULTS = MappingProxyType({
    "spacing": 0,
    "padding": 0,
    "align": "stretch",
    "expand": False,
    "enabled": True,
})
ROW_DEFAULTS = MappingProxyType({
    "spacing": 0,
    "padding": 0,
    "align": "stretch",
    "expand": False,
    "enabled": True,
})

SLIDER_DEFAULTS = MappingProxyType({
    "value": 0.0,
    "min_value": 0.0,
    "max_value": 100.0,
    "step": 0.0,
    "orientation": "horizontal",
    "enabled": True,
    "on_change": None,
})

SPACER_DEFAULTS = MappingProxyType({})

DIVIDER_DEFAULTS = MappingProxyType({
    "orientation": "horizontal",
    "thickness": 1,
    "color": None,
})
