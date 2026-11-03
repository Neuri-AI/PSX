"""Deferred Scroll reentry is coalesced and never reenters a commit."""
from types import SimpleNamespace
from psx.layout.adapters.viewport_scroll_reentry import request_scroll_reentry


class DummyRenderer:
    def __init__(self):
        self._sfle_constraints = object()
        self._sfle_mounted_root = object()
        self._sfle_in_commit = False
        self.calls = 0
    def commit_layout(self, root):
        assert root is self._sfle_mounted_root
        self.calls += 1


def test_scroll_multiple_signals_one_reentry():
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True,
                           _psx_viewport_has_deferred=True)
    scheduled = []
    for _ in range(10):
        request_scroll_reentry(renderer, host, scheduled.append)
    assert len(scheduled) == 1
    scheduled.pop()()
    assert renderer.calls == 1
    assert not host._psx_viewport_reentry_pending
    request_scroll_reentry(renderer, host, scheduled.append)
    assert len(scheduled) == 1


def test_scroll_no_virtualized_children_does_not_schedule():
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True,
                           _psx_viewport_has_deferred=False)
    scheduled = []
    request_scroll_reentry(renderer, host, scheduled.append)
    assert not scheduled
    host._psx_viewport_has_deferred = True
    renderer._sfle_in_commit = True
    request_scroll_reentry(renderer, host, scheduled.append)
    assert not scheduled


def test_scroll_destroy_while_deferred_callback_pending():
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True,
                           _psx_viewport_has_deferred=True)
    scheduled = []
    request_scroll_reentry(renderer, host, scheduled.append)
    renderer._sfle_mounted_root = None
    scheduled.pop()()
    assert renderer.calls == 0
    assert not host._psx_viewport_reentry_pending


def test_scroll_flow_acceptance_keeps_grid_reentry_enabled():
    from psx.layout.adapters.native_flow_viewport import FlowViewportPlan
    host = SimpleNamespace(
        _psx_sfle_scroll=True,
        _psx_viewport_grid_deferred=True,
        _psx_viewport_has_deferred=True,
    )
    plan = FlowViewportPlan(
        workset=None, roots=(), placements=(), widgets={},
        height=200, epoch=1, backend="tk",
        deferred_ids=frozenset(), scroll_host=host,
    )
    plan.accept()
    assert host._psx_viewport_flow_deferred is False
    assert host._psx_viewport_has_deferred is True
    host._psx_viewport_grid_deferred = False
    plan.accept()
    assert host._psx_viewport_has_deferred is False


def test_scroll_bounds_clamp_inside_commit_reenters_after_acceptance():
    from psx.layout.adapters.viewport_scroll_reentry import flush_scroll_reentry_after_commit
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True, _psx_viewport_has_deferred=True)
    pending = []
    renderer._sfle_in_commit = True
    for _ in range(8):
        request_scroll_reentry(renderer, host, pending.append)
    assert not pending
    assert len(renderer._psx_scroll_after_commit) == 1
    renderer._sfle_in_commit = False
    flush_scroll_reentry_after_commit(renderer, pending.append)
    assert len(pending) == 1
    pending.pop()()
    assert renderer.calls == 1

def test_postcommit_reentry_skips_children_fully_accepted_while_committing():
    from psx.layout.adapters.viewport_scroll_reentry import flush_scroll_reentry_after_commit
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True, _psx_viewport_has_deferred=True)
    renderer._sfle_in_commit = True
    request_scroll_reentry(renderer, host, lambda fn: None)
    renderer._sfle_in_commit = False
    host._psx_viewport_has_deferred = False
    callbacks = []
    flush_scroll_reentry_after_commit(renderer, callbacks.append)
    assert not callbacks


def test_queued_scroll_callback_does_not_disappear_during_other_commit():
    from psx.layout.adapters.viewport_scroll_reentry import flush_scroll_reentry_after_commit
    renderer = DummyRenderer()
    host = SimpleNamespace(_psx_sfle_scroll=True, _psx_viewport_has_deferred=True)
    schedule = []
    request_scroll_reentry(renderer, host, schedule.append)
    assert len(schedule) == 1
    renderer._sfle_in_commit = True
    schedule.pop()()
    assert renderer.calls == 0
    renderer._sfle_in_commit = False
    flush_scroll_reentry_after_commit(renderer, schedule.append)
    assert len(schedule) == 1
    schedule.pop()()
    assert renderer.calls == 1
