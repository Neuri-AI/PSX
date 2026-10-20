"""Explicit CSS background paint conversion is native-backend independent."""
import pytest

from psx.css.native_paint import background_hex, background_rgba, foreground_hex, foreground_rgba, qt_semantic_stylesheet, border_rgba, native_text_typography
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet


def _style(css):
    return resolve_style(parse_stylesheet(css), StyleTarget("div"))


def test_background_only_applies_when_authored():
    assert background_rgba(_style("")) is None
    assert background_hex(_style("div {background-color: #123456}")) == "#123456"


def test_rgba_expansion_preserves_alpha_without_silent_loss():
    style = _style("div {background-color: #f008}")
    assert background_rgba(style) == (1.0, 0.0, 0.0, 136 / 255)
    with pytest.raises(ValueError, match="opaque"):
        background_hex(style)


def test_css_background_can_be_removed_without_inheriting_parent_background():
    parent = _style("div {background-color: #00ff00}")
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    assert background_hex(parent) == "#00ff00"
    assert background_hex(child) is None


def test_explicit_foreground_is_distinct_from_registry_default():
    assert foreground_hex(_style("")) is None
    assert foreground_hex(_style("div {color: #aBc}")) == "#aabbcc"


def test_authored_foreground_inherits_without_inheriting_background():
    parent = _style("div {color: #123456; background-color: #abcdef}")
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    grandchild = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=child)
    assert foreground_hex(child) == "#123456"
    assert foreground_hex(grandchild) == "#123456"
    assert background_hex(child) is None
    overridden = resolve_style(parse_stylesheet("span {color: #aabbcc}"), StyleTarget("span"), inherited=parent)
    assert foreground_hex(overridden) == "#aabbcc"


def test_implicit_foreground_never_becomes_explicit_through_inheritance():
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=_style(""))
    assert foreground_hex(child) is None


def test_translucent_foreground_preserves_alpha_and_fails_closed_for_hex():
    style = _style("div {color: #f008}")
    assert foreground_rgba(style) == (1.0, 0.0, 0.0, 136 / 255)
    with pytest.raises(ValueError, match="opaque"):
        foreground_hex(style)

def test_qt_semantic_paint_composes_background_foreground_and_radius():
    value = qt_semantic_stylesheet(_style(
        "div {background-color: #abc; color: #123456; border-radius: 6px}"
    ))
    assert value == "background-color: #aabbcc; color: #123456; border-radius: 6px;"


def test_qt_semantic_paint_resets_when_styles_are_removed():
    assert qt_semantic_stylesheet(_style("")) == ""
    assert qt_semantic_stylesheet(None) == ""


def test_qt_semantic_paint_rejects_unsupported_percentage_radius():
    with pytest.raises(ValueError, match="requires px"):
        qt_semantic_stylesheet(_style("div {border-radius: 25%}"))


def test_border_color_is_recognized_and_painted_with_width():
    computed = _style("div {border-width: 2px; border-color: #abc}")
    assert computed.properties["border-color"].value == "#abc"
    assert qt_semantic_stylesheet(computed) == "border: 2px solid #aabbcc;"


def test_border_color_alone_does_not_invent_nonzero_geometry():
    assert qt_semantic_stylesheet(_style("div {border-color: #123456}")) == ""


def test_border_paint_rejects_alpha_instead_of_silently_discarding_it():
    with pytest.raises(ValueError, match="opaque"):
        qt_semantic_stylesheet(_style("div {border-width: 1px; border-color: #abc8}"))


def test_qt_semantic_font_styles_are_composed():
    assert qt_semantic_stylesheet(_style(
        "div {font-family: Arial; font-size: 18px; font-weight: bold; text-align: center}"
    )) == 'font-family: "Arial"; font-size: 18px; font-weight: 700; text-align: center;'


def test_qt_semantic_typography_rejects_unresolved_percentages():
    with pytest.raises(ValueError, match="positive px"):
        qt_semantic_stylesheet(_style("div {font-size: 150%}"))


def test_qt_semantic_text_alignment_rejects_unsupported_justification():
    with pytest.raises(ValueError, match="justify"):
        qt_semantic_stylesheet(_style("div {text-align: justify}"))

def test_border_rgba_supports_native_kivy_transparency():
    assert border_rgba(_style("div {border-color: #f008}")) == (
        1.0, 0.0, 0.0, 136 / 255
    )
    assert border_rgba(_style("div {border-width: 3px}")) is None

def test_text_typography_projects_explicit_font_and_alignment():
    style = _style("div {color: #abc; font-family: Arial; font-size: 18px; font-weight: bold; text-align: center}")
    assert native_text_typography(style) == {
        "color": "#aabbcc", "font-family": "Arial", "font-size": 18.0,
        "font-weight": 700, "text-align": "center",
    }


def test_text_typography_inherits_explicit_styles_without_defaults():
    assert native_text_typography(_style("")) == {}
    parent = _style("div {font-size: 20px; color: #123456}")
    child = resolve_style(parse_stylesheet(""), StyleTarget("span"), inherited=parent)
    assert native_text_typography(child) == {"font-size": 20.0, "color": "#123456"}


def test_text_typography_rejects_uncertified_line_height():
    with pytest.raises(ValueError, match="line-height"):
        native_text_typography(_style("div {line-height: 30px}"))


def test_text_typography_keeps_kivy_alpha_channels():
    assert native_text_typography(_style("div {color: #f008}"), alpha=True) == {
        "color": (1.0, 0.0, 0.0, 136 / 255)
    }


def test_kivy_pixel_line_height_and_rejects_percentage_leading():
    assert native_text_typography(_style("div {line-height: 27px}"), line_height=True) == {"line-height": 27.0}
    with pytest.raises(ValueError, match="positive px"):
        native_text_typography(_style("div {line-height: 120%}"), line_height=True)
