"""F2.2.4.5 end-to-end bounded dependency remeasurement tests."""
import pytest

from psx.sfle.dependency_cycle import resolve_measurement_dependencies
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.sfle.native_measurement import NativeMeasurementPort
from psx.sfle.used_size_tree import UsedSizeTree


def box(width, height=20):
    return LayoutConstraints(
        AvailableSize(width, width is not None),
        AvailableSize(height, height is not None),
    )


def tree(width=None):
    return UsedSizeTree(8, (
        ("root", box(200, 100)),
        ("leaf", box(width)),
    ), ("leaf",) if width is None else ())


def snapshot():
    return LayoutInput(
        1, 8, WritingDirection.LTR, box(200, 100),
        (
            LayoutNode("root", None, "Flex", ()),
            LayoutNode("leaf", "root", "Text", ()),
        ), (),
    )


def port(calls):
    intrinsic = IntrinsicSizes(10, 60, 10, 20, 60, 20)
    def measure(request):
        calls.append((request.node_id, request.constraints.width.value))
        return MeasuredBox(request.node_id, intrinsic, request.constraints, request.revision)
    return NativeMeasurementPort(lambda: True, measure)


def test_two_pass_intrinsic_dependency_converges():
    calls = []
    def recompute(snap, current):
        assert len(snap.measurements) == 2
        leaf = next(m for m in snap.measurements if m.node_id == "leaf")
        return tree(leaf.intrinsic.preferred_width)
    result = resolve_measurement_dependencies(
        snapshot(), tree(), native_port=port(calls), recompute=recompute,
    )
    assert result.used_sizes == tree(60)
    assert result.iterations == 2
    assert [name for name, _ in calls].count("leaf") == 2


def test_stable_finite_tree_reuses_cached_measurements():
    calls = []
    result = resolve_measurement_dependencies(
        snapshot(), tree(60), native_port=port(calls),
        recompute=lambda snap, current: current,
    )
    assert result.iterations == 1
    assert len(result.measurements) == 2


def test_unsupported_unresolved_cycle_fails_closed():
    calls = []
    with pytest.raises(SFLEError) as error:
        resolve_measurement_dependencies(
            snapshot(), tree(), native_port=port(calls),
            recompute=lambda snap, current: current,
        )
    assert error.value.code is DiagnosticCode.UNSUPPORTED_MEASUREMENT


def test_invalid_adapter_measurement_rejected_before_recompute():
    called = []
    bad = NativeMeasurementPort(lambda: True, lambda request: MeasuredBox(
        request.node_id,
        IntrinsicSizes(1,1,1,1,1,1),
        request.constraints,
        request.revision + 1,
    ))
    with pytest.raises(SFLEError):
        resolve_measurement_dependencies(
            snapshot(), tree(), native_port=bad,
            recompute=lambda snap, current: called.append(True) or current,
        )
    assert not called


def test_non_ui_thread_never_calls_measurement():
    called = []
    bad = NativeMeasurementPort(lambda: False, lambda request: called.append(True))
    with pytest.raises(SFLEError):
        resolve_measurement_dependencies(
            snapshot(), tree(), native_port=bad,
            recompute=lambda snap, current: current,
        )
    assert not called
