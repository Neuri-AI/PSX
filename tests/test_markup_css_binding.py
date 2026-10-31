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
    assert node.css_source.tag == "button"
    assert node.css_computed is None
    assert node.props["label"] == "Save"


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


@pytest.mark.parametrize("tag", ("h1", "h2", "h3", "h4", "h5", "h6", "p"))
def test_heading_and_paragraph_css_reaches_native_text_leaves(tag):
    root = styled(
        f'<{tag} class="title">Hello world</{tag}>',
        '.title {font-size: 25px; font-family: Arial; font-weight: 700;'
        ' line-height: 38px; text-align: right; color: #123456}',
    )
    assert root.type == tag
    assert root.children
    for leaf in root.children:
        assert leaf.type == "Text"
        assert leaf.css_computed is not None
        assert leaf.css_computed.properties["font-size"] == Length.px(25)
        assert leaf.css_computed.properties["line-height"] == Length.px(38)
        assert leaf.css_computed.properties["font-family"] == "Arial"
        assert leaf.css_computed.properties["font-weight"] == 700
        assert leaf.css_computed.properties["text-align"] == "right"
        assert leaf.css_computed.properties["color"] == CssColor("#123456")


@pytest.mark.parametrize("tag", ("h1", "h2", "h3", "h4", "h5", "h6", "p"))
def test_heading_and_paragraph_nested_span_inherits_css(tag):
    root = styled(
        f'<{tag} style="font-size: 26px; line-height: 36px"><span>Nested text</span></{tag}>',
        "",
    )
    span = root.children[0]
    assert span.type == "span"
    assert span.children
    for leaf in span.children:
        assert leaf.type == "Text"
        assert leaf.css_computed.properties["font-size"] == Length.px(26)
        assert leaf.css_computed.properties["line-height"] == Length.px(36)


def test_heading_default_font_stays_native_without_authored_css():
    root = psx("<h1>Title</h1>")
    assert root.children[0].props["font_size"] == 32
    assert root.children[0].props["bold"] is True
    assert root.children[0].css_computed is None or "font-size" not in root.children[0].css_computed.specified


def test_heading_explicit_css_overrides_native_heading_size():
    root = styled('<h1 style="font-size: 22px">Title</h1>', "")
    assert root.children[0].props["font_size"] == 32
    assert root.children[0].css_computed.properties["font-size"] == Length.px(22)
    assert "font-size" in root.children[0].css_computed.specified


@pytest.mark.parametrize("tag,expected", (
    ("Button", "Button"), ("button", "Button"),
    ("Input", "Input"), ("input", "Input"),
    ("TextArea", "TextArea"), ("textarea", "TextArea"),
    ("Checkbox", "Checkbox"), ("Radio", "Radio"), ("Select", "Select"),
))
def test_pascal_and_html_alias_foreground_css_share_the_same_cascade(tag, expected):
    import re
    from psx.css.context import scoped_css_resources
    markup = (
        f'<{tag} class="accent" style="color: #123456" ' + ('value="option" ' if tag == "Radio" else '') + '/>'
        if tag not in ("button",) else
        '<button class="accent" style="color: #123456">Go</button>'
    )
    with scoped_css_resources(["theme.css"], resolver=lambda _: ".accent {color: #abcdef}"):
        node = psx(markup)
    assert node.type == expected
    assert node.css_computed.properties["color"] == CssColor("#123456")
    assert "style" not in node.props
    assert "class" not in node.props


def test_pascal_and_html_buttons_share_type_selector():
    from psx.css.context import scoped_css_resources
    with scoped_css_resources(["theme.css"], resolver=lambda _: "button {color: #123456}"):
        pascal = psx('<Button label="Go" />')
        html = psx('<button>Go</button>')
    assert pascal.css_computed.properties["color"] == CssColor("#123456")
    assert html.css_computed.properties["color"] == CssColor("#123456")


