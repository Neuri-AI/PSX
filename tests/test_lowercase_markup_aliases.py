"""Regression coverage for portable lowercase PSX control aliases."""

import pytest

from psx.core.errors import MarkupSyntaxError
from psx.core.registry import builtin_component_registry
from psx.markup.html_aliases import markup_alias_definitions
from psx.markup.compile import psx


def test_lowercase_controls_preserve_native_types():
    button = psx("<button>Save</button>")
    field = psx('<input value="hello" />')
    text_area = psx('<textarea value="notes" />')
    image = psx('<img src="logo.png" />')
    assert (button.type, button.props["label"]) == ("Button", "Save")
    assert (field.type, field.props["value"]) == ("Input", "hello")
    assert (text_area.type, text_area.props["value"]) == ("TextArea", "notes")
    assert (image.type, image.props["source"]) == ("Image", "logo.png")


def test_lowercase_and_pascalcase_are_both_available():
    native_registry = builtin_component_registry()
    registry = markup_alias_definitions(native_registry.snapshot())
    for lower, legacy in (
        ("button", "Button"), ("input", "Input"),
        ("textarea", "TextArea"), ("img", "Image")
    ):
        assert registry[lower].constructor is registry[legacy].constructor if lower != "img" else registry[lower].constructor is not registry[legacy].constructor
        assert registry[lower].contract is registry[legacy].contract
        assert not native_registry.contains(lower)


def test_image_alias_rejects_missing_or_conflicting_sources():
    with pytest.raises(ValueError, match="requires src"):
        psx("<img />")
    with pytest.raises(ValueError, match="both src and source"):
        psx('<img src="a.png" source="b.png" />')


def test_div_preserves_an_independent_block_host():
    node = psx("<div><button>Save</button></div>")
    assert node.type == "div"
    assert node.props["display"] == "block"
    assert [child.type for child in node.children] == ["Button"]


def test_div_rejects_unported_display_and_styles():
    with pytest.raises(ValueError, match="native formatting-context"):
        psx('<div display="flex" />')
    with pytest.raises(ValueError, match="Unsupported div properties"):
        psx('<div background="red" />')


def test_lowercase_aliases_work_in_lexically_transformed_markup():
    from psx.markup.transform import transform_source

    source = """from psx import psx
def view():
    return psx('<button>Save</button>')
"""
    result = transform_source(source, filename="lowercase_lexical.py")
    namespace = {"__name__": "lowercase_fixture"}
    exec(compile(result.source, "lowercase_lexical.py", "exec"), namespace)
    assert "'button': lambda" not in result.source
    assert namespace["view"]().type == "Button"


def test_lowercase_aliases_work_in_expressive_markup_with_callbacks():
    from psx.markup.transform import transform_source

    source = """from psx import psx
def view(handler):
    return psx('<button on_click={() => handler()}>Save</button>')
"""
    result = transform_source(source, filename="lowercase_expressive.py")
    namespace = {"__name__": "lowercase_expressive_fixture"}
    exec(compile(result.source, "lowercase_expressive.py", "exec"), namespace)
    calls = []
    button = namespace["view"](lambda: calls.append("saved"))
    assert button.type == "Button"
    button.props["on_click"]()
    assert calls == ["saved"]


def test_aliases_remain_available_with_isolated_component_registry():
    registry = builtin_component_registry()
    node = psx('<button>Confirm</button>', registry=registry)
    assert (node.type, node.props["label"]) == ("Button", "Confirm")
    assert not registry.contains("button")


def test_custom_registry_cannot_override_builtin_html_alias_by_accident():
    from psx.core.vnode import Text
    registry = builtin_component_registry()
    registry.register("button", lambda *children, **props: Text("Custom"))
    node = psx('<button />', registry=registry)
    assert node.type == "Text"
    assert node.props["value"] == "Custom"


def test_div_does_not_alias_flex_in_lexical_transform():
    from psx.markup.transform import transform_source
    source = """from psx import psx
def view():
    return psx('<div><button>Continue</button></div>')
"""
    transformed = transform_source(source, filename="div_view.py")
    namespace = {"__name__": "block_view_fixture"}
    exec(compile(transformed.source, "div_view.py", "exec"), namespace)
    root = namespace["view"]()
    assert root.type == "div"
    assert root.children[0].type == "Button"


