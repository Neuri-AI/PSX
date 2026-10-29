"""Exact-pixel regression tests for Tk's shared CSS corner raster cache."""
from psx.renderers.tkinter.rounded_surface import (
    _cached_corner_png, _corner_pixels, _png_rgb,
)


def test_identical_css_corners_share_raster_bytes_without_changing_pixels():
    radius = 8
    parent = (19, 24, 30)
    fill = (42, 55, 69)
    sides = (
        ("bottom", 1.0, (180, 30, 80)),
        ("left", 2.0, (20, 90, 180)),
        ("right", 1.0, (200, 120, 30)),
        ("top", 2.0, (30, 80, 190)),
    )
    _cached_corner_png.cache_clear()
    for corner in ("tl", "tr", "bl", "br"):
        unoptimized = _png_rgb(
            radius, radius,
            _corner_pixels(radius, corner, parent, fill,
                           {name: (thickness, ink) for name, thickness, ink in sides}),
        )
        first = _cached_corner_png(radius, corner, parent, fill, sides)
        second = _cached_corner_png(radius, corner, parent, fill, sides)
        assert unoptimized == first == second
    info = _cached_corner_png.cache_info()
    assert info.hits == 4 and info.misses == 4


def test_new_color_or_radius_never_reuses_previous_raster():
    _cached_corner_png.cache_clear()
    sides = (("top", 2.0, (30, 80, 190)),)
    parent = (19, 24, 30)
    a = _cached_corner_png(8, "tl", parent, (42, 55, 69), sides)
    b = _cached_corner_png(8, "tl", parent, (42, 55, 70), sides)
    c = _cached_corner_png(9, "tl", parent, (42, 55, 69), sides)
    assert a != b and a != c
    assert _cached_corner_png.cache_info().misses == 3
    assert _cached_corner_png.cache_info().maxsize == 256
