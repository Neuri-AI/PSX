"""C5 semantic invalidation contract and generation-fence behavior."""
from __future__ import annotations

import pytest

from psx.sfle.f3_g2_invalidation import MeasurementInvalidations, REASONS


def test_c5_invalidation_taxonomy_is_explicit():
    assert REASONS == {"content", "font", "theme", "resource", "dpi", "viewport"}


def test_c5_duplicate_notifications_coalesce_and_acknowledge_only_latest():
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


def test_c5_teardown_fences_queued_invalidation():
    state = MeasurementInvalidations()
    epoch = state.request("viewport")
    state.cancel()
    assert not state.is_current(epoch)
    assert not state.needs_commit()
    assert not state.acknowledge(epoch)


@pytest.mark.parametrize("reason", ("", "all", "input", "font-change", "window", "unknown"))
def test_c5_unknown_invalidation_kind_fails_closed(reason):
    state = MeasurementInvalidations()
    with pytest.raises(ValueError, match="Unsupported SFLE measurement invalidation"):
        state.request(reason)
    assert not state.needs_commit()
