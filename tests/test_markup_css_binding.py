"""Public opt-in CSS source binding for lowercase PSX Markup.

Geometry and paint effects are intentionally not yet applied to native toolkit
widgets. These tests certify attachment and computed style only.
"""
import pytest

from psx.markup.compile import compile_template, psx
from psx.css.visual_values import CssColor
from psx.sfle.lengths import Length


def test_css_classes_ids_and_inline_declarations_bind_to_markup():
    root = psx(
        '<div class="panel" id="main" style="width: 25px">'
        '<span class="title">Hello</span></div>',
        stylesheet="#main {width: 10px} .title {color: #fff}",
    )
    assert root.type == "div"
    assert root.props["display"] == "block"
    assert "class" not in root.props
    assert "id" not in root.props
    assert "style" not in root.props
    assert root.css_computed.properties["width"] == Length.px(25)
    assert root.children[0].css_computed.properties["color"] == CssColor("#fff")


def test_markup_styles_inherit_color_but_not_background():
    root = psx(
        '<div class="panel"><span>Text</span></div>',
        stylesheet=".panel {color: #aabbcc; background-color: #123}",
    )
    assert root.children[0].css_computed.properties["color"] == CssColor("#aabbcc")
    assert root.children[0].css_computed.properties["background-color"] == CssColor("#0000")


def test_css_opt_in_preserves_legacy_widget_props_and_keys():
    button = psx(
        '<button key="save" class="primary">Save</button>',
        stylesheet=".primary {background-color: #fff}",
    )
    assert button.type == "Button"
    assert button.key == "save"
    assert "class" not in button.props
    assert button.css_computed.properties["background-color"] == CssColor("#fff")


def test_legacy_pascalcase_tag_remains_unmodified():
    normal = psx('<Button label="Save" />')
    assert normal.css_source is None
    assert normal.css_computed is None


def test_m4b_lexical_template_style_binding():
    result = compile_template('<div class="panel">{text}</div>').render_lexical(
        {"text": lambda: "Hello"}, stylesheet=".panel {width: 45px}"
    )
    assert result.css_computed.properties["width"] == Length.px(45)


@pytest.mark.parametrize("source", [
    '<div class="panel" class_name="panel" />',
    '<div class="bad class!" />',
    '<div id="invalid id" />',
    '<div style="background-image: url(a.png)" />',
])
def test_invalid_style_attributes_fail_closed(source):
    with pytest.raises((TypeError, ValueError)):
        psx(source)
