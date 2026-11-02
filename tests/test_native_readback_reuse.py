"""Certified native readback without redundant Qt/Tcl property queries."""
from types import SimpleNamespace

import pytest

from psx.layout.adapters.native_readback_reuse import readback_reusing_prior
from psx.layout.contracts.tree_identity import LayoutTreeIdentity


def tree():
    return (
        LayoutTreeIdentity("root", None),
        LayoutTreeIdentity("child", "root"),
        LayoutTreeIdentity("nested", "child"),
    )


def test_qt_unchanged_widget_reuses_same_native_rollback_read():
    handles = {name: SimpleNamespace(widget=SimpleNamespace())
               for name in ("root", "child", "nested")}
    calls = []

    def read(node_id, _handle):
        calls.append(node_id)
        return {"x": 0, "y": 0, "width": 1, "height": 1}

    prior = {
        "child": (10, 20, 30, 40),
        "nested": (1, 2, 3, 4),
    }
    out = readback_reusing_prior(
        "qt", tree(), handles, prior, frozenset(),
        frozenset(), read,
    )
    assert calls == ["root"]
    assert out["child"] == dict(x=10.0, y=20.0, width=30.0, height=40.0)
    assert out["nested"] == dict(x=1.0, y=2.0, width=3.0, height=4.0)


def test_qt_mutated_and_external_widgets_are_always_live_read():
    handles = {name: SimpleNamespace(widget=SimpleNamespace())
               for name in ("root", "child", "nested")}
    calls = []
    readback_reusing_prior(
        "qt", tree(), handles,
        {"child": (10, 20, 30, 40), "nested": (1, 2, 3, 4)},
        frozenset({"child"}), frozenset({"nested"}),
        lambda node_id, _widget: calls.append(node_id) or {},
    )
    assert calls == ["root", "child", "nested"]


def test_tk_explicit_place_reads_once_but_relative_placement_must_be_live():
    handles = {name: SimpleNamespace()
               for name in ("root", "child", "nested")}
    calls = []
    prior = {
        "child": {"x": "12", "y": "3", "width": "40", "height": "20",
                  "relx": "0", "rely": "0", "relwidth": "0", "relheight": "0"},
        "nested": {"x": "0", "y": "0", "width": "30", "height": "20",
                   "relwidth": "0.5"},
    }
    out = readback_reusing_prior(
        "tk", tree(), handles, prior, frozenset(), frozenset(),
        lambda node_id, _handle: calls.append(node_id) or {"live": 1},
    )
    assert calls == ["root", "nested"]
    assert out["child"] == dict(x=12.0, y=3.0, width=40.0, height=20.0)
    assert out["nested"] == {"live": 1}


def test_native_scroll_clips_deferred_readback_to_real_port():
    scroll = SimpleNamespace(_psx_sfle_scroll=True)
    handles = {
        "root": SimpleNamespace(widget=SimpleNamespace()),
        "child": SimpleNamespace(widget=scroll),
        "nested": SimpleNamespace(widget=SimpleNamespace()),
    }
    calls = []
    readback_reusing_prior(
        "qt", tree(), handles,
        {"child": (0, 0, 100, 80), "nested": (0, 0, 100, 200)},
        frozenset(), frozenset(),
        lambda node_id, _handle: calls.append(node_id) or {},
    )
    assert calls == ["root", "child", "nested"]


def test_kivy_never_uses_sync_only_qt_tk_fast_path():
    handles = {name: SimpleNamespace()
               for name in ("root", "child", "nested")}
    reads = []
    readback_reusing_prior(
        "kivy", tree(), handles,
        {"child": ((0, 0), (30, 40)), "nested": ((1, 1), (2, 2))},
        frozenset(), frozenset(),
        lambda node_id, _handle: reads.append(node_id) or {},
    )
    assert reads == ["root", "child", "nested"]


@pytest.mark.parametrize("backend", ("other", "", "QT"))
def test_invalid_backend_is_never_silently_assumed(backend):
    with pytest.raises(ValueError):
        readback_reusing_prior(
            backend, (), {}, {}, frozenset(), frozenset(),
            lambda *_: {},
        )
