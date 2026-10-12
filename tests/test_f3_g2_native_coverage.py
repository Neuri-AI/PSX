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
        "Slider", "Radio", "ProgressBar", "Select", "Image",
        "Link", "Badge", "Divider", "Spacer", "Switch", "SpinBox", "RadioGroup", "Box", "Scroll",
    })),
    ("tk", frozenset({
        "Text", "Button", "Checkbox", "TextArea", "Slider", "Radio", "ProgressBar", "Image",
        "Link", "Badge", "Divider", "Spacer", "Switch", "SpinBox", "Select", "RadioGroup", "Box", "Scroll", "ProgressBar", "Input",
    })),
    ("kivy", frozenset({
        "Text", "Button", "Checkbox", "TextArea", "Slider", "Spacer", "Image",
        "Link", "Badge", "Divider", "Switch", "SpinBox", "Select", "Radio", "RadioGroup", "Box", "Scroll", "Checkbox", "ProgressBar", "Input",
    })),
])
def test_capability_surface_explicit_and_not_all_native_widgets(backend, expected):
    assert G2_LEAF_TYPES[backend] == expected
    assert "Scroll" in expected
    assert "Row" not in expected
    assert "Column" not in expected
    assert "Native" not in expected


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_flex_root_never_needs_intrinsic_measurement(backend):
    assert not g2_native_leaf_needs_measurement(Flex(), backend=backend)


@pytest.mark.parametrize("kind", ["Slider"])
def test_kivy_slider_requires_both_pixel_dimensions(kind):
    constructors = {"Checkbox": Checkbox, "Slider": Slider, "ProgressBar": ProgressBar, "Input": Input, "Spacer": Spacer}
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


@pytest.mark.parametrize("component", [Checkbox, Input, ProgressBar])
def test_kivy_intrinsic_controls_allow_auto_and_percentage_layout(component):
    for props in ({}, {"layout_width": "auto"},
                  {"layout_width": "60%", "layout_height": "auto"}):
        assert g2_native_leaf_needs_measurement(component(**props), backend="kivy")


def test_kivy_spacer_is_true_zero_intrinsic_not_native_default():
    assert g2_native_leaf_needs_measurement(Spacer(), backend="kivy")


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_structural_hosts_are_sfle_containers_not_intrinsic_leaves(backend):
    from psx import Divider, Text, RadioGroup, Radio
    from psx.core.vnode import Box
    assert not g2_native_leaf_needs_measurement(Box(Text("Child")), backend=backend)
    assert not g2_native_leaf_needs_measurement(
        RadioGroup(Radio("x", label="X"), value="x"), backend=backend,
    )
    assert not g2_native_leaf_needs_measurement(
        Divider(Text("Section")), backend=backend,
    )


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_invalid_structural_hosts_fail_before_native_changes(backend):
    from psx import Divider, RadioGroup, Text
    from psx.core.vnode import Box
    with pytest.raises(RendererCapabilityError, match="exactly one child"):
        g2_native_leaf_needs_measurement(Box(), backend=backend)
    with pytest.raises(RendererCapabilityError, match="Radio nodes"):
        g2_native_leaf_needs_measurement(
            RadioGroup(Text("invalid")), backend=backend,
        )
    with pytest.raises(RendererCapabilityError, match="Text child"):
        g2_native_leaf_needs_measurement(
            Divider(RadioGroup()), backend=backend,
        )


def test_kivy_textured_and_measurable_items_require_real_measurement():
    from psx import Text, Button
    assert g2_native_leaf_needs_measurement(Text("hello"), backend="kivy")
    assert g2_native_leaf_needs_measurement(Button("yes"), backend="kivy")


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_image_is_admitted_for_real_intrinsic_measurement(backend):
    # Admission is not proof of source decoding: each toolkit rejects invalid
    # image bytes during native measurement, never assumes a 100px QWidget.
    assert g2_native_leaf_needs_measurement(Image("missing.png"), backend=backend)


@pytest.mark.parametrize("backend", ["qt", "tk", "kivy"])
def test_switch_spinbox_select_have_native_measurement_ports(backend):
    from psx import Switch, SpinBox, Select
    for node in (
        Switch(checked=False),
        SpinBox(value=2, min=0, max=9),
        Select(options=("Alpha", "Beta"), value="Alpha"),
    ):
        assert g2_native_leaf_needs_measurement(node, backend=backend)


def test_backend_unknown_is_a_configuration_error():
    with pytest.raises(ValueError, match="Unknown F3-G2 backend"):
        g2_native_leaf_needs_measurement(Checkbox(), backend="unknown")


def test_policy_does_not_contaminate_native_control_props():
    source = ProgressBar(value=40, layout_width="110px", layout_height="20px")
    assert g2_native_leaf_needs_measurement(source, backend="qt")
    assert g2_native_leaf_needs_measurement(source, backend="tk")
    assert source.props["value"] == 40
    assert source.props["layout_width"] == "110px"


def test_tk_input_uses_actual_native_entry_measurement():
    assert g2_native_leaf_needs_measurement(Input(value="test"), backend="tk")
