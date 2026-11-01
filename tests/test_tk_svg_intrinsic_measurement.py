"""Tk SVG loads through resvg before native intrinsic measurement."""

import pytest


def test_tk_svg_intrinsic_measurement(tmp_path):
    pytest.importorskip("resvg_py")
    pytest.importorskip("PIL")
    import tkinter as tk
    from psx.renderers.tkinter.image import TkImageAdapter
    from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    root.withdraw()
    try:
        source = tmp_path / "logo.svg"
        source.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
            '<rect width="80" height="40" fill="red"/></svg>',
            encoding="utf-8",
        )
        widget = tk.Label(root)
        props = {
            "source": str(source), "width": 160, "height": None,
            "fit": "contain", "alt": "logo", "enabled": True,
        }
        widget._psx_source = None
        widget._psx_image_cache = None
        widget._psx_photo = None
        widget._psx_props = props
        TkImageAdapter._load_and_apply(widget, props)
        assert widget._psx_image_cache.size == (80, 40)
        metrics = TkMeasurementSource._image_metrics(widget)
        assert (metrics.preferred_width, metrics.preferred_height) == (160, 80)
    finally:
        root.destroy()
