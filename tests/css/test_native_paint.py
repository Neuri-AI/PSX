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


@pytest.mark.parametrize("weight", range(100, 1000, 100))
def test_native_text_accepts_standard_css_font_weights(weight):
    computed = _style(f"div {{font-weight: {weight}}}")
    assert native_text_typography(computed)["font-weight"] == weight


def test_native_radius_accepts_positive_px_and_zero():
    from psx.css.native_paint import native_border_radius
    assert native_border_radius(_style("div {border-radius: 12px}")) == 12
    assert native_border_radius(_style("div {border-radius: 0px}")) == 0
    assert native_border_radius(None) == 0


def test_native_radius_rejects_percentage_and_negative_values():
    from psx.css.native_paint import native_border_radius
    with pytest.raises(ValueError, match="nonnegative px"):
        native_border_radius(_style("div {border-radius: 15%}"))
    with pytest.raises(ValueError):
        native_border_radius(_style("div {border-radius: -3px}"))


def test_quoted_font_stack_projects_to_native_typography_and_qt_stylesheet():
    computed = _style("div {color: #333; font-family: 'Zapfino', cursive}")
    assert foreground_hex(computed) == "#333333"
    assert native_text_typography(computed)["font-family"] == "Zapfino"
    qss = qt_semantic_stylesheet(computed)
    assert 'color: #333333;' in qss
    assert 'font-family: "Zapfino", cursive;' in qss


def test_qt_paints_only_bottom_border_without_synthesizing_other_edges():
    computed = _style("div {border-bottom: 1px solid #e0e0e0}")
    rendered = qt_semantic_stylesheet(computed)
    assert "border-bottom: 1px solid #e0e0e0;" in rendered
    assert "border-top:" not in rendered
    assert "border: 1px solid" not in rendered

def test_native_side_stroke_preserves_authored_edges_and_rgba():
    from psx.css.native_paint import native_side_border_paint
    assert native_side_border_paint(None) == ()
    assert native_side_border_paint(_style("")) == ()
    only_bottom = _style("div { border-bottom: 2px solid #123456; }")
    assert native_side_border_paint(only_bottom) == (
        ("bottom", 2.0, (18 / 255, 52 / 255, 86 / 255, 1.0)),
    )
    colored = _style("div { border-left: 3px solid #f008; }")
    assert native_side_border_paint(colored) == (
        ("left", 3.0, (1.0, 0.0, 0.0, 136 / 255)),
    )
    assert native_side_border_paint(_style("div { border-bottom: none; }")) == ()


def test_native_side_stroke_updates_fallback_width_and_color_without_ghost_edges():
    from psx.css.native_paint import native_side_border_paint
    computed = _style(
        "div { border-width: 4px; border-color: #abcdef;"
        " border-bottom-color: #135790; border-top: none; }"
    )
    assert native_side_border_paint(computed) == (
        ("bottom", 4.0, (19 / 255, 87 / 255, 144 / 255, 1.0)),
    )


def test_rounded_css_side_paths_follow_half_corner_arcs_without_invented_sides():
    from psx.css.native_paint import rounded_side_stroke_points
    bottom = rounded_side_stroke_points("bottom", 160, 48, 12, 2)
    top = rounded_side_stroke_points("top", 160, 48, 12, 2)
    assert len(bottom) == len(top) == 36
    # At the tangent, a 2px line follows the inset border box.
    assert min(bottom[1::2]) >= 1 - 1e-8
    assert max(bottom[1::2]) < 12
    assert max(top[1::2]) <= 47
    assert min(top[1::2]) > 36
    assert bottom[0] > bottom[-2]  # right-to-left bottom path
    assert top[0] < top[-2]  # left-to-right top path
    assert rounded_side_stroke_points("bottom", 160, 48, 0, 2) == (
        0, 1, 160, 1,
    )


def test_rounded_css_side_paths_handle_small_boxes_and_invalid_values():
    from psx.css.native_paint import rounded_side_stroke_points
    assert rounded_side_stroke_points("left", 2, 40, 12, 2) == ()
    points = rounded_side_stroke_points("left", 40, 24, 100, 2)
    assert all(0 <= v <= (40 if i % 2 == 0 else 24)
               for i, v in enumerate(points))
    with pytest.raises(ValueError, match="Unknown CSS border side"):
        rounded_side_stroke_points("diagonal", 40, 24, 6, 2)
    with pytest.raises(ValueError, match="nonnegative"):
        rounded_side_stroke_points("top", 40, 24, 6, 0)
