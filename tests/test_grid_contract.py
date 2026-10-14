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
    "invalid_children",
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
        from psx.core.errors import MarkupSyntaxError
        with pytest.raises((RendererCapabilityError, MarkupSyntaxError, ValueError, TypeError)):
            psx(markup.replace(f"<{component}>",
                               f"<{component} __invalid_grid_prop__={{True}}>"))
    elif scenario == "invalid_children":
        from psx.core.errors import InvalidChildError
        if component == "Grid":
            with pytest.raises(InvalidChildError):
                create_element(component, inner)
            with pytest.raises(InvalidChildError):
                builder(inner)
        else:
            with pytest.raises(InvalidChildError):
                create_element(component)
            with pytest.raises(InvalidChildError):
                create_element(component, inner, Text("extra"))
            with pytest.raises(InvalidChildError):
                builder()
    elif scenario == "key_identity":
        keyed = builder(child, key="stable")
        assert keyed.key == "stable"
        assert builder(child, key="stable") == keyed
        assert builder(child, key="different").key != keyed.key
    else:
        raise AssertionError(scenario)
    assert_feature(request, Feature(component, CONTRACT, "public_api",
                                    "declaration", scenario, applicability="shared"), True)


@pytest.mark.parametrize("gap", ("0px", ".5px", "2.px", " 4PX ", 2.5))
def test_grid_gap_uses_cinnamon_pixel_grammar(gap):
    from psx.sfle.lengths import LengthKind, parse_length
    normalized = normalize_grid_props({"gap": gap})
    assert parse_length(normalized["gap"]).kind is LengthKind.PX
    assert normalized["row_gap"] == gap
    assert normalized["column_gap"] == gap


@pytest.mark.parametrize("gap", ("-1px", "10%", "auto", "none", "calc(1px)", "1em",
                                  float("inf"), float("-inf"), True, None))
def test_grid_gap_rejects_unsupported_or_nonfinite_lengths(gap):
    if gap is None:
        # None is the documented inheritance sentinel only for row/column gaps.
        assert normalize_grid_props({"row_gap": None})["row_gap"] == 0
        with pytest.raises(RendererCapabilityError):
            normalize_grid_props({"gap": None})
    else:
        with pytest.raises(RendererCapabilityError):
            normalize_grid_props({"gap": gap})


@pytest.mark.parametrize("span,offset", (
    ({"base": 12, "md": 8}, {"base": 0, "md": 5}),
    ({"base": 8, "lg": 12}, {"base": 0, "md": 1}),
    (12, {"base": 0, "sm": 1}),
    ({"base": 12, "xl": 6}, 1),
    ({"base": 6, "md": 12}, {"base": 0, "sm": 1}),
))
def test_grid_item_rejects_overflow_at_every_inherited_breakpoint(span, offset):
    with pytest.raises(RendererCapabilityError, match="span \\+ offset"):
        normalize_grid_item_props({"span": span, "offset": offset})


def test_grid_item_accepts_independently_inherited_responsive_values():
    result = normalize_grid_item_props({
        "span": {"base": 12, "md": 8, "xl": 6},
        "offset": {"base": 0, "sm": 0, "lg": 3},
    })
    assert dict(result["span"]) == {"base": 12, "md": 8, "xl": 6}
    assert dict(result["offset"]) == {"base": 0, "sm": 0, "lg": 3}


@pytest.mark.parametrize("component,feature,scenario", (
    ("Grid", "gap_normalization", "canonical_pixel_grammar"),
    ("Grid", "gap_normalization", "axis_gap_inheritance"),
    ("Grid", "gap_normalization", "invalid_primary_gap"),
    ("GridItem", "span_offset", "breakpoint_inheritance"),
    ("GridItem", "span_offset", "responsive_overflow_rejection"),
    ("GridItem", "span_offset", "responsive_valid_combination"),
))
def test_grid_cross_property_contract_receipts(component, feature, scenario, request):
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature
    if scenario == "canonical_pixel_grammar":
        from psx.sfle.lengths import parse_length, LengthKind
        for value in ("0px", ".5px", " 4PX ", 2.5):
            assert parse_length(normalize_grid_props({"gap": value})["gap"]).kind is LengthKind.PX
    elif scenario == "axis_gap_inheritance":
        props = normalize_grid_props({"gap": 3, "row_gap": None, "column_gap": 5})
        assert props["row_gap"] == 3 and props["column_gap"] == 5
    elif scenario == "invalid_primary_gap":
        for value in (None, -1, "10%", "auto", float("nan"), True):
            with pytest.raises(RendererCapabilityError):
                normalize_grid_props({"gap": value})
    elif scenario == "breakpoint_inheritance":
        props = normalize_grid_item_props({
            "span": {"base": 8, "md": 6},
            "offset": {"base": 2, "lg": 3},
        })
        assert props["span"]["md"] == 6 and props["offset"]["lg"] == 3
    elif scenario == "responsive_overflow_rejection":
        for span, offset in (
            ({"base": 12, "md": 8}, {"base": 0, "md": 5}),
            (12, {"base": 0, "sm": 1}),
            ({"base": 6, "lg": 12}, {"base": 0, "md": 1}),
        ):
            with pytest.raises(RendererCapabilityError):
                normalize_grid_item_props({"span": span, "offset": offset})
    elif scenario == "responsive_valid_combination":
        props = normalize_grid_item_props({
            "span": {"base": 12, "md": 8, "xl": 6},
            "offset": {"base": 0, "lg": 3},
        })
        assert props["span"]["xl"] == 6 and props["offset"]["lg"] == 3
    assert_feature(request, Feature(component, CONTRACT, "interaction", feature,
                                    scenario, applicability="shared"), True)


