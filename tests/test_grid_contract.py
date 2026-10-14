"""Behavioral contract tests for future native responsive Grid declarations."""
import pytest

from psx.core.errors import RendererCapabilityError
from psx.core.grid_contract import (
    GRID_BREAKPOINTS, normalize_grid_props, normalize_grid_item_props,
)


def test_grid_has_exactly_twelve_columns_and_default_gaps():
    assert dict(normalize_grid_props({})) == {
        "columns": 12, "gap": 0, "row_gap": 0, "column_gap": 0,
    }
    assert GRID_BREAKPOINTS == {
        "base": 0, "sm": 576, "md": 768, "lg": 992, "xl": 1200,
    }


def test_grid_item_defaults_to_distributive_auto_metadata():
    assert dict(normalize_grid_item_props({})) == {"span": "auto", "offset": 0}


def test_explicit_span_and_offset_are_accepted():
    assert dict(normalize_grid_item_props({"span": 8, "offset": 2})) == {
        "span": 8, "offset": 2,
    }


def test_responsive_maps_are_preserved_without_calculating_geometry():
    result = normalize_grid_item_props({
        "span": {"base": 12, "md": 8},
        "offset": {"base": 0, "md": 2},
    })
    assert dict(result["span"]) == {"base": 12, "md": 8}
    assert dict(result["offset"]) == {"base": 0, "md": 2}


@pytest.mark.parametrize("props", [
    {"columns": 11}, {"columns": True}, {"columns": 12.0},
    {"gap": -1}, {"gap": float("nan")}, {"gap": True},
    {"gap": "calc(2px)"}, {"unknown": 1},
])
def test_grid_rejects_invalid_properties(props):
    with pytest.raises(RendererCapabilityError):
        normalize_grid_props(props)


@pytest.mark.parametrize("props", [
    {"span": 0}, {"span": 13}, {"span": True},
    {"span": 1.5}, {"span": None}, {"offset": -1},
    {"offset": 12}, {"offset": False}, {"offset": 0.5},
    {"span": 12, "offset": 1}, {"unknown": 1},
    {"span": {"xxl": 4}}, {"span": {"md": 6}},
    {"offset": {"base": 0, "tablet": 1}},
    {"span": {}},
])
def test_grid_item_rejects_invalid_properties(props):
    with pytest.raises(RendererCapabilityError):
        normalize_grid_item_props(props)


def test_contract_normalization_does_not_mutate_caller_input():
    source = {"span": {"base": 12, "md": 6}}
    normalized = normalize_grid_item_props(source)
    assert source == {"span": {"base": 12, "md": 6}}
    with pytest.raises(TypeError):
        normalized["span"]["md"] = 4


def test_public_grid_builders_and_registry_resolve_to_equivalent_markup():
    from psx import Grid, GridItem, Text, psx
    from psx.core.registry import builtin_component_registry
    registry = builtin_component_registry()
    assert registry.contains("Grid") and registry.contains("GridItem")
    built = Grid(GridItem(Text("Hello"), span=6), gap=8)
    parsed = psx("""
        <Grid gap={8}>
            <GridItem span={6}><Text>Hello</Text></GridItem>
        </Grid>
    """)
    assert built == parsed
    assert built.props["columns"] == 12
    assert built.children[0].props["span"] == 6


def test_public_grid_validates_resolved_direct_children():
    from psx import Grid, GridItem, Text
    from psx.core.errors import InvalidChildError
    with pytest.raises(InvalidChildError, match="GridItem"):
        Grid(Text("invalid"))
    with pytest.raises(InvalidChildError, match="one component root"):
        GridItem()
    with pytest.raises(InvalidChildError, match="one component root"):
        GridItem(Text("a"), Text("b"))


def test_grid_item_supports_automatic_span_in_public_markup():
    from psx import psx
    node = psx("<Grid><GridItem><Text>Header</Text></GridItem></Grid>")
    assert node.type == "Grid"
    assert node.children[0].props["span"] == "auto"


