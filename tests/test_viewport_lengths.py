"""Viewport CSS lengths are typed and resolved at Cinnamon's layout boundary."""
import pytest

from psx.css.parser import parse_stylesheet
from psx.sfle.lengths import (
    Length, LengthKind, _parse_normalized_length, parse_length, resolve_viewport_length,
)
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import Flex, Text


@pytest.mark.parametrize("source,kind,fraction", [
    ("100vw", LengthKind.VW, 1.0),
    ("100vh", LengthKind.VH, 1.0),
    ("50vmin", LengthKind.VMIN, 0.5),
    ("25vmax", LengthKind.VMAX, 0.25),
])
def test_viewport_lengths_keep_typed_fraction(source, kind, fraction):
    assert parse_length(source) == Length(kind, fraction)


def test_length_cache_reuses_immutable_literals_but_not_resolved_geometry():
    _parse_normalized_length.cache_clear()
    first = parse_length(" 50VW ")
    second = parse_length("50vw")
    assert first is second
    assert _parse_normalized_length.cache_info().hits >= 1
    assert resolve_viewport_length(first, 800, 600) == Length.px(400)
    assert resolve_viewport_length(second, 1200, 600) == Length.px(600)
    numeric = Length.px(42)
    assert parse_length(numeric) is numeric
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        parse_length("UNSUPPORTED")
    assert _parse_normalized_length.cache_info().maxsize == 2048


def test_viewport_dimensions_resolve_against_window_not_parent():
    assert resolve_viewport_length(parse_length("50vw"), 1000, 600) == Length.px(500)
    assert resolve_viewport_length(parse_length("50vh"), 1000, 600) == Length.px(300)
    assert resolve_viewport_length(parse_length("100vmin"), 1000, 600) == Length.px(600)
    assert resolve_viewport_length(parse_length("100vmax"), 1000, 600) == Length.px(1000)


def test_stylesheet_accepts_viewport_geometry():
    styles = parse_stylesheet(".layout { width: 100vw; min-height: 100vh; margin-left: 2vmin; }")
    props = dict(styles.rules[0].declarations)
    assert props["width"] == parse_length("100vw")
    assert props["min-height"] == parse_length("100vh")
    assert props["margin-left"] == parse_length("2vmin")


def test_snapshot_resolves_nested_viewport_dimensions_without_parent_propagation():
    root = Flex(Text("hello", layout_width="25vw", layout_height="50vh"),
                width="100vw", height="100vh")
    normalized = normalize_flex_tree(root)
    prepared = prepare_native_layout_snapshot(normalized,
        LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True)),
        generation=1)
    snapshot = prepared.canonical_snapshot()
    nodes = {x.node_id: dict(x.style) for x in snapshot.nodes}
    assert any(v.get("width") == Length.px(800) for v in nodes.values())
    assert any(v.get("height") == Length.px(600) for v in nodes.values())
    assert any(v.get("layout_width") == Length.px(200) for v in nodes.values())
    assert any(v.get("layout_height") == Length.px(300) for v in nodes.values())


def test_viewport_units_recompute_after_window_resize():
    root = Flex(Text("hello", layout_width="50vw"))
    normalized = normalize_flex_tree(root)
    widths = []
    for w in (800, 1200):
        prepared = prepare_native_layout_snapshot(normalized,
            LayoutConstraints(AvailableSize(w, True), AvailableSize(600, True)),
            generation=1)
        style = [dict(node.style) for node in prepared.canonical_snapshot().nodes]
        widths.append(next(x["layout_width"] for x in style if "layout_width" in x))
    assert widths == [Length.px(400), Length.px(600)]


@pytest.mark.parametrize("source", ["1vwgarbage", "nanvh", "calc(50vw)", "infvmin"])
def test_invalid_viewport_values_fail_closed(source):
    with pytest.raises(ValueError):
        parse_length(source)


