"""A07 real coordinator RED: width-dependent intrinsic oscillation fails atomic.

No mocked solver: uses PythonLayoutEngine.compute/provisional and the actual
generation-scoped live lifecycle, with an adversarial width-dependent Text
measurement provided by the native port.
"""
import pytest
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.live_lifecycle import layout_measure_and_commit
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, IntrinsicSizes, WritingDirection
from psx.sfle.lengths import parse_length


def test_a07_real_remeasurement_oscillates_without_native_commit():
    def style(values):
        return tuple((key, parse_length(v) if isinstance(v, str) and
                      (v == "auto" or v.endswith("px") or v.endswith("%")) else v)
                     for key, v in values.items())

    snapshot = LayoutInput(
        1, 17, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(120, True), AvailableSize(60, True)),
        (
            LayoutNode("root", None, "Flex", style({
                "direction": "row", "width": "120px", "height": "60px",
                "align_items": "flex-start",
            })),
            LayoutNode("leaf", "root", "Text", style({
                "width": "auto", "height": "20px", "flex_basis": "auto",
                "flex_grow": 0, "flex_shrink": 0, "min_width": "0px",
            })),
        ), (),
    )
    engine = PythonLayoutEngine()
    calls = []
    commits = []

    def measure(node_id, width):
        assert node_id == "leaf"
        calls.append(width)
        preferred = 60 if width == 100 else 100
        return IntrinsicSizes(0, preferred, 20, 20, preferred, 20)

    with pytest.raises(SFLEError) as error:
        layout_measure_and_commit(
            snapshot, compute=engine.compute, provisional=engine.compute_provisional,
            measure_fn=measure, is_ui_thread=lambda: True,
            current_generation=lambda: 17, apply_geometry=commits.append,
            observed_geometry=lambda: {},
            initial_widths={"leaf": 100},
        )

    assert error.value.code == DiagnosticCode.UNSUPPORTED_MEASUREMENT
    assert "oscillat" in str(error.value).lower()
    assert calls == [100, 60], "Coordinator detects the repeated 100px signature before an unsafe third measurement"
    assert commits == [], "A07 never commits a provisional or oscillating geometry"
