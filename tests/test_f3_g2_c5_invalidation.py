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


def test_every_supported_native_component_has_c5_invalidation_evidence():
    from psx.sfle.f3_g2_matrix import g2_certification_matrix
    from psx.sfle.f3_g2_contracts import g2_operation_contracts
    native = [c for c in g2_certification_matrix() if c.status == "native"]
    assert native
    assert all("invalidation" in c.operations_with_evidence for c in native)
    gaps = [
        (contract.backend, contract.component, contract.mechanism)
        for contract in g2_operation_contracts()
        if contract.operation == "invalidation"
        and contract.applicability == "required"
        and contract.mechanism != "pytest_reference"
    ]
    assert not gaps, f"C5 per-component invalidation coverage gaps: {gaps}"