def test_viewport_projection_reuses_nodes_without_units_and_keeps_sources_immutable():
    root = Flex(Text("static", layout_width="24px"),
                Text("dynamic", layout_width="50vw"))
    normalized = normalize_flex_tree(root)
    constraints = LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True))
    prepared = prepare_native_layout_snapshot(normalized, constraints, generation=1)
    original = prepared.snapshot
    projected = prepared._resolve_viewport_units(original)
    assert projected is not original
    assert projected.nodes[0] is original.nodes[0]
    static_id = next(i for i, node in enumerate(original.nodes)
                     if dict(node.style).get("layout_width") == "24px")
    assert projected.nodes[static_id] is original.nodes[static_id]
    assert any(dict(node.style).get("layout_width") == Length.px(400)
               for node in projected.nodes)
    assert any(dict(node.style).get("layout_width") == "50vw"
               for node in original.nodes)
    plain = prepare_native_layout_snapshot(
        normalize_flex_tree(Flex(Text("static"))), constraints, generation=1,
    )
    assert plain._resolve_viewport_units(plain.snapshot) is plain.snapshot


def test_nested_flow_uses_window_viewport_instead_of_local_grid_constraints():
    # GridItem composition has an allocated width but an intrinsically measured height.
    # Neither constraint is the reference for viewport-relative CSS lengths.
    root = Flex(Text("hello", layout_width="25vw", layout_height="50vh"))
    normalized = normalize_flex_tree(root)
    local = LayoutConstraints(AvailableSize(200, True), AvailableSize(None, False))
    window = LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True))
    prepared = prepare_native_layout_snapshot(
        normalized, local, generation=1, viewport_constraints=window,
    )
    resolved = [dict(node.style) for node in prepared.canonical_snapshot().nodes]
    leaf = next(style for style in resolved if "layout_height" in style)
    assert leaf["layout_width"] == Length.px(200)
    assert leaf["layout_height"] == Length.px(300)
    assert prepared.snapshot.constraints == local


def test_nested_flow_viewport_lengths_recalculate_on_window_resize():
    root = Flex(Text("hello", layout_height="100vh", layout_width="10vw"))
    normalized = normalize_flex_tree(root)
    local = LayoutConstraints(AvailableSize(250, True), AvailableSize(None, False))
    results = []
    for width, height in ((800, 600), (1200, 900)):
        window = LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))
        prepared = prepare_native_layout_snapshot(
            normalized, local, generation=1, viewport_constraints=window,
        )
        leaf = next(dict(node.style) for node in prepared.canonical_snapshot().nodes
                    if "layout_height" in dict(node.style))
        results.append((leaf["layout_width"], leaf["layout_height"]))
    assert results == [
        (Length.px(80), Length.px(600)),
        (Length.px(120), Length.px(900)),
    ]


def test_scroll_viewport_height_uses_cinnamon_instead_of_native_fixed_pixels():
    from psx import Scroll
    scroll = Scroll(Flex(Text("Scrollable")), height="100vh", width="50vw")
    assert scroll.props["height"] is None
    assert scroll.props["width"] is None
    assert scroll.props["layout_height"] == "100vh"
    assert scroll.props["layout_width"] == "50vw"
    sizes = []
    for w, h in ((800, 600), (1200, 900)):
        normalized = normalize_flex_tree(Flex(scroll))
        prepared = prepare_native_layout_snapshot(
            normalized,
            LayoutConstraints(AvailableSize(w, True), AvailableSize(h, True)),
            generation=1,
        )
        styles = [dict(node.style) for node in prepared.canonical_snapshot().nodes]
        own = next(style for style in styles if "layout_height" in style)
        sizes.append((own["layout_width"], own["layout_height"]))
    assert sizes == [
        (Length.px(400), Length.px(600)),
        (Length.px(600), Length.px(900)),
    ]


@pytest.mark.parametrize("invalid", ["calc(50vh)", "-10vh", "0vh", "garbage"])
def test_scroll_css_sizes_reject_invalid_lengths(invalid):
    from psx import Scroll
    from psx.core.errors import RendererCapabilityError
    with pytest.raises(RendererCapabilityError):
        Scroll(Flex(Text("x")), height=invalid)
