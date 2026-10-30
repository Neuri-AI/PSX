"""Inline controls must not certify the viewport as their measured width.

The same invariant applies to Kivy, Tk and Qt when a block containing
native buttons becomes a horizontal, wrapping inline run under a column Flex.
"""
from dataclasses import replace

import pytest

from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.sfle.width_dependent_intrinsic_measurement import (
    compute_width_dependent, seed_unconstrained_width_measurements,
)


def sidebar_inline_measurements():
    constraints = LayoutConstraints(
        AvailableSize(800, True), AvailableSize(600, True),
    )
    nodes = (
        LayoutNode("sidebar", None, "Flex", (
            ("direction", "column"), ("width", "800px"), ("height", "600px"),
        )),
        LayoutNode("navigation", "sidebar", "Flex", (
            ("direction", "row"), ("wrap", "wrap"), ("align_items", "flex-start"),
        )),
        LayoutNode("home", "navigation", "Button", ()),
        LayoutNode("settings", "navigation", "Button", ()),
        LayoutNode("footer", "sidebar", "Flex", (
            ("direction", "column"), ("layout_margin_top", "auto"),
        )),
        LayoutNode("profile", "footer", "Text", ()),
    )
    measured = (
        ("home", 60.0, 24.0),
        ("settings", 118.0, 24.0),
        ("profile", 80.0, 20.0),
    )
    measurements = tuple(
        MeasuredBox(
            node_id, IntrinsicSizes(w, w, h, h, w, h),
            constraints, 1,
        )
        for node_id, w, h in measured
    )
    return LayoutInput(
        1, 1, WritingDirection.LTR, constraints, nodes, measurements,
    )


@pytest.mark.parametrize("backend", ["python", "selected"])
def test_sidebar_inline_buttons_and_auto_footer_have_certified_intrinsic_widths(backend):
    engine = PythonLayoutEngine() if backend == "python" else load_layout_engine()
    initial = sidebar_inline_measurements()

    # The text needs height-for-width measurement, while the two native
    # buttons are width-independent. Neither button may falsely claim it was
    # measured at the 800px viewport width.
    snapshot = seed_unconstrained_width_measurements(
        initial, frozenset({"home", "settings", "profile"}),
    )
    reads = []
    result = compute_width_dependent(
        engine, snapshot,
        {"profile": lambda width: (
            reads.append(width) or IntrinsicSizes(80, 80, 20, 20, 80, 20)
        )},
        current_generation=lambda: 1,
    )
    assert reads
    boxes = dict(result.boxes)
    home = boxes["home"].border
    settings = boxes["settings"].border
    footer = boxes["footer"].border
    assert home.width == pytest.approx(60, abs=1)
    assert settings.width == pytest.approx(118, abs=1)
    assert settings.x == pytest.approx(home.x + home.width, abs=1)
    assert settings.y == pytest.approx(home.y, abs=1)
    assert footer.y + footer.height == pytest.approx(600, abs=1)


def test_viewport_width_must_not_be_certified_for_intrinsic_button():
    engine = PythonLayoutEngine()
    initial = sidebar_inline_measurements()
    # This matches the old Kivy/Tk adapters: only width-dependent Text was
    # unqualified; Button retained a false definite 800px measurement.
    invalid = seed_unconstrained_width_measurements(
        initial, frozenset({"profile"}),
    )
    with pytest.raises(SFLEError, match="Missing post-flex width-specific"):
        compute_width_dependent(
            engine, invalid,
            {"profile": lambda width: IntrinsicSizes(80, 80, 20, 20, 80, 20)},
            current_generation=lambda: 1,
        )
