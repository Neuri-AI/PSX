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
    from psx.sfle.model import IntrinsicSizes

    source = '<div class="panel" style="width: 140px; height: 60px"><button style="width: 45px; height: 15px">Text</button></div>'
    from psx import psx
    tree = psx(source)
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(300, True), AvailableSize(100, True)
        ),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(20, 20, 15, 15, 20, 15),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(tree)
        assert mounted.handle.geometry.width == 140
        assert mounted.children[0].handle.geometry.width == 45
        assert mounted.children[0].handle.geometry.height == 15
        assert dict(renderer.sfle_result.boxes)[renderer.sfle_result.boxes[0][0]].border.width == 140
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



def test_explicit_default_geometry_differs_from_implicit_default():
    absent = resolve_style(parse_stylesheet(""), StyleTarget("div"))
    explicit = resolve_style(parse_stylesheet("div {padding-left: 0px}"), StyleTarget("div"))
    assert absent != explicit
    assert css_layout_overrides(absent) == {}
    assert css_layout_overrides(explicit)["layout_padding_left"] == Length.px(0)



def test_mounted_headless_respects_css_margin_padding_border_geometry():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import IntrinsicSizes

    root = psx(
        '<div><button style="width: 40px; height: 15px; '
        'margin-left: 3px; margin-top: 4px; '
        'padding: 5px; border-width: 2px">Save</button></div>'
    )
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(220, True), AvailableSize(120, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(20, 20, 15, 15, 20, 15),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(root)
        box = mounted.children[0].handle.geometry
        assert (box.x, box.y, box.width, box.height) == (3, 4, 54, 29)
        assert dict(renderer.sfle_result.boxes)[renderer.sfle_result.boxes[1][0]].content.width == 40
    finally:
        reconciler.unmount()



def test_dynamic_css_geometry_updates_preserve_mounted_widget_identity():
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import IntrinsicSizes

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(230, True), AvailableSize(150, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda _: IntrinsicSizes(20, 20, 12, 12, 20, 12),
    )
    reconciler = Reconciler(renderer)
    try:
        first = reconciler.render(psx(
            '<div><button key="saved" style="width: 30px; margin-left: 2px">Save</button></div>'
        ))
        handle = first.children[0].handle
        assert (handle.geometry.x, handle.geometry.width) == (2, 30)
        second = reconciler.render(psx(
            '<div><button key="saved" style="width: 60px; margin-left: 9px">Save</button></div>'
        ))
        assert second.children[0].handle is handle
        assert (handle.geometry.x, handle.geometry.width) == (9, 60)
    finally:
        reconciler.unmount()


def test_css_viewport_lengths_reach_cinnamon_as_window_relative_px():
    prepared = _prepared(
        '<div class="layout"><span class="sidebar">Sidebar</span></div>',
        ".layout {width: 100vw; min-height: 100vh}"
        ".sidebar {height: 50vh; padding-left: 5vmin}",
    )
    original = prepared.snapshot
    resolved = prepared.css_geometry_snapshot()
    root, child = [dict(node.style) for node in resolved.nodes[:2]]
    assert root["layout_width"] == Length.px(400)
    assert root["layout_min_height"] == Length.px(200)
    assert child["layout_height"] == Length.px(100)
    assert child["layout_padding_left"] == Length.px(10)
    assert prepared.snapshot is original


def test_two_value_padding_reaches_cinnamon_geometry():
    prepared = _prepared(
        '<div class="sidebar">hola</div>',
        ".sidebar { padding: 20px 12px; height: 100vh }",
    )
    style = dict(prepared.css_geometry_snapshot().nodes[0].style)
    assert style["layout_padding_top"] == Length.px(20)
    assert style["layout_padding_right"] == Length.px(12)
    assert style["layout_padding_bottom"] == Length.px(20)
    assert style["layout_padding_left"] == Length.px(12)
