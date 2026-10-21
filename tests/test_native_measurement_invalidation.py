"""C5 semantic invalidation contract and generation-fence behavior."""
from __future__ import annotations

import pytest

from psx.sfle.native_measurement_invalidation import MeasurementInvalidations, REASONS


def test_native_invalidation_invalidation_taxonomy_is_explicit():
    assert REASONS == {"content", "font", "theme", "resource", "dpi", "viewport"}


def test_native_invalidation_duplicate_notifications_coalesce_and_acknowledge_only_latest():
    state = MeasurementInvalidations()
    assert not state.needs_commit()
    stale = state.request("font")
    latest = state.request("font")
    state.request("resource")
    assert state.pending == {"font", "resource"}
    assert not state.acknowledge(stale)
    assert state.needs_commit()
    assert state.acknowledge(state.epoch)
    assert not state.needs_commit()
    assert state.committed_epoch > latest


def test_native_invalidation_teardown_fences_queued_invalidation():
    state = MeasurementInvalidations()
    epoch = state.request("viewport")
    state.cancel()
    assert not state.is_current(epoch)
    assert not state.needs_commit()
    assert not state.acknowledge(epoch)


@pytest.mark.parametrize("reason", ("", "all", "input", "font-change", "window", "unknown"))
def test_native_invalidation_unknown_invalidation_kind_fails_closed(reason):
    state = MeasurementInvalidations()
    with pytest.raises(ValueError, match="Unsupported SFLE measurement invalidation"):
        state.request(reason)
    assert not state.needs_commit()


def test_every_supported_native_component_has_native_invalidation_invalidation_evidence():
    from psx.sfle.native_component_matrix import native_certification_matrix
    from psx.sfle.native_operation_contracts import native_operation_contracts
    native = [c for c in native_certification_matrix() if c.status == "native"]
    assert native
    assert all("invalidation" in c.operations_with_evidence for c in native)
    gaps = [
        (contract.backend, contract.component, contract.mechanism)
        for contract in native_operation_contracts()
        if contract.operation == "invalidation"
        and contract.applicability == "required"
        and contract.mechanism != "pytest_reference"
    ]
    assert not gaps, f"C5 per-component invalidation coverage gaps: {gaps}"


def test_native_invalidation_targeted_invalidation_coalesces_without_marking_global():
    state = MeasurementInvalidations()
    state.request("resource", widget_id=123)
    state.request("content", widget_id=123)
    assert state.dirty_widgets == {123}
    assert state.pending == {"resource", "content"}
    assert not state.invalidate_all
    stale = state.epoch
    state.request("dpi")
    assert state.invalidate_all
    assert not state.acknowledge(stale)
    assert state.acknowledge(state.epoch)
    assert not state.dirty_widgets
    assert not state.invalidate_all


def test_native_invalidation_dependency_closure_retains_flex_siblings():
    from psx.sfle.native_measurement_dependencies import plan_layout_dependents
    from psx.sfle.model import LayoutInput, LayoutNode, LayoutConstraints, AvailableSize, WritingDirection

    viewport = LayoutConstraints(AvailableSize(300, True), AvailableSize(200, True))
    nodes = (
        LayoutNode("root", None, "Flex", ()),
        LayoutNode("left", "root", "Flex", ()),
        LayoutNode("a", "left", "Text", ()),
        LayoutNode("b", "left", "Text", ()),
        LayoutNode("right", "root", "Flex", ()),
        LayoutNode("c", "right", "Text", ()),
    )
    request = LayoutInput(1, 1, WritingDirection.LTR, viewport, nodes, ())
    closure = plan_layout_dependents(request, frozenset({"a"}))
    assert closure.dirty == {"a"}
    assert closure.ancestors == {"left", "root"}
    assert {"a", "b", "left", "right", "root"} <= closure.layout_candidates
    assert "c" not in closure.layout_candidates
    with pytest.raises(ValueError, match="Unknown dirty"):
        plan_layout_dependents(request, frozenset({"missing"}))


def test_targeted_typography_remeasurement_reuses_unaffected_native_sibling():
    """Only the edited widget is measured; independent native metrics are cached."""
    from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
    from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes, MeasuredBox

    left, right = object(), object()
    constraints = LayoutConstraints(AvailableSize(300, True), AvailableSize(100, True))
    intrinsic = IntrinsicSizes(10, 10, 12, 12, 10, 12)
    cache = NativeIntrinsicCache()
    measurements = {"left": 0, "right": 0}

    def measure(label, generation):
        def run():
            measurements[label] += 1
            return MeasuredBox(label, intrinsic, constraints, generation)
        return run

    def pass_over(generation, *, dirty=frozenset()):
        round_ = cache.begin(dirty_widgets=dirty)
        for label, widget in (("left", left), ("right", right)):
            round_.read(widget=widget, props=("font-size", 18),
                        constraints=constraints, node_id=label,
                        generation=generation, measure=measure(label, generation))
        round_.publish()
        return round_

    pass_over(1)
    assert measurements == {"left": 1, "right": 1}
    repeated = pass_over(2)
    assert not repeated.measured
    assert measurements == {"left": 1, "right": 1}

    state = MeasurementInvalidations()
    state.request("font", widget_id=id(left))
    state.request("font", widget_id=id(left))
    assert state.dirty_widgets == {id(left)}
    target = pass_over(3, dirty=frozenset(state.dirty_widgets))
    assert target.measured == {id(left)}
    assert measurements == {"left": 2, "right": 1}
    assert state.acknowledge(state.epoch)
    assert not pass_over(4).measured
    assert measurements == {"left": 2, "right": 1}