def test_universal_selector_applies_to_pascal_and_html_like_controls():
    from psx.css.context import scoped_css_resources
    with scoped_css_resources(["theme.css"], resolver=lambda _: (
        "* { color: #aabbcc; font-family: Arial }"
        ".accent { color: #223344 }"
        "button { font-size: 22px }"
    )):
        tree = psx(
            '<div><Button label="Save" class="accent" />'
            '<button>Save</button><Text value="Title" />'
            '<Flex><Input value="Text" /></Flex></div>'
        )
    assert tree.css_computed.properties["color"] == CssColor("#aabbcc")
    pascal, html, text_node, flex = tree.children
    assert pascal.css_computed.properties["color"] == CssColor("#223344")
    assert html.css_computed.properties["font-size"] == Length.px(22)
    assert pascal.css_computed.properties["font-size"] == Length.px(22)
    assert text_node.css_computed.properties["font-family"] == "Arial"
    assert flex.css_computed.properties["color"] == CssColor("#aabbcc")
    assert flex.children[0].css_computed.properties["color"] == CssColor("#aabbcc")


def test_programmatic_builtin_vnodes_receive_global_type_selectors():
    from psx.css.markup import compute_markup_styles
    from psx.css.parser import parse_stylesheet
    from psx.core.vnode import Button, Flex, Text
    root = Flex(Button("Save"), Text("Label"))
    styled_root = compute_markup_styles(root, parse_stylesheet(
        "* { color: #123456 } button { font-size: 24px }"
    ))
    assert styled_root.css_computed.properties["color"] == CssColor("#123456")
    assert styled_root.children[0].css_computed.properties["font-size"] == Length.px(24)
    assert styled_root.children[1].css_computed.properties["color"] == CssColor("#123456")


def test_universal_selector_does_not_override_parent_class_for_implicit_text():
    from psx.css.context import scoped_css_resources
    with scoped_css_resources(["theme.css"], resolver=lambda _: (
        "* { color: #111111 } .accent { color: #aabbcc }"
    )):
        node = psx('<p class="accent">Inherited text</p>')
    assert node.css_computed.properties["color"] == CssColor("#aabbcc")
    assert node.children[0].css_computed.properties["color"] == CssColor("#aabbcc")


def test_css_universal_specificity_below_type_and_class():
    from psx.css.parser import parse_selector, parse_stylesheet
    from psx.css.cascade import StyleTarget, resolve_style
    assert parse_selector("*").specificity == (0, 0, 0)
    computed = resolve_style(
        parse_stylesheet(".accent {color: #aabbcc} button {color: #123456} * {color: #111111}"),
        StyleTarget("button", frozenset({"accent"})),
    )
    assert computed.properties["color"] == CssColor("#aabbcc")


def test_mixed_inline_paragraph_preserves_source_order_and_whitespace():
    paragraph = psx(
        '<p>Edit <span>src/App.tsx</span> and save to test HMR</p>'
    )
    assert paragraph.type == "p"
    assert [child.type for child in paragraph.children][:2] == ["Text", "span"]
    assert len([child for child in paragraph.children if child.type == "span"]) == 1
    span = paragraph.children[1]
    assert span.children[0].props["value"] == "src/App.tsx"
    def text_content(node):
        if node.type == "Text":
            return node.props["value"]
        return "".join(text_content(child) for child in node.children)
    assert text_content(paragraph) == "Edit src/App.tsx and save to test HMR"


def test_mixed_inline_span_keeps_css_inheritance_and_own_style():
    paragraph = styled(
        '<p style="color: #334455">Edit '
        '<span key="path" style="color: #ff0000">src/App.tsx</span>'
        ' and save to test HMR</p>', "",
    )
    span = next(child for child in paragraph.children if child.type == "span")
    assert span.key == "path"
    assert span.css_computed.properties["color"] == CssColor("#ff0000")
    assert all(child.css_computed.properties["color"] == CssColor("#ff0000")
               for child in span.children if child.type == "Text")
    assert paragraph.children[0].css_computed.properties["color"] == CssColor("#334455")
