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


from tests.certification.tk_public_driver import (
    click, configured_font_size, control, enabled, keyboard, native_font, view,
)


# Every getter interrogates the real Tk widget/font/canvas; no handle.props proof.
PROPERTY_CASES = [
    ("Text", "value", "Before", "After", lambda w: str(w.cget("text"))),
    ("Text", "font_size", 16, 22, configured_font_size),
    ("Text", "bold", False, True, lambda w: native_font(w).actual("weight") == "bold"),
    ("Text", "italic", False, True, lambda w: native_font(w).actual("slant") == "italic"),
    ("Text", "color", "#123456", "#654321", lambda w: str(w.cget("foreground"))),
    ("Text", "align", "left", "right", lambda w: str(w.cget("justify"))),
    ("Button", "font_size", 14, 22, configured_font_size),
    ("Input", "password", False, True, lambda w: bool(w.cget("show"))),
    ("Input", "read_only", False, True, lambda w: str(w.cget("state")) == "readonly"),
    ("Input", "font_size", 14, 22, configured_font_size),
    ("Input", "placeholder", "Hint", "New hint", lambda w: str(w._psx_hint_label.cget("text"))),
    ("TextArea", "value", "Before", "After", lambda w: w.get("1.0", "end-1c")),
    ("TextArea", "read_only", False, True, lambda w: str(w.cget("state")) == "disabled"),
    ("TextArea", "font_size", 14, 22, configured_font_size),
    ("Slider", "min", 0, -10, lambda w: float(w.cget("from"))),
    ("Slider", "max", 100, 200, lambda w: float(w.cget("to"))),
    ("Slider", "value", 0, 50, lambda w: float(w.get())),
    ("Slider", "orientation", "horizontal", "vertical", lambda w: str(w.cget("orient"))),
    ("Radio", "label", "Before", "After", lambda w: str(w.cget("text"))),
    ("ProgressBar", "value", 0, 50, lambda w: float(w.cget("value"))),
    ("ProgressBar", "max", 100, 200, lambda w: float(w.cget("maximum"))),
    ("ProgressBar", "orientation", "horizontal", "vertical", lambda w: str(w.cget("orient"))),
    ("ProgressBar", "indeterminate", False, True, lambda w: str(w.cget("mode")) == "indeterminate"),
    ("Select", "placeholder", "Hint", "New hint", lambda w: w.get()),
    ("Link", "label", "Before", "After", lambda w: str(w.cget("text"))),
    ("Link", "color", "#123456", "#654321", lambda w: str(w.cget("foreground"))),
    ("Link", "underline", True, False, lambda w: bool(native_font(w).actual("underline"))),
]
PROPERTY_CASES += [(name, "enabled", True, False, enabled) for name in
                   ("Text", "Button", "Checkbox", "Input", "TextArea", "Slider", "Radio", "ProgressBar", "Select")]


@pytest.mark.parametrize("name,prop,before,after,read", PROPERTY_CASES,
                         ids=[f"{c[0]}-{c[1]}" for c in PROPERTY_CASES])
def test_tk_nonlayout_property_native_observation(tk_tree, request, name, prop, before, after, read):
    root, _, tree = tk_tree
    initial = tree.render(view(name, **{prop: before}))
    widget = initial.children[0].handle.widget
    root.update()
    assert read(widget) == before
    updated = tree.render(view(name, **{prop: after}))
    root.update()
    assert updated.children[0].handle.widget is widget
    for scenario in ("live_update", "native_readback"):
        assert_feature(request, Feature(name, "tkinter", "property", prop, scenario,
                                        applicability="native"), read(widget) == after)


@pytest.mark.parametrize("name,event", [("Button", "on_click"), ("Checkbox", "on_change"),
                                         ("Switch", "on_change"), ("Link", "on_click"),
                                         ("Input", "on_change"), ("Input", "on_submit"),
                                         ("TextArea", "on_change"), ("Slider", "on_change"),
                                         ("SpinBox", "on_change")])
