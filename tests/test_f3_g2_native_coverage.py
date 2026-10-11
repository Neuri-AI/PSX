"""F3-G2 backend native-leaf capability and Kivy intrinsic-size guardrails."""
from __future__ import annotations

import pytest

from psx import Checkbox, Flex, Image, Input, ProgressBar, Slider, Spacer
from psx.core.errors import RendererCapabilityError
from psx.sfle.f3_native_coverage import (
    G2_LEAF_TYPES, KIVY_EXPLICIT_BOUNDS, g2_native_leaf_needs_measurement,
)


@pytest.mark.parametrize("backend,expected", [
    ("qt", frozenset({
        "Text", "Button", "Checkbox", "Input", "TextArea",
        "Slider", "Radio", "ProgressBar", "Select",
    })),
    ("tk", frozenset({
        "Text", "Button", "Checkbox", "Slider", "Radio", "ProgressBar",
    })),
    ("kivy", frozenset({
        "Text", "Button", "Checkbox", "Slider", "Spacer",
    })),
])
def test_capability_surface_explicit_and_not_all_native_widgets(backend, expected):
    assert G2_LEAF_TYPES[backend] == expected
    assert "Scroll" not in expected
    assert "Row" not in expected
    assert "Column" not in expected
    assert "Native" not in expected


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_flex_root_never_needs_intrinsic_measurement(backend):
    assert not g2_native_leaf_needs_measurement(Flex(), backend=backend)


@pytest.mark.parametrize("kind", ["Checkbox", "Slider", "Spacer"])
def test_kivy_nontextured_controls_require_both_pixel_dimensions(kind):
    constructors = {"Checkbox": Checkbox, "Slider": Slider, "Spacer": Spacer}
    builder = constructors[kind]
    for props in (
        {},
        {"layout_width": "20px"},
        {"layout_height": "20px"},
        {"layout_width": "20%", "layout_height": "10px"},
        {"layout_width": "auto", "layout_height": "10px"},
        {"layout_width": "20px", "layout_height": "max-content"},
    ):
        with pytest.raises(RendererCapabilityError, match="explicit pixel|definite px"):
            g2_native_leaf_needs_measurement(builder(**props), backend="kivy")
    assert not g2_native_leaf_needs_measurement(
        builder(layout_width="20px", layout_height="12px"),
        backend="kivy",
    )


def test_kivy_textured_and_measurable_items_require_real_measurement():
    from psx import Text, Button
    assert g2_native_leaf_needs_measurement(Text("hello"), backend="kivy")
    assert g2_native_leaf_needs_measurement(Button("yes"), backend="kivy")


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_unported_image_cannot_silently_use_native_fallback(backend):
    with pytest.raises(RendererCapabilityError, match="not certified"):
        g2_native_leaf_needs_measurement(Image("missing.png"), backend=backend)


def test_backend_unknown_is_a_configuration_error():
    with pytest.raises(ValueError, match="Unknown F3-G2 backend"):
        g2_native_leaf_needs_measurement(Checkbox(), backend="unknown")


def test_policy_does_not_contaminate_native_control_props():
    source = ProgressBar(value=40, layout_width="110px", layout_height="20px")
    assert g2_native_leaf_needs_measurement(source, backend="qt")
    assert g2_native_leaf_needs_measurement(source, backend="tk")
    assert source.props["value"] == 40
    assert source.props["layout_width"] == "110px"


def test_tk_input_requires_separate_native_port_not_a_fake_certification():
    with pytest.raises(RendererCapabilityError, match="not certified"):
        g2_native_leaf_needs_measurement(Input(value="test"), backend="tk")
