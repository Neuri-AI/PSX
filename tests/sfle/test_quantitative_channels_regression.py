"""RED A10: independent error magnitudes must not alias one another."""
import pytest
from psx.sfle.calibration import attach_calibration_errors
from psx.sfle.engine import PythonLayoutEngine
from test_acceptance_contract_regression import case_snapshot


def test_A10_quantitative_measurement_engine_and_commit_error_are_independent():
    layout=PythonLayoutEngine().compute(case_snapshot("A10"))
    # Browser actually measured 41px against independent expected 40px.
    # Engine x is 0px; independent Chromium reference x is 2px.
    report=attach_calibration_errors(
        layout,
        measured_height_pairs=[(40.0,41.0)],
        reference_border_rectangles={
            "root":{"x":2,"y":0,"width":120,"height":20}
        },
    )
    assert report.measurement_error==pytest.approx(1,abs=0.01)
    assert report.engine_error==pytest.approx(2,abs=0.01)
    assert report.geometry_commit_error is None

    committed=attach_calibration_errors(
        layout,
        measured_height_pairs=[(40.0,41.0)],
        reference_border_rectangles={
            "root":{"x":2,"y":0,"width":120,"height":20}
        },
        committed_border_rectangles={
            "root":{"x":3,"y":0,"width":120,"height":20}
        },
    )
    assert committed.measurement_error==pytest.approx(1)
    assert committed.engine_error==pytest.approx(2)
    assert committed.geometry_commit_error==pytest.approx(3)
