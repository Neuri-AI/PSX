"""Regressions for Cocoa/SDL2 resize callbacks with stale Retina sizes."""

import pytest

pytest.importorskip("kivy")

from psx.renderers.kivy import kivy as kivy_module


class _Root:
    def __init__(self, parent, size):
        self.parent = parent
        self._size = size
        self.writes = 0

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        self.writes += 1
        self._size = tuple(size)


class _Event:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Clock:
    scheduled = []

    @classmethod
    def schedule_once(cls, callback, timeout):
        assert timeout == 0
        event = _Event(callback)
        cls.scheduled.append(event)
        return event


def _renderer(window, *, size=(1600, 1200)):
    renderer = object.__new__(kivy_module.KivyRenderer)
    renderer._sfle_watched_widget = _Root(window, size)
    renderer._sfle_resize_epoch = 1
    renderer._sfle_window_resize_event = None
    return renderer


def test_macos_resize_coalesces_and_reads_current_drawable_window_size(monkeypatch):
    monkeypatch.setattr(kivy_module, "Clock", _Clock)
    _Clock.scheduled = []
    window = type("Window", (), {"size": (1600, 1200)})()
    renderer = _renderer(window)
    root = renderer._sfle_watched_widget

    # SDL may report Cocoa-point dimensions (and multiple intermediate
    # events) while its current drawable pixels are from a later epoch.
    renderer._sfle_on_window_resize(window, 1200, 600)
    renderer._sfle_on_window_resize(window, 1250, 620)
    assert root.size == (1600, 1200)
    assert root.writes == 0
    assert len(_Clock.scheduled) == 1

    window.size = (1670, 1260)
    _Clock.scheduled.pop().callback(0)
    assert root.size == (1670, 1260)
    assert root.writes == 1

    renderer._sfle_on_window_resize(window, 1300, 650)
    _Clock.scheduled.pop().callback(0)
    assert root.writes == 1


def test_outdated_resize_does_not_mutate_new_root(monkeypatch):
    monkeypatch.setattr(kivy_module, "Clock", _Clock)
    _Clock.scheduled = []
    window = type("Window", (), {"size": (1600, 1200)})()
    renderer = _renderer(window)
    root = renderer._sfle_watched_widget
    renderer._sfle_on_window_resize(window, 1200, 600)
    event = _Clock.scheduled.pop()
    renderer._sfle_resize_epoch += 1
    window.size = (1400, 1000)
    event.callback(0)
    assert root.size == (1600, 1200)
    assert root.writes == 0


def test_window_resize_never_writes_when_root_unmounted(monkeypatch):
    monkeypatch.setattr(kivy_module, "Clock", _Clock)
    _Clock.scheduled = []
    window = type("Window", (), {"size": (1600, 1200)})()
    renderer = _renderer(window)
    renderer._sfle_watched_widget.parent = None
    renderer._sfle_on_window_resize(window, 1200, 600)
    assert not _Clock.scheduled