def test_public_declarations_preserve_key_identity():
    from psx import Grid, GridItem, Text
    node = Grid(GridItem(Text("one"), key="one"), key="outer")
    assert node.key == "outer"
    assert node.children[0].key == "one"


def test_grid_contract_rejects_flex_metadata_at_all_entry_points():
    from psx import Grid, GridItem, Text
    from psx.core.registry import builtin_component_registry
    from psx.core.vnode import create_element
    registry = builtin_component_registry()
    for name, constructor, child in (
        ("Grid", Grid, GridItem(Text("content"))),
        ("GridItem", GridItem, Text("content")),
    ):
        contract = registry.resolve(name).contract
        assert contract is not None
        with pytest.raises(RendererCapabilityError):
            contract.validate({"flex_grow": 1})
        with pytest.raises(RendererCapabilityError):
            contract.validate_builder({"flex_grow": 1})
        with pytest.raises(RendererCapabilityError):
            constructor(child, flex_grow=1)
        with pytest.raises(RendererCapabilityError):
            create_element(name, child, flex_grow=1)


def test_grid_registry_is_isolated_and_contracts_are_explicit():
    from psx.core.registry import builtin_component_registry
    first = builtin_component_registry()
    second = builtin_component_registry()
    for name, policy, props in (
        ("Grid", "multiple", {"columns", "gap", "row_gap", "column_gap"}),
        ("GridItem", "single", {"span", "offset"}),
    ):
        contract = first.resolve(name).contract
        assert contract is not None
        assert contract.child_policy == policy
        assert contract.properties == props
        assert contract.events == frozenset()
        assert first.resolve(name) is not second.resolve(name)


@pytest.mark.parametrize("component", ("Grid", "GridItem"))
@pytest.mark.parametrize("scenario", (
    "builder", "markup", "direct_element", "registry", "invalid_property", "key_identity",
))
def test_public_grid_declaration_entry_points_are_executed(component, scenario, request):
    """Prove public entry points independently, not by borrowing property receipts."""
    from psx import Grid, GridItem, Text, psx
    from psx.core.registry import builtin_component_registry
    from psx.core.vnode import create_element
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature

    inner = Text("content")
    item = GridItem(inner)
    child = item if component == "Grid" else inner
    builder = Grid if component == "Grid" else GridItem
    markup = ("<Grid><GridItem><Text>content</Text></GridItem></Grid>"
              if component == "Grid" else "<GridItem><Text>content</Text></GridItem>")
    if scenario == "builder":
        result = builder(child)
        assert result.type == component and result.children == (child,)
    elif scenario == "markup":
        result = psx(markup)
        assert result.type == component and len(result.children) == 1
        assert result.children[0].type == ("GridItem" if component == "Grid" else "Text")
    elif scenario == "direct_element":
        result = create_element(component, child)
        assert result.type == component and result.children == (child,)
    elif scenario == "registry":
        registry = builtin_component_registry()
        definition = registry.resolve(component)
        assert definition.name == component
        assert definition.constructor is builder
        assert definition.contract is not None
        assert registry.clone().resolve(component) is definition
    elif scenario == "invalid_property":
        for construct in (lambda: builder(child, __invalid_grid_prop__=True),
                          lambda: create_element(component, child, __invalid_grid_prop__=True)):
            with pytest.raises(RendererCapabilityError):
                construct()
        with pytest.raises((RendererCapabilityError, ValueError, TypeError)):
            psx(markup.replace(f"<{component}>",
                               f"<{component} __invalid_grid_prop__={{True}}>"))
    elif scenario == "key_identity":
        keyed = builder(child, key="stable")
        assert keyed.key == "stable"
        assert builder(child, key="stable") == keyed
        assert builder(child, key="different").key != keyed.key
    else:
        raise AssertionError(scenario)
    assert_feature(request, Feature(component, CONTRACT, "public_api",
                                    "declaration", scenario, applicability="shared"), True)
