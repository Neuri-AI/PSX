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
    assert coordinator.promote(workset, "a")
    assert not coordinator.promote(workset, "b")
    assert not coordinator.finish_batch(success=False)
    generation = coordinator.resize((900, 600))
    assert coordinator.begin_settlement(generation)
    assert coordinator.promote(workset, "a")
    coordinator.cancel()
    assert not coordinator.begin_batch(generation)