def test_div_native_mount_fails_closed_without_block_port():
    from psx.core.errors import RendererCapabilityError
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer

    with pytest.raises(RendererCapabilityError, match="Cinnamon block"):
        Reconciler(HeadlessRenderer()).render(psx("<div />"))


def test_div_keys_preserve_logical_identity_without_entering_native_props():
    keyed = psx('<div key="card" />')
    assert keyed.key == "card"
    assert "key" not in keyed.props
    assert keyed.type == "div"


def test_div_accepts_ref_without_mistaking_it_for_native_style():
    marker = object()
    from psx.markup.html_aliases import _html_div
    node = _html_div(ref=marker)
    assert node.props["ref"] is marker
    assert node.type == "div"


def test_div_rejects_invalid_key_before_renderer_dispatch():
    from psx.markup.html_aliases import _html_div
    with pytest.raises(TypeError, match="PSX keys"):
        _html_div(key=True)


def test_div_does_not_pollute_native_host_capability_registry():
    registry = builtin_component_registry()
    markup = markup_alias_definitions(registry.snapshot())
    assert "div" in markup
    assert not registry.contains("div")
    assert "display" in markup["div"].constructor().props


def test_div_normalizes_as_a_distinct_block_participant():
    from psx.core.layout_tree import normalize_flex_tree
    root = psx('<div key="page"><button>Continue</button></div>')
    normalized = normalize_flex_tree(root)
    assert normalized.type == "div"
    assert normalized.source.props["display"] == "block"
    assert normalized.children[0].type == "Button"
    assert normalized.children[0].path[-1] == ("index", 0)


def test_block_normalization_rejects_unsupported_direct_vnode_properties():
    from psx.core.layout_tree import normalize_flex_tree
    from psx.core.errors import RendererCapabilityError
    from psx.core.vnode import create_element
    with pytest.raises(RendererCapabilityError, match="Unsupported div layout"):
        normalize_flex_tree(create_element("div", display="block", opacity=0.5))
    with pytest.raises(RendererCapabilityError, match="Block or Inline flow"):
        normalize_flex_tree(create_element("div", display="flex"))


def test_measured_div_commits_actual_headless_block_rectangles():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    measured = []
    def measure(node):
        measured.append(node.type)
        height = 12 if node.type == "Button" else 30
        return IntrinsicSizes(10, 10, height, height, 10, height)

    constraints = LayoutConstraints(
        AvailableSize(240, True), AvailableSize(400, True),
    )
    renderer = HeadlessRenderer(
        sfle_constraints=constraints, measure_intrinsic=measure,
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(psx("<div><button>Save</button><button>Next</button></div>"))
        assert root.handle.geometry.width == 240
        assert root.handle.geometry.height == 400
        assert root.children[0].handle.geometry.y == 0
        assert root.children[1].handle.geometry.y == 12
        assert measured == ["Button", "Button"]
        assert renderer.sfle_result is not None
        assert [node_id for node_id, _ in renderer.sfle_result.boxes]
    finally:
        reconciler.unmount()
    assert renderer.sfle_result is None


def test_block_mount_does_not_assume_unmeasured_leaf_height():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.errors import SFLEError
    from psx.sfle.model import AvailableSize, LayoutConstraints

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(240, True), AvailableSize(400, True),
        ),
        measure_intrinsic=lambda node: None,
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        with pytest.raises(SFLEError, match="did not provide intrinsic"):
            reconciler.render(psx("<div><button>Save</button></div>"))
        assert renderer.sfle_result is None
    finally:
        reconciler.unmount()


def test_display_change_reflows_without_replacing_keyed_headless_handles():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    def measure(node):
        return IntrinsicSizes(30, 30, 12, 12, 30, 12, baseline=9)

    backend = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(240, True), AvailableSize(140, True)),
        measure_intrinsic=measure, engine=PythonLayoutEngine(),
    )
    tree = Reconciler(backend)
    try:
        block = tree.render(psx(
            '<div display="block"><button key="a">Alpha</button><button key="b">Beta</button></div>'
        ))
        container = block.handle
        left, right = (child.handle for child in block.children)
        generation = backend.sfle_result.generation
        assert (right.geometry.x, right.geometry.y) == (0, 12)
        inline = tree.render(psx(
            '<div display="inline"><button key="a">Alpha</button><button key="b">Beta</button></div>'
        ))
        assert inline.handle is container
        assert inline.children[0].handle is left
        assert inline.children[1].handle is right
        assert (right.geometry.x, right.geometry.y) == (30, 0)
        assert backend.sfle_result.generation > generation
        assert left.geometry.width == 30
    finally:
        tree.unmount()