def test_native_width_measurement_cache_reuses_independent_widths():
    """Width-dependent wrapping invalidation must not evict independent leaves."""
    from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache

    one, other = object(), object()
    cache = NativeIntrinsicCache()
    counts = {"one": 0, "other": 0}

    def measurement(key):
        counts[key] += 1
        return (40, 16)

    def round_trip(*, dirty=frozenset(), invalidate_all=False):
        round_ = cache.begin(dirty_widgets=dirty, invalidate_all=invalidate_all)
        for key, widget in (("one", one), ("other", other)):
            round_.read_width(widget=widget, props=("font", "sans"),
                              constraints=(300, 100), width=140,
                              measure=lambda key=key: measurement(key))
        round_.publish()
        return round_

    round_trip()
    assert counts == {"one": 1, "other": 1}
    assert not round_trip().measured_width
    selected = round_trip(dirty=frozenset({id(one)}))
    assert selected.measured_width == {(id(one), 140)}
    assert counts == {"one": 2, "other": 1}
    assert round_trip(invalidate_all=True).measured_width == {
        (id(one), 140), (id(other), 140)
    }


def test_redundant_native_invalidation_does_not_restart_commit_generation():
    """Exact repeated notifications are coalesced, but new scope is not lost."""
    state = MeasurementInvalidations()
    targeted = state.request("font", widget_id=101)
    for _ in range(100):
        assert state.request("font", widget_id=101) == targeted
    assert state.epoch == targeted
    second = state.request("font", widget_id=202)
    assert second > targeted
    assert state.dirty_widgets == {101, 202}
    global_epoch = state.request("font")
    assert global_epoch > second
    assert state.invalidate_all
    assert state.request("font", widget_id=303) == global_epoch
    assert state.request("font") == global_epoch
    assert state.acknowledge(global_epoch)
    assert not state.needs_commit()
    next_epoch = state.request("font", widget_id=101)
    assert next_epoch > global_epoch


def test_dependent_layout_plan_rejects_cycles_and_unknown_parents():
    from psx.sfle.native_measurement_dependencies import plan_layout_dependents
    from psx.sfle.model import LayoutInput, LayoutNode, LayoutConstraints, AvailableSize, WritingDirection

    constraints = LayoutConstraints(AvailableSize(300, True), AvailableSize(200, True))

    def snapshot(nodes):
        return LayoutInput(1, 1, WritingDirection.LTR, constraints, nodes, ())

    shared = snapshot((
        LayoutNode("root", None, "Flex", ()),
        LayoutNode("left", "root", "Text", ()),
        LayoutNode("right", "root", "Text", ()),
    ))
    plan = plan_layout_dependents(shared, frozenset({"left", "right"}))
    assert plan.ancestors == {"root"}
    assert plan.layout_candidates == {"root", "left", "right"}
    # LayoutInput correctly rejects malformed topology before execution;
    # exercise the dependency planner's own defensive guard in isolation.
    from types import SimpleNamespace
    cyclic = SimpleNamespace(nodes=(
        LayoutNode("a", "b", "Flex", ()),
        LayoutNode("b", "a", "Flex", ()),
    ))
    with pytest.raises(ValueError, match="Cyclic"):
        plan_layout_dependents(cyclic, frozenset({"a"}))
    missing = SimpleNamespace(nodes=(
        LayoutNode("a", "absent", "Flex", ()),
    ))
    with pytest.raises(ValueError, match="Missing layout parent"):
        plan_layout_dependents(missing, frozenset({"a"}))


def test_invalidation_soak_1000_cycles_bounds_cached_native_measurements():
    """Repeated updates must not grow cache ownership or remeasure siblings."""
    from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
    from psx.sfle.model import IntrinsicSizes, MeasuredBox, LayoutConstraints, AvailableSize

    constraints = LayoutConstraints(AvailableSize(300, True), AvailableSize(100, True))
    intrinsic = IntrinsicSizes(10, 10, 10, 10, 10, 10)
    widgets = [object() for _ in range(16)]
    cache = NativeIntrinsicCache()
    state = MeasurementInvalidations()
    calls = [0] * len(widgets)

    for generation in range(1, 1001):
        dirty_index = generation % len(widgets)
        state.request("font", widget_id=id(widgets[dirty_index]))
        round_ = cache.begin(dirty_widgets=frozenset(state.dirty_widgets))
        for index, widget in enumerate(widgets):
            def measure(index=index):
                calls[index] += 1
                return MeasuredBox(str(index), intrinsic, constraints, generation)
            round_.read(widget=widget, props=("font-size", 16),
                        constraints=constraints, node_id=str(index),
                        generation=generation, measure=measure)
        assert len(round_.measured) == (16 if generation == 1 else 1)
        round_.publish()
        assert len(cache.entries) == len(widgets)
        assert len(cache.last_measured) <= len(widgets)
        assert state.acknowledge(state.epoch)

    assert sum(calls) == 16 + 999
    cache.clear()
    assert not cache.entries
    assert not cache.last_measured
