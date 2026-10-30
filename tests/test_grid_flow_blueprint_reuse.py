"""Immutable GridItem Flow preparation must be geometry-equivalent on resize."""
from __future__ import annotations

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.grid_native_composition import FlowBlueprintReuse
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
from psx.sfle.model import AvailableSize, LayoutConstraints


def _flow(markup):
    roots = normalize_flex_tree(psx(markup))._participating_roots()
    assert len(roots) == 1
    return roots[0]


def _measure(flow, width, generation, epoch=0, *, cache=None, pixel_scale=1.0):
    constraints = LayoutConstraints(
        AvailableSize(width, True), AvailableSize(None, False))
    viewport = LayoutConstraints(
        AvailableSize(width, True), AvailableSize(650, True))
    if cache is not None:
        return cache.prepare(
            flow, constraints, generation, viewport, epoch, pixel_scale=pixel_scale,
        )[1]
    return prepare_native_layout_snapshot(
        flow, constraints, generation=generation,
        viewport_constraints=viewport,
    ).css_geometry_snapshot(pixel_scale=pixel_scale)


def test_blueprint_reuse_matches_unoptimized_css_geometry_on_resize():
    flow = _flow(
        '<div style="display:flex; flex-direction:column; padding:12px">'
        '<span style="margin-left:3px">Alpha</span>'
        '<span>Beta</span>'
        '</div>'
    )
    cache = FlowBlueprintReuse()
    for generation, width in enumerate((480, 560, 700, 640), 1):
        assert _measure(flow, width, generation, cache=cache) == _measure(
            flow, width, generation,
        )
    assert len(cache._entries) == 1


def test_blueprint_reuse_respects_semantic_epoch_and_changed_content():
    cache = FlowBlueprintReuse()
    first = _flow('<div><span>Alpha</span></div>')
    second = _flow('<div><span>Beta</span></div>')
    assert _measure(first, 300, 1, cache=cache) == _measure(first, 300, 1)
    assert _measure(first, 480, 2, epoch=1, cache=cache) == _measure(
        first, 480, 2)
    assert _measure(second, 480, 3, epoch=1, cache=cache) == _measure(
        second, 480, 3)


def test_blueprint_does_not_reuse_viewport_relative_css_geometry():
    flow = _flow(
        '<div style="padding-left:10vw; min-height:5vh">'
        '<span>Viewport</span></div>'
    )
    cache = FlowBlueprintReuse()
    for generation, width in enumerate((480, 720), 1):
        assert _measure(flow, width, generation, cache=cache) == _measure(
            flow, width, generation,
        )
    assert not cache._entries


def test_blueprint_cache_is_bounded_to_avoid_retaining_unmounted_trees():
    cache = FlowBlueprintReuse(limit=2)
    for i in range(5):
        flow = _flow(f'<div><span>Item {i}</span></div>')
        assert _measure(flow, 480, i + 1, cache=cache) == _measure(flow, 480, i + 1)
        assert len(cache._entries) <= 2


def test_kivy_retina_nested_css_geometry_scales_and_cache_cannot_mix_densities():
    from psx.sfle.lengths import Length
    flow = _flow(
        '<div style="display:flex;flex-direction:column;gap:10px;padding:12px">'
        '<span style="margin-left:3px">Alpha</span>'
        '<span>Beta</span></div>'
    )
    cache = FlowBlueprintReuse()
    for factor in (1.0, 2.0, 1.5, 2.0):
        calculated = _measure(
            flow, 800, 1, cache=cache, pixel_scale=factor,
        )
        baseline = _measure(flow, 800, 1, pixel_scale=factor)
        assert calculated == baseline
        root = dict(calculated.nodes[0].style)
        assert root["layout_padding_top"] == Length.px(12 * factor)
        assert root["row_gap"] == Length.px(10 * factor)
    assert len(cache._entries) == 3
