"""Native layout G2 physical-pixel readback invariants (do not double-scale widgets)."""
from __future__ import annotations

from types import SimpleNamespace
import math

import pytest

from psx.sfle.errors import SFLEError
from psx.sfle.model import Rect
from psx.sfle.native_pixel_space import DevicePixelSpace


@pytest.mark.parametrize("backend", ("qt", "kivy", "tk"))
def test_unit_device_pixel_space_and_exact_edges(backend):
    fake_qt = SimpleNamespace(devicePixelRatioF=lambda: 1)
    space = DevicePixelSpace.from_widget(backend, fake_qt)
    assert space.scale == 1
    assert space.to_physical(Rect(10.25, 5.5, 20.5, 7.25)) == Rect(10, 6, 21, 7)


@pytest.mark.parametrize("dpr", (1.0, 1.25, 1.5, 2.0, 2.5, 3.0))
def test_fractional_dpi_snaps_absolute_edges_without_width_drift(dpr):
    space = DevicePixelSpace(dpr, "qt")
    source = Rect(10.25, 5.5, 20.5, 7.25)
    actual = space.to_physical(source)
    x0 = math.floor(source.x * dpr + 0.5)
    x1 = math.floor((source.x + source.width) * dpr + 0.5)
    y0 = math.floor(source.y * dpr + 0.5)
    y1 = math.floor((source.y + source.height) * dpr + 0.5)
    assert actual == Rect(x0, y0, x1 - x0, y1 - y0)
    assert abs(actual.x - source.x * dpr) <= 0.5
    assert abs(actual.y - source.y * dpr) <= 0.5


def test_fractional_scale_is_obtained_from_live_qwidget_each_transaction():
    holder = {"dpr": 1.0}
    widget = SimpleNamespace(devicePixelRatioF=lambda: holder["dpr"])
    assert DevicePixelSpace.from_widget("qt", widget).scale == 1.0
    holder["dpr"] = 1.5
    assert DevicePixelSpace.from_widget("qt", widget).scale == 1.5
    holder["dpr"] = 2.0
    assert DevicePixelSpace.from_widget("qt", widget).scale == 2.0


def test_qt5_legacy_device_pixel_ratio_fallback():
    widget = SimpleNamespace(devicePixelRatio=lambda: 2)
    space = DevicePixelSpace.from_widget("qt", widget)
    assert space.scale == 2


@pytest.mark.parametrize("scale", (0, -1, math.inf, -math.inf, math.nan))
def test_invalid_device_pixel_scale_fails_before_native_commit(scale):
    with pytest.raises(ValueError, match="scale|positive"):
        DevicePixelSpace(scale, "qt")


@pytest.mark.parametrize("scale", ("2", None, True))
def test_non_numeric_device_pixel_scale_fails_closed(scale):
    with pytest.raises(TypeError):
        DevicePixelSpace(scale, "qt")


def test_missing_qt_device_pixel_ratio_fails_closed():
    with pytest.raises(SFLEError, match="device pixel ratio"):
        DevicePixelSpace.from_widget("qt", SimpleNamespace())


def test_invalid_toolkit_cannot_masquerade_as_qt_or_native_pixel_space():
    with pytest.raises(ValueError):
        DevicePixelSpace.from_widget("android", object())
    with pytest.raises(ValueError):
        DevicePixelSpace(1, "android")


def test_widget_readback_error_tracks_logical_and_physical_units_separately():
    scale = DevicePixelSpace(2.0, "qt")
    logical, physical = scale.error(
        Rect(0, 0, 20, 10), Rect(1, 0, 20, 10),
    )
    assert logical == 1
    assert physical == 2
    assert scale.allowed_physical_error == 2


def test_tk_scaling_and_kivy_density_do_not_double_scale_widget_coordinates():
    # These values affect Tk points / Kivy dp-style conversions, *not* the
    # unit used by place() / Widget.pos after viewport sizes are resolved.
    fake = SimpleNamespace(density=3.0, tk_scaling=2.5)
    assert DevicePixelSpace.from_widget("kivy", fake).scale == 1
    assert DevicePixelSpace.from_widget("tk", fake).scale == 1
    assert DevicePixelSpace.from_widget("kivy", fake).to_physical(
        Rect(10, 12, 25, 40),
    ) == Rect(10, 12, 25, 40)


def test_nested_edges_do_not_add_independent_sibling_pixel_rounding():
    scale = DevicePixelSpace(1.5, "qt")
    left = scale.to_physical(Rect(0, 0, 20.25, 10))
    right = scale.to_physical(Rect(20.25, 0, 15.5, 10))
    assert left.x + left.width == right.x
    assert right.width >= 0
