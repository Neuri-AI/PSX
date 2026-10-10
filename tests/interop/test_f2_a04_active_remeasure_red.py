"""RED A04: active width-dependent measurement, both engines, shared coordinator."""
import pytest
from width_measurement_helpers import run_measured_case
from test_sfle_f2_differential import rust_binary


@pytest.mark.parametrize("backend", ["python", "rust"])
def test_A04_active_post_flex_remeasurement(backend, rust_binary):
    boxes, calls = run_measured_case(
        "A04", backend, rust_binary,
        characters_px=210, initial_widths={"text":100},
    )
    assert [list(item) for item in calls] == [["text",100],["text",150]], "Each text leaf must be measured at initial and final allocated widths"
    assert boxes["root"].content.height == pytest.approx(40, abs=0.01)
    assert boxes["text"].content.height == pytest.approx(40, abs=0.01)
