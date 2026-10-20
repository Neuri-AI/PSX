"""Computed CSS box metadata projected into the existing Cinnamon schema."""
from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.css.geometry import css_layout_overrides
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet
from psx.sfle.lengths import Length
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot


def _prepared(markup: str, rules: str):
    root = psx(
        '<link rel="stylesheet" href="styles/style.css" />' + markup,
        scope={"__velto_css_resource_resolver__": lambda _: rules},
    )
    return prepare_native_layout_snapshot(
        normalize_flex_tree(root),
        LayoutConstraints(AvailableSize(400, True), AvailableSize(200, True)),
        generation=3,
    )


def test_css_geometry_to_cinnamon_is_typed_and_preserves_source():
    prepared = _prepared(
        '<div class="panel"><span class="label">Text</span></div>',
        ".panel {width: 70%; padding: 12px; margin-left: -4px; border-width: 2px}"
        ".label {height: 20px}",
    )
    original = prepared.snapshot
    result = prepared.css_geometry_snapshot()
    root = dict(result.nodes[0].style)
    child = dict(result.nodes[1].style)
    assert root["layout_width"] == Length.percent(.7)
    assert root["layout_padding_top"] == Length.px(12)
    assert root["layout_padding_right"] == Length.px(12)
    assert root["layout_margin_left"] == Length.px(-4)
    assert root["layout_border_bottom"] == Length.px(2)
    assert child["layout_height"] == Length.px(20)
    assert original is prepared.snapshot
    assert "layout_padding_top" not in dict(original.nodes[0].style)
    assert "layout_width" not in prepared.identities[0][1].props


def test_explicit_legacy_layout_width_wins_over_stylesheet():
    prepared = _prepared(
        '<div class="panel" layout_width="45px" />',
        ".panel {width: 80px; padding: 8px}",
    )
    result = dict(prepared.css_geometry_snapshot().nodes[0].style)
    assert result["layout_width"] == Length.px(45)
    assert result["layout_padding_right"] == Length.px(8)


def test_paint_only_declarations_do_not_change_cinnamon_style():
    computed = resolve_style(
        parse_stylesheet("div {color: #fff; background-color: #000}"),
        StyleTarget("div"),
    )
    assert css_layout_overrides(computed) == {}


def test_css_edge_specific_value_overrides_shorthand():
    computed = resolve_style(
        parse_stylesheet("div {padding: 10px; padding-left: 2px}"),
        StyleTarget("div"),
    )
    result = css_layout_overrides(computed)
    assert result["layout_padding_top"] == Length.px(10)
    assert result["layout_padding_left"] == Length.px(2)


def test_mounted_headless_applies_css_width_through_cinnamon():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine

    source = '<div class="panel" style="width: 140px; height: 60px"><span style="width: 45px; height: 15px">Text</span></div>'
    from psx import psx
    tree = psx(source)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(300, True), AvailableSize(100, True)
        ),
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(tree)
        assert mounted.handle.geometry.width == 140
        assert mounted.children[0].handle.geometry.width == 45
        assert mounted.children[0].handle.geometry.height == 15
        assert renderer.sfle_result.geometry_commit_error == 0
    finally:
        reconciler.unmount()



def test_explicit_zero_side_value_clears_padding_shorthand():
    computed = resolve_style(
        parse_stylesheet("div {padding: 10px; padding-left: 0px}"),
        StyleTarget("div"),
    )
    edges = css_layout_overrides(computed)
    assert edges["layout_padding_top"] == Length.px(10)
    assert edges["layout_padding_left"] == Length.px(0)


def test_explicit_css_dimension_keyword_is_preserved():
    computed = resolve_style(
        parse_stylesheet("div {width: auto; min-width: 0px}"),
        StyleTarget("div"),
    )
    projected = css_layout_overrides(computed)
    assert projected["layout_width"].kind.value == "auto"
    assert projected["layout_min_width"] == Length.px(0)
