"""Native Grid root commit must avoid unchanged writes without skipping placement."""
import pytest

from psx.sfle.grid_native_commit import GridCommitBackend
from psx.sfle.native_grid_bridge import root_geometry_changed


@pytest.mark.parametrize("backend", (GridCommitBackend.QT, GridCommitBackend.KIVY))
def test_unchanged_native_root_geometry_does_not_trigger_write(backend):
    desired = (0, 0, 800, 600)
    assert not root_geometry_changed(backend, desired, desired)
    assert root_geometry_changed(backend, (0, 0, 801, 600), desired)


@pytest.mark.parametrize("previous,changed", (
    ({"x": "0", "y": "0", "width": "800", "height": "600"}, False),
    ({"x": "0", "y": "0", "width": "801", "height": "600"}, True),
    ({}, True),
    ({"x": "0", "y": "0", "width": "", "height": ""}, True),
))
def test_tk_root_auto_geometry_never_raises_and_never_skips_placement(previous, changed):
    assert root_geometry_changed(GridCommitBackend.TK, previous, (0, 0, 800, 600)) is changed
