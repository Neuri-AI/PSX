"""F2.2.4.5 measurement round planning and atomic acceptance."""
import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.measurement_round import accept_round, prepare_round
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode, MeasuredBox, WritingDirection
from psx.sfle.remeasurement import RemeasurementDelta


def size(value):
    return LayoutConstraints(AvailableSize(value, value is not None), AvailableSize(20, True))


def measured(node_id, constraint, revision=0):
    return MeasuredBox(node_id, IntrinsicSizes(1, 1, 1, 1, 1, 1), constraint, revision)


def snapshot():
    return LayoutInput(1, 8, WritingDirection.LTR, size(200), (
        LayoutNode("root", None, "Flex", ()),
        LayoutNode("child", "root", "Flex", ()),
        LayoutNode("leaf", "child", "Text", ()),
    ), (measured("root", size(200)), measured("child", size(100)), measured("leaf", size(50))))


def test_changed_child_round_requests_leaf_first_and_validates_all_results():
    current = (("root", size(200)), ("child", size(120)), ("leaf", size(50)))
    delta = RemeasurementDelta(8, ("child",), ("leaf", "child", "root"), ())
    round_ = prepare_round(snapshot(), delta, constraints=current)
    assert [item.node_id for item in round_.requests] == ["leaf", "child", "root"]
    results = tuple(measured(req.node_id, req.constraints) for req in round_.requests)
    assert len(accept_round(round_, results, current_generation=8)) == 3
    with pytest.raises(SFLEError):
        accept_round(round_, results[:-1], current_generation=8)
    with pytest.raises(SFLEError):
        accept_round(round_, results, current_generation=9)


def test_unchanged_cached_round_retains_without_native_measurement():
    delta = RemeasurementDelta(8, (), (), ())
    round_ = prepare_round(snapshot(), delta, constraints=(
        ("root", size(200)), ("child", size(100)), ("leaf", size(50)),
    ))
    assert round_.requests == ()
    assert len(round_.retained) == 3


def test_deferred_axis_remains_indefinite_and_requires_measurement():
    delta = RemeasurementDelta(8, ("child",), ("leaf", "child", "root"), ("child",))
    round_ = prepare_round(snapshot(), delta, constraints=(
        ("root", size(200)), ("child", size(None)), ("leaf", size(50)),
    ))
    assert round_.deferred == ("child",)
    assert round_.requests[1].constraints.width.definite is False
    with pytest.raises(SFLEError):
        prepare_round(snapshot(), delta, constraints=(
            ("root", size(200)), ("child", size(100)), ("leaf", size(50)),
        ))
