"""Tk layout commits must not reconfigure unchanged wrapping widths."""
from __future__ import annotations

import pytest

from psx.renderers.tkinter.cinnamon_tkinter_layout_bridge import (
    _apply_wraplength_if_changed,
)


class FakeTkLabel:
    def __init__(self):
        self.calls = []

    def configure(self, **options):
        self.calls.append(options)


@pytest.mark.parametrize("previous", ("120", 120, 120.0))
def test_no_tcl_command_for_unchanged_wraplength(previous):
    widget = FakeTkLabel()
    assert _apply_wraplength_if_changed(widget, previous, 120) is False
    assert widget.calls == []


def test_width_change_reconfigures_once_without_extra_reads():
    widget = FakeTkLabel()
    assert _apply_wraplength_if_changed(widget, "120", 140) is True
    assert widget.calls == [{"wraplength": 140}]


@pytest.mark.parametrize("previous", ("", "auto", None, float("inf")))
def test_unrecognized_prior_wraplength_fails_open_to_native_configure(previous):
    widget = FakeTkLabel()
    assert _apply_wraplength_if_changed(widget, previous, 10) is True
    assert widget.calls == [{"wraplength": 10}]
