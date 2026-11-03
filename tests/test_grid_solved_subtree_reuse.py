"""End-to-end accepted native text-only GridItem solve reuse.

The optimization must remain layout-identical, generation-correct and
transactional on Qt, Tk and Kivy's shared geometry preparation path.
"""
from psx import Flex, Text, psx
from psx.core.layout_tree import normalize_flex_tree
from psx.layout.contracts.model import IntrinsicSizes
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.grid_flex_composition import prepare_composed_flex
from psx.layout.grid.grid_native_composition import (
    FlowBlueprintReuse, prepare_composed_flow,
)


def metrics():
    return IntrinsicSizes(20, 50, 16, 16, 50, 16)


def flex(node, width, gen, reuse, epoch=0, pixel_scale=1.0):
    observations = []
    def measure(node_id, child, allocated_width):
        observations.append((node_id, allocated_width))
        return metrics()
    result = prepare_composed_flex(
        node, content_width=width, generation=gen,
        current_generation=gen, measure_leaf=measure,
        measure_grid=lambda *args: None, is_ui_thread=lambda: True,
        engine=PythonLayoutEngine(), pixel_scale=pixel_scale,
        flow_reuse=reuse, invalidation_epoch=epoch,
    )
    return result, observations


def test_flex_cached_solve_is_identical_and_skips_all_native_text_reads():
    node = normalize_flex_tree(Flex(
        Text("Alpha"), Text("Beta"), direction="column", gap="8px",
    ))
    cache = FlowBlueprintReuse()
    cache.solved.begin(1, 0)
    before, native_reads = flex(node, 480, 1, cache)
    assert native_reads
    assert cache.solved.hits == 0
    # A failed or partial native commit cannot publish native geometry.
    cache.solved.begin(2, 0)
    not_accepted, native_reads = flex(node, 480, 2, cache)
    assert native_reads
    cache.solved.accept(2, 0)

    cache.solved.begin(3, 0)
    reused, native_reads = flex(node, 480, 3, cache)
    assert native_reads == []
    assert reused.result.generation == 3
    assert reused.prepared.snapshot.generation == 3
    assert reused.result.boxes == before.result.boxes
    assert cache.solved.hits == 1


def test_flex_resize_and_style_epoch_require_fresh_measurements():
    node = normalize_flex_tree(Flex(Text("Stable"), direction="column"))
    cache = FlowBlueprintReuse()
    cache.solved.begin(1, 0)
    flex(node, 300, 1, cache)
    cache.solved.accept(1, 0)

    cache.solved.begin(2, 0)
    _, changed_width_reads = flex(node, 450, 2, cache)
    assert changed_width_reads
    cache.solved.accept(2, 0)

    cache.solved.begin(3, 1)
    _, invalidated_reads = flex(node, 450, 3, cache, epoch=1)
    assert invalidated_reads


def test_flex_cache_never_crosses_retina_pixel_scales():
    node = normalize_flex_tree(Flex(Text("Retina"), direction="column"))
    cache = FlowBlueprintReuse()
    cache.solved.begin(1, 0)
    flex(node, 480, 1, cache, pixel_scale=1.0)
    cache.solved.accept(1, 0)
    cache.solved.begin(2, 0)
    _, observations = flex(node, 480, 2, cache, pixel_scale=2.0)
    assert observations


def test_interactive_control_is_never_deferred():
    from psx import Button
    node = normalize_flex_tree(Flex(Text("Static"), Button("Click")))
    cache = FlowBlueprintReuse()
    cache.solved.begin(1, 0)
    first, reads = flex(node, 480, 1, cache)
    assert reads
    cache.solved.accept(1, 0)
    cache.solved.begin(2, 0)
    second, reads = flex(node, 480, 2, cache)
    assert reads
    assert first.result.boxes == second.result.boxes


def test_html_like_flow_reuses_certified_geometry_without_native_text_read():
    original = normalize_flex_tree(
        psx('<div><p>Alpha</p><p>Beta</p></div>')
    )._participating_roots()[0]
    cache = FlowBlueprintReuse()
    def layout(generation, width=400):
        reads = []
        def measure(ident, node, width):
            reads.append(ident)
            return metrics()
        result = prepare_composed_flow(
            original, width=width, generation=generation, measure_leaf=measure,
            engine=PythonLayoutEngine(), flow_reuse=cache, invalidation_epoch=0,
        )
        return result, reads

    cache.solved.begin(1, 0)
    before, reads = layout(1)
    assert reads
    cache.solved.accept(1, 0)
    cache.solved.begin(2, 0)
    after, reads = layout(2)
    assert reads == []
    assert after.result.generation == 2
    assert after.result.boxes == before.result.boxes
    cache.solved.begin(3, 0)
    _, reads = layout(3, width=480)
    assert reads


def test_solved_cache_reserves_width_sensitive_card_receipts():
    """Nine sampled resize widths x 500 cards must fit without LRU thrash."""
    from psx.layout.grid.grid_solved_reuse import SolvedTextSubtreeReuse

    cache = FlowBlueprintReuse()
    assert cache.limit == 4096, "Structural receipts need only one key per Flow"
    assert cache.solved.limit >= 500 * 9
    assert SolvedTextSubtreeReuse().limit >= 500 * 9

    # Simulate accepted (already validated) receipts at the realistic
    # 500-item / nine-width cardinality. The limit, not eviction order,
    # is the cause of the pathological 500-card benchmark cliff.
    solved = cache.solved
    solved.begin(1, 0)
    total = 500 * 9
    solved._pending = {
        (item, width): (None, None, 0, None)
        for item in range(500) for width in range(9)
    }
    solved.accept(1, 0)
    assert len(solved._entries) == total
    assert (0, 0) in solved._entries
    assert (499, 8) in solved._entries