def test_headless_cinnamon_commits_nested_block_and_inline_rectangles(request):
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(100, True), AvailableSize(100, True),
        ),
        measure_intrinsic=lambda node: IntrinsicSizes(
            60, 60, 12, 12, 60, 12, baseline=9,
        ),
    )
    reconciler = Reconciler(renderer)
    root = reconciler.render(psx(
        "<div><h1>Heading</h1><p><span>one two three</span></p></div>"
    ))
    assert root.handle.geometry.width == 100
    heading, paragraph = root.children
    assert heading.handle.geometry.y == 0
    assert paragraph.handle.geometry.y == heading.handle.geometry.height
    span = paragraph.children[0]
    assert span.handle.geometry.height > 12
    assert len(span.children) >= 3
    assert renderer.sfle_result.generation > 0
    from tests.certification.public_behavior_census import Feature, assert_feature
    assert_feature(
        request, Feature("div", "headless", "interaction", "semantic_flow",
                         "native_geometry", applicability="partial_native"),
        root.handle.geometry.width == 100
        and paragraph.handle.geometry.y == heading.handle.geometry.height
        and span.handle.geometry.height > 12,
    )
    reconciler.unmount()


@pytest.mark.parametrize(
    "tag",
    (
        "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "main", "header", "footer", "form", "label", "ul", "li",
    ),
)
def test_semantic_markup_carries_public_census_assertions(request, tag):
    from tests.certification.public_behavior_census import (
        CONTRACT, Feature, assert_feature,
    )
    node = psx(f'<{tag} key="section-key">Hello</{tag}>')
    expected_display = "inline" if tag == "span" else "block"
    assert_feature(
        request, Feature(tag, CONTRACT, "public_api", "markup",
                         "default_display", applicability="shared"),
        node.type == tag and node.props.get("display") == expected_display,
    )
    assert_feature(
        request, Feature(tag, CONTRACT, "public_api", "markup",
                         "key_identity", applicability="shared"),
        node.key == "section-key" and "key" not in node.props,
    )


def test_headless_display_change_reflows_without_replacing_keyed_handles(request):
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    from tests.certification.public_behavior_census import Feature, assert_feature

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(200, True), AvailableSize(100, True),
        ),
        measure_intrinsic=lambda node: IntrinsicSizes(
            60, 60, 12, 12, 60, 12, baseline=9,
        ),
    )
    reconciler = Reconciler(renderer)
    initial = reconciler.render(psx(
        '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
    ))
    first, second = (item.handle for item in initial.children)
    assert second.geometry.y == first.geometry.height
    updated = reconciler.render(psx(
        '<div display="inline"><button key="a">Alpha</button>'
        '<button key="b">Beta</button></div>'
    ))
    assert_feature(
        request, Feature("div", "headless", "interaction", "semantic_flow",
                         "display_reflow", applicability="partial_native"),
        updated.handle is initial.handle
        and updated.children[0].handle is first
        and updated.children[1].handle is second
        and first.geometry.x == 0
        and second.geometry.x == first.geometry.width
        and second.geometry.y == 0,
    )
    previous_generation = renderer.sfle_result.generation
    renderer.set_sfle_constraints(LayoutConstraints(
        AvailableSize(120, True), AvailableSize(100, True),
    ))
    resized = reconciler.render(psx(
        '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
    ))
    assert_feature(
        request, Feature("div", "headless", "interaction", "semantic_flow",
                         "viewport_reflow", applicability="partial_native"),
        resized.children[0].handle is first
        and resized.children[1].handle is second
        and first.geometry.width == 120 and second.geometry.width == 120
        and second.geometry.y == first.geometry.height
        and renderer.sfle_result.generation > previous_generation,
    )
    reconciler.unmount()


