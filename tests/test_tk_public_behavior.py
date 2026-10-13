"""Executable Tk native readback and update evidence, not inferred coverage."""
from __future__ import annotations

import tkinter as tk

import pytest

from psx import Button, Checkbox, Flex, Input
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature


@pytest.fixture
def tk_tree():
    root = tk.Tk()
    root.geometry("400x120+0+0")
    root.update_idletasks()
    constraints = LayoutConstraints(AvailableSize(400, True),
                                    AvailableSize(120, True))
    renderer = TkinterRenderer(root=root, sfle_constraints=constraints,
                               engine=PythonLayoutEngine())
    tree = Reconciler(renderer)
    try:
        yield root, renderer, tree
    finally:
        tree.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.parametrize(("name", "before", "after", "read"),
                         [
                             ("Button", "Before", "After", lambda w: w.cget("text")),
                             ("Checkbox", False, True,
                              lambda w: bool(w._psx_variable.get())),
                             ("Input", "Before", "After", lambda w: w.get()),
                         ])
def test_tk_control_native_update_and_readback(tk_tree, request, name, before, after, read):
    root, renderer, tree = tk_tree
    def view(value):
        options = {"key": "control", "layout_width": "160px",
                   "layout_height": "32px", "flex_basis": "160px", "flex_shrink": 0}
        if name == "Button":
            child = Button(value, **options)
        elif name == "Checkbox":
            child = Checkbox(checked=value, **options)
        else:
            child = Input(value=value, **options)
        return Flex(child, width="400px", height="120px", align_items="flex-start")

    first = tree.render(view(before))
    widget = first.children[0].handle.widget
    assert read(widget) == before
    updated = tree.render(view(after))
    root.update_idletasks()
    assert updated.children[0].handle.widget is widget
    prop = {"Button": "label", "Checkbox": "checked", "Input": "value"}[name]
    for scenario in ("live_update", "native_readback"):
        assert_feature(request, Feature(name, "tkinter", "property", prop,
                                        scenario, applicability="native"),
                       read(widget) == after)
    assert renderer.sfle_result.geometry_commit_error <= 1
