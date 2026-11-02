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
