"""Qt-compatible, inward-only Kivy stroke coordinates."""
import pytest

from psx.css.native_paint import inset_rounded_border_box


@pytest.mark.parametrize("scale", (1.0, 1.5, 2.0, 3.0))
def test_inset_border_never_paints_outside_box(scale):
    left, bottom, width, height, radius = inset_rounded_border_box(
        10 * scale, 20 * scale, 200 * scale, 120 * scale,
        8 * scale, 1 * scale,
    )
    half = scale / 2
    assert left - half == pytest.approx(10 * scale)
    assert bottom - half == pytest.approx(20 * scale)
    assert left + width + half == pytest.approx(210 * scale)
    assert bottom + height + half == pytest.approx(140 * scale)
    assert radius == pytest.approx(7.5 * scale)


def test_inset_border_radius_clamps_to_zero():
    assert inset_rounded_border_box(0, 0, 30, 30, 0, 2) == (
        1, 1, 28, 28, 0
    )


@pytest.mark.parametrize("values", [
    (0, 0, -1, 20, 2, 1),
    (0, 0, 20, 20, -1, 1),
    (0, 0, 20, 20, 2, 0),
])
def test_invalid_stroke_geometry_fails_closed(values):
    with pytest.raises(ValueError):
        inset_rounded_border_box(*values)
