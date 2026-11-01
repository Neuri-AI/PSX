"""The Kivy viewport must follow the drawable window, not a stale startup size.

Only the top-level window-facing widget gets a size_hint. Cinnamon still
owns every descendant's geometry and receives updates from the root observer.
"""

import pytest


def test_run_uses_native_window_sizing_for_sfle_viewport(monkeypatch):
    pytest.importorskip("kivy")
    import psx.renderers.kivy.kivy as module

    root = module.Widget(size_hint=(None, None), size=(800, 600))
    renderer = module.KivyRenderer.__new__(module.KivyRenderer)
    renderer._root = root
    renderer._sfle_constraints = object()
    observed = []

    def fake_run_touch_app(widget):
        observed.append(tuple(widget.size_hint))
        # Emulate Window.update_childsize on a Retina drawable window:
        # the physical viewport need not equal the initial layout config.
        if widget.size_hint == (1.0, 1.0):
            widget.size = (1600, 1200)

    monkeypatch.setattr(module, "runTouchApp", fake_run_touch_app)
    monkeypatch.setattr(renderer, "invalidate_layout", lambda: observed.append("closed"))

    assert renderer.run() == 0
    assert observed == [(1.0, 1.0), "closed"]
    assert tuple(root.size) == (1600, 1200)
    assert tuple(root.size_hint) == (None, None)


def test_run_preserves_non_sfle_root_size_hint(monkeypatch):
    pytest.importorskip("kivy")
    import psx.renderers.kivy.kivy as module

    root = module.Widget(size_hint=(None, None))
    renderer = module.KivyRenderer.__new__(module.KivyRenderer)
    renderer._root = root
    renderer._sfle_constraints = None
    observed = []
    monkeypatch.setattr(module, "runTouchApp", lambda widget: observed.append(tuple(widget.size_hint)))
    monkeypatch.setattr(renderer, "invalidate_layout", lambda: None)

    assert renderer.run() == 0
    assert observed == [(None, None)]
