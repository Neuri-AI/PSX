"""Viewport CSS lengths are typed and resolved at Cinnamon's layout boundary."""
import pytest

from psx.css.parser import parse_stylesheet
from psx.sfle.lengths import Length, LengthKind, parse_length, resolve_viewport_length
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
