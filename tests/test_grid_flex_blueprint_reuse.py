"""GridItem Flex blueprints reuse immutable structure, never solved geometry."""
from __future__ import annotations

from psx import Flex, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.grid_flex_composition import prepare_composed_flex
from psx.layout.grid.grid_native_composition import FlowBlueprintReuse
from psx.layout.contracts.model import IntrinsicSizes


def _compose(node, width, generation, cache=None, *, epoch=0, pixel_scale=1.0):
    reads = []

    def measure_leaf(identifier, leaf, allocated):
        reads.append((identifier, allocated))
        return IntrinsicSizes(20, 80, 12, 20, 80, 20)

    result = prepare_composed_flex(
        node, content_width=width, generation=generation,
        current_generation=generation, measure_leaf=measure_leaf,
        measure_grid=lambda _node, _width: None,
        is_ui_thread=lambda: True, engine=PythonLayoutEngine(),
        flow_reuse=cache, invalidation_epoch=epoch, pixel_scale=pixel_scale,
    )
    return result, reads


def test_cached_flex_blueprint_preserves_exact_solver_rectangles_on_resize():
    node = normalize_flex_tree(Flex(
        Text("Alpha"), Text("Beta"), direction="column", gap="8px",
    ))
    cache = FlowBlueprintReuse()
    for generation, width in enumerate((480, 560, 700, 480), 1):
        cached, actual_measurements = _compose(node, width, generation, cache)
        uncached, expected_measurements = _compose(node, width, generation)
        assert cached.result.boxes == uncached.result.boxes
        assert cached.content_height == uncached.content_height
        assert actual_measurements == expected_measurements
        assert actual_measurements, "Native intrinsic reads must remain fresh"
    assert len(cache._entries) == 1


def test_cached_flex_blueprint_invalidates_on_semantic_epoch():
    node = normalize_flex_tree(Flex(Text("First"), direction="column"))
    cache = FlowBlueprintReuse()
    _compose(node, 400, 1, cache, epoch=0)
    first = next(iter(cache._entries.values()))
    _compose(node, 400, 2, cache, epoch=1)
    second = next(iter(cache._entries.values()))
    assert second[2] == 1
    assert first[2] == 0


def test_cached_flex_blueprint_keeps_retina_scaling_of_css_geometry():
    node = normalize_flex_tree(Flex(
        Text("Retina"), direction="column", gap="8px",
        layout_padding_left="12px",
    ))
    cache = FlowBlueprintReuse()
    for gen, factor in enumerate((1.0, 2.0, 1.5, 2.0), 1):
        cached, _ = _compose(node, 500, gen, cache, pixel_scale=factor)
        expected, _ = _compose(node, 500, gen, pixel_scale=factor)
        assert cached.result.boxes == expected.result.boxes
    assert len(cache._entries) == 3


def test_flex_reuse_skips_second_structural_projection(monkeypatch):
    from psx.layout.grid import grid_native_composition
    original = grid_native_composition.prepare_native_layout_snapshot
    attempts = []

    def observed(*args, **kwargs):
        attempts.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        grid_native_composition, "prepare_native_layout_snapshot", observed,
    )
    node = normalize_flex_tree(Flex(Text("Stable"), direction="column"))
    cache = FlowBlueprintReuse()
    first, _ = _compose(node, 480, 1, cache)
    second, _ = _compose(node, 560, 2, cache)
    assert first.content_height == second.content_height
    assert len(attempts) == 1, "Reuse must skip a second full VNode projection"