@pytest.mark.parametrize("tag", (
    "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "main", "header", "footer", "form", "label", "ul", "li",
))
def test_headless_semantic_flow_native_geometry_receipt(request, tag):
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    from tests.certification.public_behavior_census import Feature, assert_feature

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(200, True), AvailableSize(80, True),
        ),
        measure_intrinsic=lambda node: IntrinsicSizes(
            60, 60, 12, 12, 60, 12, baseline=9,
        ),
    )
    tree = Reconciler(renderer)
    try:
        root = tree.render(psx(f"<{tag}><button>Action</button></{tag}>"))
        child = root.children[0].handle.geometry
        assert_feature(
            request, Feature(tag, "headless", "interaction", "semantic_flow",
                             "native_geometry", applicability="partial_native"),
            root.handle.geometry.width == 200
            and child.x == 0 and child.y == 0
            and child.height == 12
            and (child.width == 60 if tag in ("span", "label")
                 else child.width == 120 if tag == "li"
                 else child.width == 200),
        )
    finally:
        tree.unmount()


@pytest.mark.parametrize("tag,display", [
    ("form", "block"), ("label", "inline"),
    ("ul", "block"), ("li", "block"),
])
def test_remaining_semantic_tags_are_native_flow_hosts(tag, display):
    from psx.markup.html_aliases import FORMATTING_TAGS
    from psx.core.layout_tree import normalize_flex_tree
    content = "A" if tag != "ul" else "<li>A</li>"
    node = psx(f"<{tag} key='stable'>{content}</{tag}>")
    assert node.type == tag and node.key == "stable"
    assert node.props["display"] == display
    assert tag in FORMATTING_TAGS
    assert not builtin_component_registry().contains(tag)
    normalized = normalize_flex_tree(node)
    assert normalized.type == tag


def test_list_item_includes_a_measured_bullet_and_text():
    root = psx("<ul><li>First item</li><li>Second item</li></ul>")
    assert root.type == "ul" and len(root.children) == 2
    first, second = root.children
    assert first.type == second.type == "li"
    for item in (first, second):
        marker_run = item.children[0]
        assert marker_run.type == "span"
        assert marker_run.props["display"] == "inline"
        assert marker_run.children[0].type == "Text"
        assert marker_run.children[0].props["value"] == "• "
    assert "First" in "".join(child.props["value"] for child in first.children[0].children)


def test_semantic_tags_do_not_silently_accept_unimplemented_browser_contracts():
    with pytest.raises(ValueError, match="Unsupported form properties"):
        psx('<form on_reset="reset"></form>')
    with pytest.raises(ValueError, match="Unsupported label properties"):
        psx('<label html_for="field">Name</label>')
    with pytest.raises(ValueError, match="Unsupported ul properties"):
        psx('<ul style="list-style: square"></ul>')
    with pytest.raises(ValueError, match="requires content"):
        psx("<li></li>")


def test_form_submit_dispatch_uses_existing_native_control_events(request):
    from psx.markup.html_aliases import _formatting_host
    from psx.core.vnode import Button, Input
    calls = []
    root = _formatting_host(
        "form",
        Button("Save", key="save", on_click=lambda: calls.append("button")),
        Input(value="draft", key="name", on_submit=lambda value: calls.append(value)),
        on_submit=lambda: calls.append("form"),
    )
    assert root.type == "form" and root.props["display"] == "block"
    assert "on_submit" not in root.props
    button, field = root.children
    assert button.key == "save" and field.key == "name"
    button.props["on_click"]()
    field.props["on_submit"]("draft")
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature
    assert_feature(
        request, Feature("form", CONTRACT, "event", "on_submit",
                         "handler_delegation", applicability="shared"),
        calls == ["button", "form", "draft", "form"],
    )


def test_form_submit_closure_is_replaced_on_render_and_is_fail_closed():
    from psx.markup.html_aliases import _formatting_host
    from psx.core.vnode import Button
    calls = []
    def view(tag):
        return _formatting_host("form", Button("Save", key="save"),
                                on_submit=lambda: calls.append(tag))
    first = view("old")
    updated = view("new")
    assert first.children[0].key == updated.children[0].key == "save"
    updated.children[0].props["on_click"]()
    assert calls == ["new"]
    with pytest.raises(TypeError, match="callable"):
        _formatting_host("form", on_submit="invalid")
