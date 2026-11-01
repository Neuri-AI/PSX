"""Native geometry commit guards and generation invalidation."""
import pytest

from psx.layout.contracts.errors import SFLEError
from psx.layout.adapters.headless_measurement import HeadlessMeasurementSource
from psx.layout.runtime.native_lifecycle import NativeLayoutLifecycle, layout_and_commit
from psx.layout.fallback.measurement_plan import MeasurementRequest
from psx.layout.contracts.model import IntrinsicSizes
from test_recursive_measurement import NODES, SIZING, METRICS, snapshot


def test_commit_runs_only_after_a_complete_native_round():
    commits = []
    source = HeadlessMeasurementSource((("root", METRICS), ("child", METRICS)))
    lifecycle = NativeLayoutLifecycle(lambda: 5, source.port(), commits.append)
    result = layout_and_commit(snapshot(), NODES, lifecycle, child_sizing=SIZING)
    assert commits == [result]
    assert result.geometry.boxes[1].content.width == 40


def test_stale_generation_blocks_commit_after_measurement():
    commits = []
    generation = [5]

    def measure(request: MeasurementRequest):
        generation[0] = 6
        return HeadlessMeasurementSource(((request.node_id, METRICS),)).measure(request)

    from psx.layout.runtime.native_measurement import NativeMeasurementPort
    lifecycle = NativeLayoutLifecycle(
        lambda: generation[0], NativeMeasurementPort(lambda: True, measure),
        commits.append,
    )
    with pytest.raises(SFLEError, match="stale"):
        layout_and_commit(snapshot(), NODES, lifecycle, child_sizing=SIZING)
    assert commits == []


def test_deferred_axis_is_not_committed_as_complete_geometry():
    from psx.layout.contracts.lengths import Length, LengthKind
    from psx.layout.fallback.constraint_propagation import ChildSizing
    commits = []
    source = HeadlessMeasurementSource((("root", METRICS), ("child", METRICS)))
    lifecycle = NativeLayoutLifecycle(lambda: 5, source.port(), commits.append)
    with pytest.raises(SFLEError, match="deferred"):
        layout_and_commit(snapshot(), NODES, lifecycle, child_sizing=(
            ("child", ChildSizing(Length(LengthKind.AUTO), Length.px(20))),
        ))
    assert commits == []


def test_wrong_ui_thread_blocks_all_native_measurement():
    from psx.layout.runtime.native_measurement import NativeMeasurementPort
    lifecycle = NativeLayoutLifecycle(
        lambda: 5,
        NativeMeasurementPort(lambda: False, lambda _: (_ for _ in ()).throw(AssertionError())),
        lambda _: (_ for _ in ()).throw(AssertionError()),
    )
    with pytest.raises(SFLEError, match="UI thread"):
        layout_and_commit(snapshot(), NODES, lifecycle, child_sizing=SIZING)
