"""Public PSX CSS source graph attachment and immutable style tests."""
import pytest

from psx.core.errors import MarkupSyntaxError
from psx.core.vnode import NodeKind
from psx.markup.compile import compile_template, psx
from psx.css.visual_values import CssColor
from psx.sfle.lengths import Length


def styled(markup: str, css: str, scope=None):
    bound = dict(scope or ())
    bound["__velto_css_resource_resolver__"] = lambda name: css
    tree = psx(
        '<link rel="stylesheet" href="styles/test.css" />' + markup,
        scope=bound,
    )
    return tree.children[0] if tree.kind is NodeKind.FRAGMENT and len(tree.children) == 1 else tree


def test_class_id_and_inline_precedence():
    root = styled(
        '<div class="panel" id="main" style="width: 25px"><span class="title">Hello</span></div>',
        "#main {width: 10px} .title {color: #fff}",
    )
    assert root.type == "div"
    assert "class" not in root.props
    assert "style" not in root.props
    assert root.css_computed.properties["width"] == Length.px(25)
    assert root.children[0].css_computed.properties["color"] == CssColor("#fff")


def test_inheritance_and_noninherited_background():
    root = styled(
        '<div class="panel"><span>Text</span></div>',
        ".panel {color: #aabbcc; background-color: #123}",
    )
    assert root.children[0].css_computed.properties["color"] == CssColor("#aabbcc")
    assert root.children[0].css_computed.properties["background-color"] == CssColor("#0000")


def test_native_alias_keeps_props_and_key():
    button = styled('<button key="save" class="primary">Save</button>',
                    ".primary {background-color: #fff}")
    assert button.type == "Button"
    assert button.key == "save"
    assert "class" not in button.props
    assert button.css_computed.properties["background-color"] == CssColor("#fff")


def test_legacy_pascalcase_tag_remains_unmodified():
    node = psx('<Button label="Save" />')
    assert node.css_source is None
    assert node.css_computed is None


def test_lexical_compiler_resolves_link_sources():
    template = compile_template('<link rel="stylesheet" href="styles/a.css" /><div class="panel">{text}</div>')
    result = template.render_lexical({
        "text": lambda: "Hello",
        "__velto_css_resource_resolver__": lambda _: ".panel {width: 45px}",
    })
    assert result.css_computed.properties["width"] == Length.px(45)


@pytest.mark.parametrize("source", (
    '<div class="panel" class_name="panel" />',
    '<div class="bad class!" />',
    '<div id="invalid id" />',
    '<div style="background-image: url(a.png)" />',
))
def test_invalid_style_attributes_fail_closed(source):
    with pytest.raises((TypeError, ValueError, MarkupSyntaxError)):
        psx(source)


def test_dynamic_class_updates_without_key_loss():
    source = '<div key="panel" class={theme}>Hello</div>'
    first = styled(source, ".dark {color: #fff} .light {color: #000}", {"theme": "dark"})
    second = styled(source, ".dark {color: #fff} .light {color: #000}", {"theme": "light"})
    assert first.key == second.key == "panel"
    assert first.css_computed.properties["color"] == CssColor("#fff")
    assert second.css_computed.properties["color"] == CssColor("#000")


def test_stylesheet_scope_isolated():
    first = styled('<div class="primary" />', ".primary {color: #fff}")
    second = styled('<div class="primary" />', ".primary {color: #000}")
    assert first.css_computed.properties["color"] == CssColor("#fff")
    assert second.css_computed.properties["color"] == CssColor("#000")


def test_css_markup_diff_reports_paint_only_change():
    from psx.css.parser import parse_stylesheet
    from psx.css.tree import resolve_vnode_styles, compare_styled_trees
    from psx.css.effects import StyleEffect
    source = '<div key="same" class={theme}>Hello</div>'
    rules = ".dark {color: #fff} .light {color: #000}"
    first = styled(source, rules, {"theme": "dark"})
    second = styled(source, rules, {"theme": "light"})
    before = resolve_vnode_styles(first, parse_stylesheet(""))
    after = resolve_vnode_styles(second, parse_stylesheet(""))
    changes = compare_styled_trees(before, after)
    assert any(change.key == "same" and change.effect == StyleEffect.PAINT for change in changes)
    assert all(not change.added and not change.removed for change in changes)


def test_type_selectors_work_without_class_or_id():
    root = styled('<div><span>Text</span></div>',
                  "div {width: 100px} span {font-size: 20px}")
    assert root.css_computed.properties["width"] == Length.px(100)
    assert root.children[0].css_computed.properties["font-size"] == Length.px(20)


def test_css_does_not_override_native_component_props():
    node = styled('<button class="cta" style="font-size: 18px">Go</button>',
                  ".cta {background-color: #abc}")
    assert node.props["font_size"] == 14
    assert node.css_computed.properties["font-size"] == Length.px(18)


def test_fragment_roots_receive_stylesheets():
    tree = styled('<><div class="one">One</div><span id="two">Two</span></>',
                  ".one {width: 80px} #two {color: #fff}")
    assert tree.children[0].css_computed.properties["width"] == Length.px(80)
    assert tree.children[1].css_computed.properties["color"] == CssColor("#fff")


def test_inline_mapping_and_class_name():
    node = styled('<div class_name="panel" style={style_map} />',
                  ".panel {width: 10px}", {"style_map": {"width": "73px"}})
    assert node.css_computed.properties["width"] == Length.px(73)


def test_unknown_stylesheet_property_fails_closed():
    from psx.css.parser import CssSyntaxError
    with pytest.raises(CssSyntaxError):
        styled('<div />', "div {grid-template-columns: 1fr}")


def test_link_is_not_a_widget():
    root = psx('<link rel="stylesheet" href="styles/main.css" /><div />',
               scope={"__velto_css_resource_resolver__": lambda _: ""})
    assert root.type == "div"


def test_removed_stylesheet_keyword_is_rejected():
    with pytest.raises(TypeError):
        psx('<div />', stylesheet="div {color:#fff}")


def test_expressive_markup_loads_link_without_native_widget(tmp_path, monkeypatch):
    from psx.markup.transform import transform_source
    (tmp_path / "style.css").write_text(".panel {color: #fff}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    program = (
        "from psx import psx\n"
        "def view():\n"
        "    return psx('<><link rel=\"stylesheet\" href=\"style.css\" />"
        "<div class=\"panel\" style={{\"width\": \"22px\"}}>Hello</div></>')\n"
    )
    transformed = transform_source(program, filename="expressive_styles.py")
    namespace = {}
    exec(compile(transformed.source, "expressive_styles.py", "exec"), namespace)
    node = namespace["view"]()
    assert len(node.children) == 1
    assert node.children[0].css_computed.properties["color"] == CssColor("#fff")
    assert node.children[0].css_computed.properties["width"] == Length.px(22)


def test_expressive_global_type_selector_without_css_attributes():
    from psx.css.context import scoped_css_resources
    from psx.markup.transform import transform_source
    program = (
        "from psx import psx\n"
        "def view():\n"
        "    ready = True\n"
        "    return psx('<div>{ready && <span>Hello</span>}</div>')\n"
    )
    transformed = transform_source(program, filename="type_selector.py")
    ns = {}
    exec(compile(transformed.source, "type_selector.py", "exec"), ns)
    with scoped_css_resources(["global.css"], resolver=lambda _: "div {color: #fff}"):
        root = ns["view"]()
    assert root.css_computed.properties["color"] == CssColor("#fff")
