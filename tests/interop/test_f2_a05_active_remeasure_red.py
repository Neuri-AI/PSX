"""RED A05: active width-dependent measurement, both engines, shared coordinator."""
import pytest
from width_measurement_helpers import run_measured_case
from test_sfle_f2_differential import rust_binary


@pytest.mark.parametrize("backend", ["python", "rust"])
def test_A05_active_post_flex_remeasurement(backend, rust_binary):
    boxes, calls = run_measured_case(
        "A05", backend, rust_binary,
        characters_px=100, initial_widths={"a":50,"b":50},
    )
    assert [list(item) for item in calls] == [["a",50],["b",50],["a",35],["b",35]], "Each text leaf must be measured at initial and final allocated widths"
    assert boxes["root"].content.height == pytest.approx(60, abs=0.01)
    assert boxes["a"].content.height == pytest.approx(60, abs=0.01)
