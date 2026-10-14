"""G2 width-dependent intrinsic measurement contract: exact post-flex widths."""
from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.width_dependent_intrinsic_measurement import (
    auto_height_measurement_ids, compute_width_dependent,
    seed_unconstrained_width_measurements,
)
from psx.sfle.model import (
    AvailableSize, BoxRect, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, LayoutResult, MeasuredBox, Rect, WritingDirection,
)


def intrinsic(height=16):
    return IntrinsicSizes(8, 140, height, height, 140, height)


def snapshot():
    root = LayoutNode(
        "root", None, "Flex",
        (("direction", "column"), ("width", "160px"), ("height", "80px")),
    )
    child = LayoutNode(
        "text", "root", "Text",
        (("layout_width", "100%"),),
    )
    constraints = LayoutConstraints(AvailableSize(160, True), AvailableSize(80, True))
    return LayoutInput(
        1, 3, WritingDirection.LTR, constraints,
        (root, child),
        (MeasuredBox("text", intrinsic(), constraints, 3),),
    )


def box(width, height, y=0):
    rect = Rect(0, y, width, height)
    return BoxRect(rect, rect, rect, rect)


class FixedProvisional:
    def __init__(self, width=72):
        self.width = width
        self.provisional_calls = 0
        self.final_calls = 0

    def compute_provisional(self, source):
        self.provisional_calls += 1
        measured = source.measurements[0].intrinsic
        return LayoutResult(1, source.generation, (
            ("root", box(160, 80)),
            ("text", box(self.width, measured.preferred_height)),
        ))

    def compute(self, source):
        self.final_calls += 1
        return self.compute_provisional(source)


def test_measures_actual_leaf_width_not_root_viewport():
    engine = FixedProvisional(72)
    incoming = snapshot()
    selected = auto_height_measurement_ids(incoming)
    assert selected == frozenset({"text"})
    incoming = seed_unconstrained_width_measurements(incoming, selected)
    widths = []
    def measure(width):
        widths.append(width)
        return intrinsic(44 if width < 80 else 20)
    result = compute_width_dependent(
        engine, incoming, {"text": measure}, current_generation=lambda: 3,
    )
    assert widths == [72]
    assert dict(result.boxes)["text"].content.height == 44
    assert engine.provisional_calls == 3
    assert engine.final_calls == 1


def test_explicit_text_height_is_not_selected_for_intrinsic_remeasurement():
    incoming = snapshot()
    leaf = replace(incoming.nodes[1], style=(
        ("layout_height", "20px"), ("layout_width", "100%"),
    ))
    fixed = replace(incoming, nodes=(incoming.nodes[0], leaf))
    assert auto_height_measurement_ids(fixed) == frozenset()


def test_missing_native_width_port_fails_before_geometry():
    with pytest.raises(SFLEError, match="compute_provisional"):
        compute_width_dependent(
            object(), snapshot(), {"text": lambda width: intrinsic()},
            current_generation=lambda: 3,
        )


def test_stale_generation_rejected_before_native_measurement():
    called = []
    with pytest.raises(SFLEError) as error:
        compute_width_dependent(
            FixedProvisional(), snapshot(),
            {"text": lambda width: called.append(width) or intrinsic()},
            current_generation=lambda: 4,
        )
    assert error.value.code is DiagnosticCode.INVALID_SNAPSHOT
    assert not called


def test_invalid_native_width_metrics_rejected_without_commit():
    engine = FixedProvisional()
    with pytest.raises(SFLEError) as error:
        compute_width_dependent(
            engine, seed_unconstrained_width_measurements(
                snapshot(), frozenset({"text"}),
            ),
            {"text": lambda width: (12, 20)},
            current_generation=lambda: 3,
        )
    assert error.value.code is DiagnosticCode.UNSUPPORTED_MEASUREMENT
    assert engine.final_calls == 0


def test_oscillating_provisional_width_fails_closed():
    class Oscillating(FixedProvisional):
        def compute_provisional(self, source):
            self.width = 72 if self.width == 110 else 110
            return super().compute_provisional(source)
    engine = Oscillating(110)
    with pytest.raises(SFLEError, match="failed to converge"):
        compute_width_dependent(
            engine,
            seed_unconstrained_width_measurements(snapshot(), frozenset({"text"})),
            {"text": lambda width: intrinsic(20)},
            current_generation=lambda: 3,
        )
    assert engine.final_calls == 0


def test_real_python_engine_provisional_parity_for_explicit_width():
    incoming = seed_unconstrained_width_measurements(
        snapshot(), frozenset({"text"}),
    )
    engine = PythonLayoutEngine()
    widths = []
    result = compute_width_dependent(
        engine, incoming,
        {"text": lambda width: widths.append(width) or intrinsic(24)},
        current_generation=lambda: 3,
    )
    assert widths
    assert abs(widths[0] - 160) < 0.01
    assert abs(dict(result.boxes)["text"].border.height - 24) <= 0.01
