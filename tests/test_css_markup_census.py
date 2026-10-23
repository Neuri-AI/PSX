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
    if tag == 'radio':
        return f'<radio value="a" {attributes} />'
    if tag in ('input', 'textarea', 'checkbox', 'select', 'radiogroup'):
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



def test_public_css_box_geometry_updates_native_headless_receipts(request):
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(200, True), AvailableSize(100, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(20, 20, 15, 15, 20, 15),
    )
    tree = Reconciler(renderer)
    try:
        first = tree.render(psx(
            '<div style="padding: 5px"><button key="same" '
            'style="width: 40px; height: 15px; margin-left: 3px; '
            'padding: 2px; border-width: 1px">Save</button></div>'
        ))
        boxes = dict(renderer.sfle_result.boxes)
        root_box = boxes[renderer.sfle_result.boxes[0][0]]
        assert_feature(
            request,
            Feature("div", CONTRACT, "interaction", "css_box_geometry",
                    "distinct_boxes", applicability="shared"),
            root_box.content.x == 5 and root_box.padding.x == 0
            and root_box.border.width == 200,
        )
        handle = first.children[0].handle
        before_x = handle.geometry.x
        second = tree.render(psx(
            '<div style="padding: 5px"><button key="same" '
            'style="width: 40px; height: 15px; margin-left: 8px; '
            'padding: 2px; border-width: 1px">Save</button></div>'
        ))
        assert_feature(
            request,
            Feature("button", CONTRACT, "interaction", "css_box_geometry",
                    "margin_update", applicability="shared"),
            second.children[0].handle is handle
            and handle.geometry.x == before_x + 5
            and handle.geometry.width == 46,
        )
    finally:
        tree.unmount()


def test_div_css_flex_public_formatting_receipts(request):
    from psx.css.markup import compute_markup_styles
    from psx.core.layout_tree import normalize_flex_tree
    from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
    from psx.sfle.model import AvailableSize, LayoutConstraints
    tree = psx("<div><p>First</p><p>Second</p></div>")
    flexed = compute_markup_styles(
        tree, "div { display: flex; gap: 10px; flex-direction: row; }")
    block = compute_markup_styles(tree, "div { display: block; }")
    constraints = LayoutConstraints(AvailableSize(400, True),
                                    AvailableSize(200, True))
    flex_input = prepare_native_layout_snapshot(
        normalize_flex_tree(flexed), constraints, generation=1).css_geometry_snapshot()
    block_input = prepare_native_layout_snapshot(
        normalize_flex_tree(block), constraints, generation=2).css_geometry_snapshot()
    props = dict(flex_input.nodes[0].style)
    assert_feature(
        request, Feature("div", CONTRACT, "interaction", "css_flex_formatting",
                         "typed_row_gap", applicability="shared"),
        flex_input.nodes[0].component == "Flex"
        and props["direction"] == "row"
        and props["column_gap"] == Length.px(10),
    )
    assert_feature(
        request, Feature("div", CONTRACT, "interaction", "css_flex_formatting",
                         "block_reflow", applicability="shared"),
        block_input.nodes[0].component == "div"
        and dict(block_input.nodes[0].style)["display"] == "block"
        and block_input.nodes[0].node_id == flex_input.nodes[0].node_id,
    )
