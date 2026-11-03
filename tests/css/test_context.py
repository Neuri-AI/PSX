"""App-scoped stylesheet declarations are isolated and ordered."""
from psx.css.context import current_css_context, scoped_css_resources
from psx.markup.compile import psx
from psx.css.visual_values import CssColor


def test_global_style_applied_without_widget_constructor_override():
    resolver = lambda name: ".panel {color: #fff}"
    with scoped_css_resources(["styles/app.css"], resolver=resolver):
        node = psx('<div class="panel" />')
    assert node.css_computed.properties["color"] == CssColor("#fff")
    assert current_css_context() is None


def test_stylesheet_links_override_global_sources():
    resources = {
        "global.css": ".panel {color: #000}",
        "pages/page.css": ".panel {color: #fff}",
    }
    with scoped_css_resources(["global.css"], resolver=resources.__getitem__):
        root = psx('<link rel="stylesheet" href="pages/page.css" /><div class="panel"/>')
    assert root.css_computed.properties["color"] == CssColor("#fff")


def test_nested_contexts_restore_previous_sources():
    with scoped_css_resources(["outer.css"], resolver=lambda _: "div {color: #fff}"):
        assert current_css_context().stylesheets == ("outer.css",)
        with scoped_css_resources(["inner.css"], resolver=lambda _: "div {color: #000}"):
            assert psx("<div />").css_computed.properties["color"] == CssColor("#000")
        assert psx("<div />").css_computed.properties["color"] == CssColor("#fff")
    assert current_css_context() is None
