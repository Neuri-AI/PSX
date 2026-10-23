import pytest

from psx.css.catalog import css_capability_catalog
from psx.css.parser import CssSyntaxError, parse_stylesheet
from psx.css.properties import foundation_registry


def test_catalog_is_complete_for_internal_properties():
    catalog = css_capability_catalog()
    assert set(foundation_registry().properties).issubset(catalog)
    assert all(catalog[name].status == "parsed-internal" for name in foundation_registry().properties)


@pytest.mark.parametrize("name", [
    "background-image", "grid-template-columns",
    "overflow", "position", "transition", "box-sizing",
])
def test_planned_properties_are_visible_but_not_falsely_accepted(name):
    assert css_capability_catalog()[name].status == "planned-not-supported"
    with pytest.raises(CssSyntaxError):
        parse_stylesheet(f"div {{{name}: 10px}}")


def test_catalog_cannot_be_mutated():
    with pytest.raises(TypeError):
        css_capability_catalog()["new-property"] = "not allowed"


@pytest.mark.parametrize("name", [
    "display", "flex-direction", "flex-grow", "flex-shrink",
    "flex-basis", "justify-content", "align-items", "align-self",
])
def test_supported_flex_declarations_are_catalogued_as_active(name):
    assert css_capability_catalog()[name].status == "parsed-internal"
