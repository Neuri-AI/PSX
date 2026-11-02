"""Real native-commit core exercised with Qt/Tk/Kivy-compatible widget ports.

The test intentionally changes widths of 30 cards in a complete solver batch.
Only proven offscreen cards may avoid native setters, and those cards must
receive their newest geometry as soon as the viewport grows to include them.
"""
import pytest

from psx.layout.adapters.grid_native_commit import (
    GridCommitBackend, commit_grid_native_geometry,
)
from psx.layout.adapters.grid_viewport_workset import GridViewportWorkset
from psx.layout.grid.grid_native_plan import GridNativePlacement


class _QtRect:
    def __init__(self, coords):
        self.coords = coords
    def x(self): return self.coords[0]
    def y(self): return self.coords[1]
    def width(self): return self.coords[2]
    def height(self): return self.coords[3]


class _QtWidget:
    def __init__(self):
        self.value, self.writes = (0, 0, 0, 0), 0
    def geometry(self):
        return _QtRect(self.value)
    def setGeometry(self, *coords):
        self.value = tuple(coords)
        self.writes += 1


class _TkWidget:
    def __init__(self):
        self.value, self.writes = None, 0
    def place_info(self):
        return (dict(zip(("x", "y", "width", "height"), self.value))
                if self.value is not None else {})
    def place(self, **kwargs):
        self.value = tuple(kwargs[k] for k in ("x", "y", "width", "height"))
        self.writes += 1
    def place_forget(self):
        self.value = None


class _KivyWidget:
    def __init__(self):
        self._pos = (0, 0)
        self._size = (0, 0)
        self.writes = 0
        self.parent = None
    @property
    def pos(self): return self._pos
    @pos.setter
    def pos(self, value):
        self._pos = tuple(value)
        self.writes += 1
    @property
    def size(self): return self._size
    @size.setter
    def size(self, value):
        self._size = tuple(value)
        self.writes += 1


def _batch(roots, width):
    result = []
    for i, root in enumerate(roots):
        result.extend((
            GridNativePlacement(root, 0, i * 40, width, 32,
                                width, 32, False, False),
            GridNativePlacement(root + "/leaf", 0, 0, width, 32,
                                width, 32, False, False),
        ))
    return tuple(result)


@pytest.mark.parametrize("backend,widget_type", [
    (GridCommitBackend.QT, _QtWidget),
    (GridCommitBackend.TK, _TkWidget),
    (GridCommitBackend.KIVY, _KivyWidget),
])
def test_native_offscreen_resize_then_reentry(backend, widget_type):
    roots = tuple(f"card-{i}" for i in range(30))
    widgets = {name: widget_type() for root in roots
               for name in (root, root + "/leaf")}
    workset = GridViewportWorkset()
    epoch = 1
    generation = 0

    def resize(width, viewport_height):
        nonlocal generation
        generation += 1
        batch = _batch(roots, width)
        kwargs = dict(root_ids=roots, batch=batch, widgets=widgets,
                      viewport_height=viewport_height, epoch=epoch,
                      backend=backend, safe_ids=set(roots))
        skipped = workset.plan(**kwargs)
        active = tuple(p for p in batch if p.node_id not in skipped)
        active_widgets = {key: value for key, value in widgets.items()
                          if key not in skipped}
        parent_heights = None
        if backend is GridCommitBackend.KIVY:
            parent_heights = {
                key: (32 if key.endswith("/leaf") else viewport_height)
                for key in active_widgets
            }
        receipt = commit_grid_native_geometry(
            active, backend=backend, widgets=active_widgets,
            generation=generation, current_generation=lambda: generation,
            is_ui_thread=lambda: True,
            parent_height=(float(viewport_height)
                           if backend is GridCommitBackend.KIVY else None),
            parent_heights=parent_heights,
        )
        workset.accept(**kwargs, skipped=skipped)
        return skipped, receipt

    first, _ = resize(200, 100)
    assert first == frozenset()
    before_writes = sum(w.writes for w in widgets.values())

    skipped, receipt = resize(220, 100)
    assert len(skipped) >= 45
    assert len(receipt.node_ids) == 60 - len(skipped)
    assert sum(w.writes for w in widgets.values()) - before_writes < 20

    # The formerly invisible descendants must be committed *before* the
    # enlarged viewport can expose them, with their newest width.
    exposed, _ = resize(220, 1400)
    assert exposed == frozenset()
    for root in roots:
        for name in (root, root + "/leaf"):
            widget = widgets[name]
            if backend is GridCommitBackend.KIVY:
                assert widget.size[0] == 220
            else:
                assert widget.value[2] == 220
