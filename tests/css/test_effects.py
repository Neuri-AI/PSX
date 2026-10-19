from psx.css.cascade import StyleTarget, resolve_style
from psx.css.effects import StyleEffect, classify_style_change
from psx.css.parser import parse_stylesheet


def computed(css: str):
    return resolve_style(parse_stylesheet(css), StyleTarget("div"))


def test_color_change_does_not_require_layout():
    before = computed("div { color: #000; background-color: #fff }")
    after = computed("div { color: #f00; background-color: #fff }")
    assert classify_style_change(before, after) == StyleEffect.PAINT


def test_font_changes_require_new_measurement_and_geometry():
    before = computed("div { font-size: 16px }")
    after = computed("div { font-size: 22px }")
    effect = classify_style_change(before, after)
    assert effect & StyleEffect.MEASUREMENT
    assert effect & StyleEffect.GEOMETRY


def test_width_changes_require_geometry():
    assert classify_style_change(computed("div { width: 10px }"), computed("div { width: 20px }")) == StyleEffect.GEOMETRY


def test_identical_computed_styles_are_noop():
    before = computed("div { color: #fff }")
    after = computed("div { color: #fff }")
    assert classify_style_change(before, after) == StyleEffect.NONE
