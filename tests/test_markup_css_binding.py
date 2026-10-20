"""Public opt-in CSS source binding for lowercase PSX Markup.

Geometry and paint effects are intentionally not yet applied to native toolkit
widgets. These tests certify attachment and computed style only.
"""
import pytest

from psx.core.errors import MarkupSyntaxError

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
    with pytest.raises((TypeError, ValueError, MarkupSyntaxError)):
        psx(source)


def test_dynamic_class_update_recomputes_style_without_changing_key():
    source = '<div key="panel" class={theme}>Hello</div>'
    css = '.dark {color: #fff} .light {color: #000}'
    first = psx(source, scope={"theme": "dark"}, stylesheet=css)
    second = psx(source, scope={"theme": "light"}, stylesheet=css)
    assert first.key == second.key == "panel"
    assert first.css_computed.properties["color"] == CssColor("#fff")
    assert second.css_computed.properties["color"] == CssColor("#000")


def test_expressive_lowering_keeps_inline_object_styles_and_sheet():
    from psx.markup.transform import transform_source
    source = (
        "from psx import psx\\n"
        "def view():\\n"
        '    return psx(\'ready && <div class="panel" style={{"width": "35px"}}>OK</div>\', stylesheet=".panel {width: 10px}")\\n'
    )
    converted = transform_source(source, filename="css_expressive.py")
    assert "_psx_expr_compute_styles" in converted.source
    namespace = {}
    exec(compile(converted.source, "css_expressive.py", "exec"), namespace)
    root = namespace["view"]()
    assert root.css_computed.properties["width"] == Length.px(35)


def test_stylesheet_is_scoped_to_render_tree():
    css = ".panel {color: #fff}"
    styled = psx('<div class="panel" />', stylesheet=css)
    plain = psx('<div />')
    assert styled.css_computed.properties["color"] == CssColor("#fff")
    assert plain.css_computed is None


def test_css_markup_reconciliation_reports_paint_only_class_changes():
    from psx.css.parser import parse_stylesheet
    from psx.css.tree import resolve_vnode_styles, compare_styled_trees
    from psx.css.effects import StyleEffect

    source = '<div key="same" class={theme}>Hello</div>'
    rules = ".dark {color: #fff} .light {color: #000}"
    first = psx(source, scope={"theme": "dark"}, stylesheet=rules)
    second = psx(source, scope={"theme": "light"}, stylesheet=rules)
    before = resolve_vnode_styles(first, parse_stylesheet(""))
    after = resolve_vnode_styles(second, parse_stylesheet(""))
    changes = compare_styled_trees(before, after)
    assert any(change.key == "same" and change.effect == StyleEffect.PAINT for change in changes)
    assert all(not change.added and not change.removed for change in changes)
    assert all(not change.effect & StyleEffect.GEOMETRY for change in changes)


def test_selector_tags_match_lowercase_markup_without_css_attributes():
    root = psx('<div><span>Text</span></div>', stylesheet="div {width: 100px} span {font-size: 20px}")
    assert root.css_computed.properties["width"] == Length.px(100)
    assert root.children[0].css_computed.properties["font-size"] == Length.px(20)


def test_css_styles_are_kept_out_of_native_component_properties():
    node = psx(
        '<button class="cta" style="font-size: 18px">Go</button>',
        stylesheet=".cta {background-color: #abc}",
    )
    assert "style" not in node.props
    assert "class" not in node.props
    assert node.props["font_size"] == 14
    assert node.css_computed.properties["font-size"] == Length.px(18)
