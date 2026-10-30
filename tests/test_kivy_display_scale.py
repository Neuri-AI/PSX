"""High-DPI scale observations must not change Kivy or Cinnamon geometry."""
from types import SimpleNamespace

import pytest

from psx.sfle.kivy_display_scale import KivyDisplayScale


@pytest.mark.parametrize("factor", (1, 1.25, 1.5, 2, 2.5, 3))
def test_retina_scale_reads_both_coordinate_spaces(factor):
    window = SimpleNamespace(
        size=(800 * factor, 600 * factor),
        system_size=(800, 600),
    )
    before = (window.size, window.system_size)
    scale = KivyDisplayScale.from_window(window)
    assert scale.uniform == pytest.approx(factor)
    assert scale.snapshot()["scale_y"] == pytest.approx(factor)
    assert (window.size, window.system_size) == before


def test_anisotropic_report_fails_closed_instead_of_distorting_css():
    scale = KivyDisplayScale(1600, 1200, 800, 500)
    with pytest.raises(ValueError, match="unequal axis"):
        _ = scale.uniform


@pytest.mark.parametrize("bad", (0, -1, float("nan"), float("inf"), True))
def test_unusable_screen_dimensions_are_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        KivyDisplayScale(bad, 600, 800, 600)


def test_no_implicit_kivy_density_or_widget_scaling():
    window = SimpleNamespace(size=(1600, 1200), system_size=(800, 600))
    scale = KivyDisplayScale.from_window(window)
    assert scale.uniform == 2
    # This class reports the backing pixel ratio; it does not assert that
    # Widget.size is in Cocoa points or dictate a conversion for every host.
    assert not hasattr(scale, "scale_widget")


@pytest.mark.parametrize(
    ("drawable", "system", "expected"),
    [
        ((1600, 1200), (800, 600), 2.0),
        ((1600, 1200), (800, 590), 2.0),
        ((1600, 1200), (800, 500), 2.0),
        ((1200, 900), (800, 600), 1.5),
        ((800, 600), (800, 600), 1.0),
        ((1537, 999), (811, 417), 1.0),
    ],
)
def test_css_scale_does_not_block_startup_when_cocoa_axes_disagree(
    drawable, system, expected,
):
    scale = KivyDisplayScale.from_window(
        SimpleNamespace(size=drawable, system_size=system)
    )
    assert scale.css_scale == pytest.approx(expected)


def test_anisotropic_diagnostic_remains_available_even_if_runtime_can_boot():
    scale = KivyDisplayScale(1600, 1200, 800, 500)
    assert scale.css_scale == 2.0
    with pytest.raises(ValueError, match="unequal axis"):
        _ = scale.uniform
