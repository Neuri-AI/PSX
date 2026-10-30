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
        on_write = getattr(self, "on_write", None)
        if on_write is not None:
            on_write()


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


def test_window_resize_commits_in_same_clock_frame_as_root_sizing(monkeypatch):
    """No second UI tick may leave an old-height Grid/Scroll layout visible."""
    from types import SimpleNamespace
    from psx.sfle.model import AvailableSize, LayoutConstraints

    monkeypatch.setattr(kivy_module, "Clock", _Clock)
    _Clock.scheduled = []
    window = type("Window", (), {"size": (1600, 1200)})()
    renderer = _renderer(window)
    root = renderer._sfle_watched_widget
    renderer._sfle_resize_pending = None
    renderer._sfle_resize_event = None
    renderer._sfle_constraints = LayoutConstraints(
        AvailableSize(1600, True), AvailableSize(1200, True),
    )
    mounted = SimpleNamespace(
        disposed=False, native_handle=lambda: SimpleNamespace(widget=root),
    )
    renderer._sfle_mounted_root = mounted
    commits = []

    def set_constraints(constraints):
        renderer._sfle_constraints = constraints

    renderer.set_sfle_constraints = set_constraints
    renderer.commit_layout = lambda current: commits.append(current)
    # A real Kivy Widget fires its size observer synchronously. Without
    # coalescing, this would queue an extra frame after window resize.
    root.on_write = lambda: renderer._sfle_on_root_size(root, root.size)

    window.size = (1600, 900)
    renderer._sfle_on_window_resize(window, 1200, 450)
    assert len(_Clock.scheduled) == 1
    _Clock.scheduled.pop(0).callback(0)
    assert root.size == (1600, 900)
    assert commits == [mounted]
    assert renderer._sfle_resize_pending is None
    assert renderer._sfle_resize_event is None
    assert renderer._sfle_constraints.height.value == 900
    # A root-size event is allowed to have been queued, but must be
    # cancelled before the same frame commits the new viewport.
    assert not any(not event.cancelled for event in _Clock.scheduled)

    # A duplicate SDL resize callback does not trigger another commit.
    renderer._sfle_on_window_resize(window, 1200, 450)
    _Clock.scheduled.pop().callback(0)
    assert commits == [mounted]


def test_root_only_resize_still_uses_observer_clock(monkeypatch):
    """Standalone native root changes retain the existing deferred route."""
    from types import SimpleNamespace
    from psx.sfle.model import AvailableSize, LayoutConstraints

    monkeypatch.setattr(kivy_module, "Clock", _Clock)
    _Clock.scheduled = []
    window = type("Window", (), {"size": (1600, 1200)})()
    renderer = _renderer(window)
    renderer._sfle_resize_pending = None
    renderer._sfle_resize_event = None
    renderer._sfle_constraints = LayoutConstraints(
        AvailableSize(1600, True), AvailableSize(1200, True),
    )
    root = renderer._sfle_watched_widget
    mounted = SimpleNamespace(
        disposed=False, native_handle=lambda: SimpleNamespace(widget=root),
    )
    renderer._sfle_mounted_root = mounted
    commits = []
    renderer.set_sfle_constraints = lambda c: setattr(
        renderer, "_sfle_constraints", c,
    )
    renderer.commit_layout = lambda r: commits.append(r)
    renderer._sfle_on_root_size(root, (1600, 900))
    assert len(_Clock.scheduled) == 1
    root._size = (1600, 900)
    _Clock.scheduled.pop().callback(0)
    assert commits == [mounted]
