"""C5: per-native-handle caching, dirty inputs and transactional publication."""
from __future__ import annotations

import pytest

from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox,
)


def test_native_measurements_skip_unaffected_widget_and_rebind_new_node_ids():
    cache = NativeIntrinsicCache()
    constraints = LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True))
    alpha, beta = object(), object()
    calls = []

    def measure(tag, node_id, generation):
        def call():
            calls.append(tag)
            return MeasuredBox(node_id, IntrinsicSizes(10, 20, 10, 15, 20, 15),
                               constraints, generation)
        return call

    def run(props_a, props_b, generation, invalidated=False):
        tx = cache.begin(invalidate_all=invalidated)
        a = tx.read(widget=alpha, props=props_a, constraints=constraints,
                    node_id="reassigned-a", generation=generation,
                    measure=measure("alpha", "reassigned-a", generation))
        b = tx.read(widget=beta, props=props_b, constraints=constraints,
                    node_id="reassigned-b", generation=generation,
                    measure=measure("beta", "reassigned-b", generation))
        tx.publish()
        assert a.revision == generation and b.revision == generation

    run({"label": "first"}, {"label": "same"}, 1)
    assert calls == ["alpha", "beta"]
    run({"label": "first"}, {"label": "same"}, 2)
    assert calls == ["alpha", "beta"]
    run({"label": "second"}, {"label": "same"}, 3)
    assert calls == ["alpha", "beta", "alpha"]
    assert cache.last_measured == {id(alpha)}
    run({"label": "second"}, {"label": "same"}, 4, invalidated=True)
    assert calls[-2:] == ["alpha", "beta"]
    cache.clear()
    assert not cache.entries and not cache.last_measured


def test_failed_native_measurement_transaction_never_publishes_partial_cache():
    cache = NativeIntrinsicCache()
    widget = object()
    constraints = LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True))
    tx = cache.begin()
    tx.read(widget=widget, props={"label": "ok"}, constraints=constraints,
            node_id="leaf", generation=1,
            measure=lambda: MeasuredBox("leaf", IntrinsicSizes(5, 5, 5, 5, 5, 5),
                                        constraints, 1))
    assert not cache.entries
    with pytest.raises(RuntimeError, match="host failed"):
        cache.begin().read(widget=widget, props={"label": "changed"},
                           constraints=constraints, node_id="leaf", generation=2,
                           measure=lambda: (_ for _ in ()).throw(RuntimeError("host failed")))
    assert not cache.entries


def test_native_invalidation_width_specific_measurements_cache_only_matching_width_and_props():
    cache = NativeIntrinsicCache()
    widget = object()
    viewport = LayoutConstraints(AvailableSize(160, True), AvailableSize(90, True))
    calls = []
    def roundtrip(props, width, invalidated=False):
        tx = cache.begin(invalidate_all=invalidated)
        value = tx.read_width(
            widget=widget, props=props, constraints=viewport, width=width,
            measure=lambda: (calls.append(width), (width, 24))[1],
        )
        tx.publish()
        return value
    assert roundtrip({"text": "same"}, 80) == (80, 24)
    assert roundtrip({"text": "same"}, 80) == (80, 24)
    assert calls == [80]
    assert roundtrip({"text": "same"}, 40) == (40, 24)
    assert calls == [80, 40]
    assert roundtrip({"text": "changed"}, 40) == (40, 24)
    assert calls == [80, 40, 40]
    assert roundtrip({"text": "changed"}, 40, invalidated=True) == (40, 24)
    assert calls == [80, 40, 40, 40]


def test_native_invalidation_targeted_resource_change_remeasures_only_its_widget():
    cache = NativeIntrinsicCache()
    constraints = LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True))
    alpha, beta = object(), object()
    calls = []

    def run(dirty=frozenset()):
        transaction = cache.begin(dirty_widgets=dirty)
        for label, widget in (("alpha", alpha), ("beta", beta)):
            transaction.read(
                widget=widget, props={"source": label}, constraints=constraints,
                node_id=label, generation=1,
                measure=lambda label=label: (
                    calls.append(label),
                    MeasuredBox(label, IntrinsicSizes(8, 8, 8, 8, 8, 8),
                                constraints, 1),
                )[1],
            )
        transaction.publish()

    run()
    assert calls == ["alpha", "beta"]
    run(dirty=frozenset((id(alpha),)))
    assert calls == ["alpha", "beta", "alpha"]
    assert cache.last_measured == {id(alpha)}


def test_cache_discards_obsolete_identity_and_width_entries_after_successful_round():
    """Churn may not accumulate past widgets or prior width samples."""
    import gc
    import weakref

    class Payload:
        pass

    cache = NativeIntrinsicCache()
    constraints = LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True))
    prior = None
    for index in range(128):
        payload = Payload()
        reference = weakref.ref(payload)
        tx = cache.begin()
        widget = object()
        tx.read(widget=widget, props={"payload": payload},
                constraints=constraints, node_id="current", generation=index + 1,
                measure=lambda: MeasuredBox(
                    "current", IntrinsicSizes(8, 8, 8, 8, 8, 8),
                    constraints, index + 1))
        tx.read_width(widget=widget, props={"payload": payload},
                      constraints=constraints, width=index + 1,
                      measure=lambda: (10, 20))
        tx.publish()
        assert len(cache.entries) == 1
        assert len(cache.width_entries) == 1
        if prior is not None:
            gc.collect()
            assert prior() is None
        prior = reference
        del tx, payload
    cache.clear()
    gc.collect()
    assert prior() is None
    assert not cache.entries and not cache.width_entries
    assert not cache.last_measured and not cache.last_width_measured


def test_failed_round_preserves_last_committed_cache_and_clear_drops_refs():
    import gc
    import weakref

    class Payload:
        pass

    cache = NativeIntrinsicCache()
    constraints = LayoutConstraints(AvailableSize(100, True), AvailableSize(100, True))
    payload = Payload()
    retained = weakref.ref(payload)
    widget = object()
    tx = cache.begin()
    tx.read(widget=widget, props={"owned": payload},
            constraints=constraints, node_id="leaf", generation=1,
            measure=lambda: MeasuredBox("leaf",
                IntrinsicSizes(4, 4, 4, 4, 4, 4), constraints, 1))
    tx.publish()
    del tx, payload
    with pytest.raises(ValueError, match="failed decode"):
        cache.begin(invalidate_all=True).read(
            widget=widget, props={}, constraints=constraints,
            node_id="leaf", generation=2,
            measure=lambda: (_ for _ in ()).throw(ValueError("failed decode")))
    assert retained() is not None
    cache.clear()
    gc.collect()
    assert retained() is None