@pytest.mark.parametrize("width,span,offset", (
    (0, 12, 0), (575, 12, 0), (576, 12, 0),
    (767, 12, 0), (768, 8, 0), (991, 8, 0),
    (992, 8, 2), (1199, 8, 2), (1200, 6, 2),
))
def test_grid_responsive_resolution_uses_inclusive_container_thresholds(width, span, offset):
    from psx.core.grid_contract import resolve_grid_item_props
    props = {"span": {"base": 12, "md": 8, "xl": 6},
             "offset": {"base": 0, "lg": 2}}
    assert dict(resolve_grid_item_props(props, width)) == {"span": span, "offset": offset}


def test_grid_custom_breakpoints_are_validated_and_resolved():
    from psx.core.grid_contract import resolve_grid_item_props, validate_grid_breakpoints
    custom = {"base": 0, "sm": 400, "md": 600, "lg": 900, "xl": 1100}
    validated = validate_grid_breakpoints(custom)
    assert dict(validated) == custom
    with pytest.raises(TypeError):
        validated["md"] = 700
    assert resolve_grid_item_props({"span": {"base": 12, "md": 6}}, 600,
                                   breakpoints=custom)["span"] == 6
    assert resolve_grid_item_props({"span": {"base": 12, "md": 6}}, 599,
                                   breakpoints=custom)["span"] == 12


@pytest.mark.parametrize("breakpoints", (
    {}, {"base": 0, "sm": 576, "md": 768, "lg": 992},
    {"base": 1, "sm": 576, "md": 768, "lg": 992, "xl": 1200},
    {"base": 0, "sm": 576, "md": 576, "lg": 992, "xl": 1200},
    {"base": 0, "sm": True, "md": 768, "lg": 992, "xl": 1200},
    {"base": 0, "sm": 576.0, "md": 768, "lg": 992, "xl": 1200},
))
def test_grid_rejects_invalid_breakpoint_tables(breakpoints):
    from psx.core.grid_contract import validate_grid_breakpoints
    with pytest.raises(RendererCapabilityError):
        validate_grid_breakpoints(breakpoints)


@pytest.mark.parametrize("width", (-1, True, None, float("nan"), float("inf"), "768"))
def test_grid_rejects_indefinite_or_invalid_container_width(width):
    from psx.core.grid_contract import resolve_grid_item_props
    with pytest.raises(RendererCapabilityError):
        resolve_grid_item_props({}, width)


@pytest.mark.parametrize("scenario", (
    "inclusive_threshold", "custom_thresholds", "inherited_values",
    "invalid_width", "invalid_thresholds",
))
def test_grid_responsive_resolution_receipts(scenario, request):
    from psx.core.grid_contract import resolve_grid_item_props, validate_grid_breakpoints
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature
    props = {"span": {"base": 12, "md": 6}, "offset": {"base": 0, "lg": 2}}
    if scenario == "inclusive_threshold":
        assert resolve_grid_item_props(props, 767)["span"] == 12
        assert resolve_grid_item_props(props, 768)["span"] == 6
    elif scenario == "custom_thresholds":
        thresholds = {"base": 0, "sm": 400, "md": 600, "lg": 900, "xl": 1100}
        assert resolve_grid_item_props(props, 600, breakpoints=thresholds)["span"] == 6
    elif scenario == "inherited_values":
        assert dict(resolve_grid_item_props(props, 1000)) == {"span": 6, "offset": 2}
    elif scenario == "invalid_width":
        with pytest.raises(RendererCapabilityError):
            resolve_grid_item_props(props, float("nan"))
    elif scenario == "invalid_thresholds":
        with pytest.raises(RendererCapabilityError):
            validate_grid_breakpoints({"base": 0})
    assert_feature(request, Feature("GridItem", CONTRACT, "interaction",
                                    "responsive_resolution", scenario,
                                    applicability="shared"), True)


@pytest.mark.parametrize("component", ("Grid", "GridItem"))
@pytest.mark.parametrize("sfle_enabled", (False, True))
def test_headless_rejects_unsupported_grid_mount_before_side_effects(component, sfle_enabled):
    from psx import Grid, GridItem, Text
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.model import LayoutConstraints, AvailableSize
    node = Grid(GridItem(Text("x"))) if component == "Grid" else GridItem(Text("x"))
    renderer = (HeadlessRenderer(sfle_constraints=LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True)))
                if sfle_enabled else HeadlessRenderer())
    with pytest.raises(RendererCapabilityError, match="requires a Cinnamon Grid layout backend"):
        renderer.create(node, None)
    assert renderer.operations == []


@pytest.mark.parametrize("component", ("Grid", "GridItem"))
def test_grid_unsupported_headless_mount_receipts(component, request):
    from psx import Grid, GridItem, Text
    from psx.renderers.headless import HeadlessRenderer
    from tests.certification.public_behavior_census import CONTRACT, Feature, assert_feature
    node = Grid(GridItem(Text("x"))) if component == "Grid" else GridItem(Text("x"))
    renderer = HeadlessRenderer()
    with pytest.raises(RendererCapabilityError, match="Grid layout backend"):
        renderer.create(node, None)
    assert not renderer.operations
    assert_feature(request, Feature(component, CONTRACT, "interaction",
                                    "unsupported_mount", "headless_fail_closed",
                                    applicability="shared"), True)
