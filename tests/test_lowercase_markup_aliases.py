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


def test_unsupported_generic_tags_do_not_silently_use_flex():
    with pytest.raises(MarkupSyntaxError, match="Unknown PSX tag"):
        psx("<div />")


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
