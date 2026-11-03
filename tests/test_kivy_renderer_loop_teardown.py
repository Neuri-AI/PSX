"""Kivy event-loop exit must release renderer-owned native watchers."""

import pytest

pytest.importorskip("kivy")

import psx.renderers.kivy.kivy as renderer_module


@pytest.mark.parametrize("interrupt", [False, True])
def test_kivy_renderer_cleans_window_observers_when_mainloop_exits(monkeypatch, interrupt):
    renderer = object.__new__(renderer_module.KivyRenderer)
    renderer._root = object()
    renderer._sfle_watched_widget = None
    cleaned = []
    renderer.invalidate_layout = lambda: cleaned.append("invalidated")

    def fake_run_touch_app(root):
        assert root is renderer._root
        if interrupt:
            raise KeyboardInterrupt()

    monkeypatch.setattr(renderer_module, "runTouchApp", fake_run_touch_app)
    if interrupt:
        with pytest.raises(KeyboardInterrupt):
            renderer.run()
    else:
        assert renderer.run() == 0
    assert cleaned == ["invalidated"]
