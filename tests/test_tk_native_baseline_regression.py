"""Tk native baseline regression across measured Flex leaves."""

import pytest


def test_tk_native_baselines():
    import tkinter as tk
    from tkinter import ttk
    from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource
    from psx.layout.fallback.measurement_plan import MeasurementRequest
    from psx.layout.contracts.model import AvailableSize, LayoutConstraints

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No Tk display")
    root.withdraw()
    try:
        text = ttk.Label(root, text="Hello")
        link = ttk.Label(root, text="Docs")
        button = ttk.Button(root, text="Submit")
        widgets = {"text": text, "link": link, "button": button}
        constraints = LayoutConstraints(
            AvailableSize(320.0, True), AvailableSize(None, False))
        source = TkMeasurementSource(widgets)
        for node_id in widgets:
            measured = source.measure(
                MeasurementRequest(node_id, constraints, 1, 1)).intrinsic
            assert measured.baseline is not None, node_id
            assert 0 <= measured.baseline <= measured.preferred_height
        wrapped = source.measure_width("text", 160.0)
        assert wrapped.baseline is not None
    finally:
        root.destroy()


def test_tk_image_bottom_edge_baseline():
    from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource

    class FakeImage:
        size = (80, 40)

    class FakeWidget:
        _psx_image_cache = FakeImage()
        _psx_props = {"width": 160, "height": None}

    image = TkMeasurementSource._image_metrics(FakeWidget())
    assert image.baseline == image.preferred_height == 80