def test_tk_real_event_rebinding_disabled_and_teardown(tk_tree, request, name, event):
    root, _, tree = tk_tree
    calls = []
    def render(tag, **props):
        return tree.render(view(name, **{event: lambda *args: calls.append((tag, args)), **props}))
    mounted = render("first")
    widget = mounted.children[0].handle.widget
    root.update()
    def interact():
        if name == "Switch":
            click(root, widget._psx_canvas)
        elif name == "SpinBox":
            click(root, widget._psx_parts[2])
        elif name in ("Button", "Checkbox", "Link", "Slider"):
            click(root, widget)
        elif event == "on_submit":
            keyboard(root, widget, "<Return>")
        else:
            keyboard(root, widget, "<KeyPress-a>")
    interact()
    if name == "Slider":
        assert len(calls) == 1 and len(calls[0][1]) == 1
        assert isinstance(calls[0][1][0], float) and 0 < calls[0][1][0] <= 100
        expected_payload = calls[0][1]
    else:
        expected_payload = (() if event == "on_click" or event == "on_submit" else
                        (True,) if name in ("Checkbox", "Switch") else ("a",))
    if name == "SpinBox":
        expected_payload = (1,)
    assert_feature(request, Feature(name, "tkinter", "event", event, "native_dispatch", applicability="native"),
                   calls == [("first", expected_payload)])
    assert_feature(request, Feature(name, "tkinter", "event", event, "payload", applicability="native"),
                   calls[0][1] == expected_payload)
    updated = render("second")
    assert updated.children[0].handle.widget is widget
    interact()
    assert_feature(request, Feature(name, "tkinter", "event", event, "rebind", applicability="native"),
                   len(calls) == 2 and calls[-1][0] == "second")
    render("disabled", enabled=False)
    old = list(calls)
    interact()
    assert_feature(request, Feature(name, "tkinter", "event", event, "disabled", applicability="native"), calls == old)
    if name in ("Button", "Checkbox", "Switch", "Slider", "Input") and event != "on_submit":
        assert_feature(request, Feature(name, "tkinter", "interaction",
                                        "enabled__" + event, "paired_native", applicability="native"), calls == old)
    tree.unmount()
    root.update()
    assert_feature(request, Feature(name, "tkinter", "event", event, "teardown", applicability="native"),
                   not widget.winfo_exists() and calls == old)


def test_tk_textarea_controlled_update_while_locked(tk_tree):
    root, _, tree = tk_tree
    for lock in ({"enabled": False}, {"read_only": True}):
        mounted = tree.render(view("TextArea", value="before", **lock))
        widget = mounted.children[0].handle.widget
        tree.render(view("TextArea", value="after", **lock))
        root.update()
        assert widget.get("1.0", "end-1c") == "after"
        keyboard(root, widget, "<KeyPress-a>")
        assert widget.get("1.0", "end-1c") == "after"
        tree.unmount()


@pytest.mark.parametrize("name", ["Text", "Button", "Checkbox", "Input", "TextArea",
                                  "Slider", "Radio", "ProgressBar", "Select", "Link",
                                  "Switch", "Badge", "Divider", "Spacer", "SpinBox"])
def test_tk_native_leaf_lifecycle(tk_tree, request, name):
    root, _, tree = tk_tree
    mounted = tree.render(Flex(control(name), control(name, key="other"),
                               width="400px", height="120px", align_items="flex-start"))
    first, second = (child.handle.widget for child in mounted.children)
    root.update()
    assert_feature(request, Feature(name, "tkinter", "lifecycle", "mount", "native_behavior", applicability="native"),
                   first.winfo_exists() and second.winfo_exists() and first.winfo_ismapped())
    updated = tree.render(Flex(control(name), control(name, key="other"),
                               width="400px", height="120px", align_items="flex-start"))
    assert_feature(request, Feature(name, "tkinter", "lifecycle", "update", "native_behavior", applicability="native"),
                   updated.children[0].handle.widget is first and updated.children[1].handle.widget is second)
    reordered = tree.render(Flex(control(name, key="other"), control(name),
                                 width="400px", height="120px", align_items="flex-start"))
    root.update()
    assert_feature(request, Feature(name, "tkinter", "lifecycle", "reorder", "native_behavior", applicability="native"),
                   reordered.children[0].handle.widget is second and reordered.children[1].handle.widget is first
                   and second.winfo_x() < first.winfo_x())
    tree.unmount()
    root.update()
    assert_feature(request, Feature(name, "tkinter", "lifecycle", "unmount", "native_behavior", applicability="native"),
                   not first.winfo_exists() and not second.winfo_exists())


@pytest.mark.parametrize("name", ["Input", "TextArea"])
def test_tk_read_only_prevents_native_edit_event(tk_tree, request, name):
    root, _, tree = tk_tree
    calls = []
    mounted = tree.render(view(name, value="original", read_only=True, on_change=calls.append))
    widget = mounted.children[0].handle.widget
    root.update()
    keyboard(root, widget, "<KeyPress-a>")
    read = widget.get() if name == "Input" else widget.get("1.0", "end-1c")
    assert_feature(request, Feature(name, "tkinter", "interaction", "read_only__on_change",
                                    "paired_native", applicability="native"), read == "original" and calls == [])


def test_tk_password_and_placeholder_preserve_value(tk_tree, request):
    root, _, tree = tk_tree
    calls = []
    mounted = tree.render(view("Input", placeholder="Hint", password=True, on_change=calls.append))
    widget = mounted.children[0].handle.widget
    root.update()
    assert widget.get() == "" and widget._psx_hint_label.winfo_ismapped()
    tree.render(view("Input", value="secret", placeholder="New hint", password=True, on_change=calls.append))
    root.update()
    assert_feature(request, Feature("Input", "tkinter", "interaction", "password__value", "paired_native", applicability="native"),
                   widget.get() == "secret" and str(widget.cget("show")) == "*" and calls == [])
    assert_feature(request, Feature("Input", "tkinter", "interaction", "placeholder__value", "paired_native", applicability="native"),
                   widget.get() == "secret" and not widget._psx_hint_label.winfo_ismapped() and calls == [])
