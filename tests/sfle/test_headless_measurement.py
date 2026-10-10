"""F2.2.4.7 deterministic headless measurement contract tests."""
import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.headless_measurement import HeadlessMeasurementSource
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.measurement_round import MeasurementRound
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox,
)
from psx.sfle.native_measurement import fulfill_native_round


METRICS = IntrinsicSizes(3, 20, 4, 12, 18, 10, 7)
WIDTH_100 = LayoutConstraints(AvailableSize(100, True), AvailableSize(None, False))


def test_headless_round_preserves_constraints_and_revision():
    source = HeadlessMeasurementSource((("label", METRICS),))
    request = MeasurementRequest("label", WIDTH_100, 9, 3)
    round_ = MeasurementRound(9, (request,), (), ("label",))
    results = fulfill_native_round(round_, source.port(), current_generation=9)
    assert results == (MeasuredBox("label", METRICS, WIDTH_100, 3),)


def test_headless_round_rejects_stale_generation_before_measure():
    source = HeadlessMeasurementSource((("label", METRICS),))
    round_ = MeasurementRound(9, (MeasurementRequest("missing", WIDTH_100, 9, 3),), (), ())
    with pytest.raises(SFLEError, match="Stale"):
        fulfill_native_round(round_, source.port(), current_generation=10)


def test_headless_missing_metrics_fails_closed():
    source = HeadlessMeasurementSource((("label", METRICS),))
    round_ = MeasurementRound(9, (MeasurementRequest("missing", WIDTH_100, 9, 3),), (), ())
    with pytest.raises(SFLEError, match="No headless intrinsic snapshot"):
        fulfill_native_round(round_, source.port(), current_generation=9)


def test_headless_rejects_duplicate_identifiers_and_invalid_metrics():
    with pytest.raises(SFLEError):
        HeadlessMeasurementSource((("label", METRICS), ("label", METRICS)))
    with pytest.raises(TypeError):
        HeadlessMeasurementSource((("label", object()),))


def test_headless_preserves_retained_measurements_in_round():
    source = HeadlessMeasurementSource((("label", METRICS),))
    retained = MeasuredBox("cached", METRICS, WIDTH_100, 1)
    round_ = MeasurementRound(
        4, (MeasurementRequest("label", WIDTH_100, 4, 2),), (retained,), ()
    )
    results = fulfill_native_round(round_, source.port(), current_generation=4)
    assert results[0] is retained
    assert results[1].node_id == "label"
