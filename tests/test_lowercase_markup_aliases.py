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
