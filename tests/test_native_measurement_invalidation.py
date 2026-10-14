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
