from psx.css.cache import StyleResolver
from psx.css.cascade import StyleTarget
from psx.sfle.lengths import Length


def test_repeated_resolution_skips_reparse_and_cascade():
    resolver = StyleResolver()
    target = StyleTarget("div", frozenset({"a"}))
    first = resolver.resolve(".a { width: 10px }", target)
    assert first is resolver.resolve(".a { width: 10px }", target)
    assert (resolver.stats.parses, resolver.stats.computations, resolver.stats.hits) == (1, 1, 1)


def test_class_change_invalidates_correct_dependency():
    resolver = StyleResolver()
    source = ".a { width: 10px } .b { width: 30px }"
    a = resolver.resolve(source, StyleTarget("div", frozenset({"a"})))
    b = resolver.resolve(source, StyleTarget("div", frozenset({"b"})))
    assert a.properties["width"] == Length.px(10)
    assert b.properties["width"] == Length.px(30)
    assert resolver.stats.parses == 1


def test_cache_has_finite_bounded_residency_and_cleanup():
    resolver = StyleResolver(max_entries=2)
    for i in range(100):
        resolver.resolve(f"div {{ width: {i}px }}", StyleTarget("div"))
    assert resolver.stats.entries <= 4
    assert resolver.stats.evictions > 0
    resolver.clear()
    assert resolver.stats.entries == 0
