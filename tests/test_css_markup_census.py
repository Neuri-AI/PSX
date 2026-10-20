"""Assertion-bound public CSS markup source receipts, not native paint claims."""
import pytest

from psx.markup.compile import psx
from psx.markup.html_aliases import PORTABLE_HTML_ALIASES
from psx.css.visual_values import CssColor
from psx.sfle.lengths import Length
from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature


def _source(tag: str, attributes: str) -> str:
    if tag == 'img':
        return f'<img src="image.png" {attributes} />'
    if tag in ('input', 'textarea'):
        return f'<{tag} {attributes} />'
    return f'<{tag} {attributes}>Text</{tag}>'


def _styled(tag: str, attributes: str, css: str):
    return psx(
        '<link rel="stylesheet" href="styles/test.css" />' + _source(tag, attributes),
        scope={"__velto_css_resource_resolver__": lambda _: css},
    )


def _feature(tag: str, scenario: str) -> Feature:
    return Feature(tag, CONTRACT, "public_api", "css_source", scenario, applicability="shared")


@pytest.mark.parametrize("tag", sorted(PORTABLE_HTML_ALIASES))
def test_css_markup_class_selection(tag: str, request):
    node = _styled(tag, 'class="active"', ".active {color: #fff}")
    assert_feature(request, _feature(tag, "class_selection"),
                   node.css_computed.properties["color"] == CssColor("#fff")
                   and "class" not in node.props)


@pytest.mark.parametrize("tag", sorted(PORTABLE_HTML_ALIASES))
def test_css_markup_inline_precedence(tag: str, request):
    node = _styled(tag, 'class="active" style="width: 42px"',
                   ".active {width: 10px}")
    assert_feature(request, _feature(tag, "inline_precedence"),
                   node.css_computed.properties["width"] == Length.px(42)
                   and "style" not in node.props)


@pytest.mark.parametrize("tag", sorted(PORTABLE_HTML_ALIASES))
def test_css_markup_invalid_rejection(tag: str, request):
    try:
        psx(_source(tag, 'class="not!valid"'))
    except ValueError:
        rejected = True
    else:
        rejected = False
    assert_feature(request, _feature(tag, "invalid_rejection"), rejected)


def _link_feature(scenario: str) -> Feature:
    return Feature("link", CONTRACT, "public_api", "stylesheet_resource",
                   scenario, applicability="shared")


def test_link_source_public_behavior_receipt(request):
    root = psx('<link rel="stylesheet" href="styles/main.css" /><div class="panel" />',
               scope={"__velto_css_resource_resolver__": lambda _: ".panel {color: #fff}"})
    assert_feature(request, _link_feature("linked_source"),
                   root.css_computed.properties["color"] == CssColor("#fff"))


def test_link_relative_import_public_behavior_receipt(request):
    resources = {
        "styles/main.css": '@import "./buttons.css"; .panel {color: #fff}',
        "styles/buttons.css": ".panel {color: #abc}",
    }
    root = psx('<link rel="stylesheet" href="styles/main.css" /><div class="panel"/>',
               scope={"__velto_css_resource_resolver__": resources.__getitem__})
    assert_feature(request, _link_feature("relative_import"),
                   root.css_computed.properties["color"] == CssColor("#fff"))


def test_link_invalid_input_public_behavior_receipt(request):
    rejected = False
    try:
        psx('<link rel="preload" href="styles/main.css" /><div/>')
    except ValueError:
        rejected = True
    assert_feature(request, _link_feature("invalid_rejection"), rejected)


def test_link_creates_no_native_widget_public_behavior_receipt(request):
    root = psx('<link rel="stylesheet" href="styles/main.css" /><div />',
               scope={"__velto_css_resource_resolver__": lambda _: ""})
    assert_feature(request, _link_feature("no_native_widget"),
                   root.type == "div" and not root.children)
