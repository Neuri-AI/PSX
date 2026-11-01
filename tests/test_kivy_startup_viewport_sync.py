"""Regressions for missed Kivy Window attachment / Retina resize epochs."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("root_size", [(800, 600), (1600, 1200)])
def test_startup_sync_updates_constraints_even_without_new_root_resize(
    monkeypatch, root_size,
):
    pytest.importorskip("kivy")
    from kivy.core import window as window_module
    from psx.renderers.kivy.kivy import KivyRenderer
    from psx.sfle.model import AvailableSize, LayoutConstraints

    window = SimpleNamespace(size=(1600, 1200))
    monkeypatch.setattr(window_module, "Window", window)

    root = SimpleNamespace(parent=window, size=root_size)
    mounted = SimpleNamespace(disposed=False)
    renderer = KivyRenderer.__new__(KivyRenderer)
    renderer._root = root
    renderer._sfle_watched_widget = root
    renderer._sfle_mounted_root = mounted
    renderer._sfle_constraints = LayoutConstraints(
        AvailableSize(800, True), AvailableSize(600, True),
    )
    renderer._sfle_generation = 0
    renderer._sfle_resize_pending = (800, 600)
    pending = SimpleNamespace(cancelled=False)
    pending.cancel = lambda: setattr(pending, "cancelled", True)
    renderer._sfle_resize_event = pending
    renderer._sfle_window_resize_event = None
    commits = []
    renderer.commit_layout = lambda instance: commits.append(instance)

    renderer._sfle_sync_attached_viewport()

    assert tuple(root.size) == (1600, 1200)
    assert renderer._sfle_constraints.width.value == 1600
    assert renderer._sfle_constraints.height.value == 1200
    assert pending.cancelled
    assert renderer._sfle_resize_pending is None
    assert commits == [mounted]

    # The next frame is stable. Do not force another expensive layout.
    renderer._sfle_sync_attached_viewport()
    assert commits == [mounted]


def test_startup_sync_never_reflows_when_native_and_cinnamon_match(monkeypatch):
    pytest.importorskip("kivy")
    from kivy.core import window as window_module
    from psx.renderers.kivy.kivy import KivyRenderer
    from psx.sfle.model import AvailableSize, LayoutConstraints

    window = SimpleNamespace(size=(1024, 768))
    monkeypatch.setattr(window_module, "Window", window)
    root = SimpleNamespace(parent=window, size=(1024, 768))
    renderer = KivyRenderer.__new__(KivyRenderer)
    renderer._sfle_watched_widget = root
    renderer._sfle_mounted_root = SimpleNamespace(disposed=False)
    renderer._sfle_constraints = LayoutConstraints(
        AvailableSize(1024, True), AvailableSize(768, True),
    )
    renderer.commit_layout = lambda _: pytest.fail("Unexpected recompute")
    renderer._sfle_sync_attached_viewport()
