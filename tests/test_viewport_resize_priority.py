"""Priority-driven resize deferral never invents geometry or survives staleness."""
from psx.layout.adapters.viewport_resize_priority import (
    ViewportPriority, ViewportResizeCoordinator, classify_viewport_priority,
)


def priority(**overrides):
    data = dict(certified=True, safe=True, old_top=800, old_bottom=850,
                new_top=900, new_bottom=950, viewport_top=0,
                viewport_height=300)
    data.update(overrides)
    return classify_viewport_priority(**data)


def test_p0_newly_visible_and_oldly_visible():
    assert priority(new_top=210, new_bottom=270) == ViewportPriority.VISIBLE
    assert priority(old_top=210, old_bottom=270) == ViewportPriority.VISIBLE


def test_p1_uncertain_intersecting_structural_and_crossing():
    assert priority(certified=False) == ViewportPriority.STRUCTURAL
    assert priority(safe=False) == ViewportPriority.STRUCTURAL
    assert priority(new_top=-700, new_bottom=-500) == ViewportPriority.STRUCTURAL
    assert priority(viewport_height=float("nan")) == ViewportPriority.STRUCTURAL


def test_p2_offscreen_below_and_above():
    assert priority() == ViewportPriority.DEFERRED
    assert priority(old_top=-900, old_bottom=-500,
                    new_top=-850, new_bottom=-450) == ViewportPriority.DEFERRED


def test_coalesced_generations_discard_obsolete_idle_work():
    coordinator = ViewportResizeCoordinator(batch_size=2)
    first = coordinator.resize((800, 600))
    assert first == coordinator.resize((800, 600))
    assert coordinator.resize((900, 600)) != first
    assert not coordinator.begin_settlement(first)
    current = coordinator.resize((1100, 600))
    assert coordinator.begin_settlement(current)
    assert coordinator.begin_batch(current)
    assert not coordinator.begin_batch(first)


def test_p2_bounded_batches_eventually_reconcile_without_repeating():
    coordinator = ViewportResizeCoordinator(batch_size=2)
    generation = coordinator.resize((800, 600))
    assert coordinator.begin_settlement(generation)
    workset = object()
    for count in (2, 2, 1):
        assert coordinator.begin_batch(generation)
        promoted = [i for i in range(5) if coordinator.promote(workset, str(i))]
        assert len(promoted) == count
        more = coordinator.finish_batch(success=True)
        assert more == (count != 1)
    assert not coordinator.settling


def test_failed_batch_never_accepts_and_next_resize_restarts():
    coordinator = ViewportResizeCoordinator(batch_size=1)
    workset = object()
    generation = coordinator.resize((800, 600))
    assert coordinator.begin_settlement(generation)
    # Promotion is transactional; outside an open batch nothing is accepted.
    assert not coordinator.promote(workset, "a")
    assert coordinator.begin_batch(generation)
    assert coordinator.promote(workset, "a")
    assert not coordinator.promote(workset, "b")
    assert not coordinator.finish_batch(success=False)
    assert not coordinator.promote(workset, "a")

    generation = coordinator.resize((900, 600))
    assert coordinator.begin_settlement(generation)
    assert coordinator.begin_batch(generation)
    # A failed batch cannot permanently suppress the group's next promotion.
    assert coordinator.promote(workset, "a")
    coordinator.cancel()
    assert not coordinator.begin_batch(generation)

def test_resize_burst_only_reconciles_latest_generation_in_bounded_batches():
    from types import SimpleNamespace
    from psx.layout.adapters.viewport_resize_priority import schedule_resize_settlement

    class Renderer:
        _psx_native_flow_deferred_ids = frozenset({"card"})
        _psx_native_grid_deferred_total = 0
        _sfle_in_commit = False
        _sfle_mounted_root = SimpleNamespace(disposed=False)

        def __init__(self):
            self.calls = 0
            self.promoted = []
            self.workset = object()

        def commit_layout(self, root):
            assert root is self._sfle_mounted_root
            self.calls += 1
            for index in range(5):
                if self._psx_resize_priority.promote(self.workset, str(index)):
                    self.promoted.append(index)

    renderer = Renderer()
    callbacks = []
    schedule = lambda milliseconds, callback: callbacks.append((milliseconds, callback))
    for width in (801, 802, 803, 804):
        schedule_resize_settlement(renderer, (width, 600), schedule)
    renderer._psx_resize_priority.batch_size = 2
    assert renderer.calls == 0
    assert len(callbacks) == 4

    # Three obsolete debounces have no side effects.
    for _ in range(3):
        milliseconds, callback = callbacks.pop(0)
        assert milliseconds == 125
        callback()
    assert renderer.calls == 0

    callbacks.pop(0)[1]()
    while callbacks:
        delay, callback = callbacks.pop(0)
        assert delay == 16
        callback()
    assert renderer.calls == 3
    assert renderer.promoted == [0, 1, 2, 3, 4]
    assert not renderer._psx_resize_priority.settling


def test_no_deferred_native_groups_means_no_settlement_commit():
    from types import SimpleNamespace
    from psx.layout.adapters.viewport_resize_priority import schedule_resize_settlement

    renderer = SimpleNamespace(
        _psx_native_flow_deferred_ids=frozenset(),
        _psx_native_grid_deferred_total=0,
    )
    callbacks = []
    schedule_resize_settlement(renderer, (900, 600), lambda ms, cb: callbacks.append(cb))
    assert not callbacks


def test_pending_settlement_must_not_commit_a_replaced_mounted_root():
    from types import SimpleNamespace
    from psx.layout.adapters.viewport_resize_priority import schedule_resize_settlement

    class Renderer:
        def __init__(self):
            self._sfle_mounted_root = SimpleNamespace(disposed=False)
            self._psx_native_flow_deferred_ids = frozenset({"deferred"})
            self._sfle_in_commit = False
            self.calls = 0

        def commit_layout(self, root):
            self.calls += 1

    renderer = Renderer()
    scheduled = []
    schedule_resize_settlement(
        renderer, (700, 500), lambda _ms, callback: scheduled.append(callback),
    )
    renderer._sfle_mounted_root = SimpleNamespace(disposed=False)
    scheduled.pop()()
    assert renderer.calls == 0
    assert not renderer._psx_resize_priority.settling
