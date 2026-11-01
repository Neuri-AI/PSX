"""Kivy SVG images must provide a real texture to Cinnamon before layout."""

from pathlib import Path

import pytest


def test_svg_texture_rasterization_and_measurement(tmp_path):
    pytest.importorskip("kivy")
    pytest.importorskip("resvg_py")
    from psx.renderers.kivy.image import _apply_image_source, _VeltoKivyImage
    from psx.sfle.kivy_measurement import KivyMeasurementSource
    
    source = tmp_path / "logo.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
        '<rect width="80" height="40" fill="red"/></svg>',
        encoding="utf-8",
    )
    widget = _VeltoKivyImage(source="")
    widget._psx_props = {"width": 160, "height": None}
    _apply_image_source(widget, str(source))

    assert widget.source == ""
    assert widget.texture is not None
    assert tuple(widget.texture.size) == (80, 40)
    widget.texture_update()
    assert widget.texture is not None
    assert tuple(widget.texture.size) == (80, 40)
    sizes = KivyMeasurementSource._image_metrics(widget)
    assert sizes.preferred_width == 160
    assert sizes.preferred_height == 80
    assert sizes.baseline == 80

    # A delayed Kivy reload may clear the empty-source texture. Cinnamon
    # must measure the retained SVG rather than trying to open source="".
    widget.texture = None
    restored = KivyMeasurementSource._image_metrics(widget)
    assert restored == sizes
    assert restored.baseline == restored.preferred_height
    assert widget.texture is not None
