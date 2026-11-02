"""Tkinter CSS form controls: pixels, placeholders and state transitions."""

import tkinter as tk
from tkinter import ttk

import pytest

from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet
from psx.renderers.components.button import apply_tk_button
from psx.renderers.components.input import apply_tk_input, input_props
from psx.renderers.tkinter.tkinter import TkHandle, TkinterRenderer, _tk_input_factory
from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource
from psx.layout.contracts.model import AvailableSize, LayoutConstraints
from psx.layout.runtime.measurement_plan import MeasurementRequest


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No live Tk display: {exc}")
    root.geometry("440x300")
    root.update_idletasks()
    yield root
    root.destroy()


def _rule(css, tag):
    return resolve_style(parse_stylesheet(css), StyleTarget(tag))


def test_placeholder_is_native_text_without_opaque_label(tk_root):
    entry = _tk_input_factory(tk_root)
    entry.pack()
    apply_tk_input(entry, input_props({
        "value": "", "placeholder": "Username",
    }))
    tk_root.update()
    assert entry.var.get() == ""
    assert entry.get() == "Username"
    assert not any(isinstance(w, tk.Label) for w in entry.winfo_children())
    entry.focus_force()
    tk_root.update()
    assert entry.get() == ""
    entry.insert(0, "Fredo")
    tk_root.update()
    assert entry.var.get() == "Fredo"
    assert entry.get() == "Fredo"
    entry.var.set("")
    tk_root.focus_set()
    tk_root.update()
    assert entry.var.get() == ""
    assert entry.get() == "Username"


def test_password_hint_is_not_masked_or_submitted(tk_root):
    entry = _tk_input_factory(tk_root)
    entry.pack()
    apply_tk_input(entry, input_props({
        "value": "", "placeholder": "Password", "password": True,
    }))
    tk_root.update()
    assert entry.var.get() == ""
    assert str(entry.cget("show")) == ""
    entry.focus_force()
    tk_root.update()
    assert entry.get() == ""
    assert str(entry.cget("show")) == "*"
    entry.insert(0, "secret")
    tk_root.update()
    assert entry.var.get() == "secret"


def test_entry_css_background_padding_and_single_rounded_border(tk_root):
    renderer = TkinterRenderer(root=tk_root)
    entry = _tk_input_factory(tk_root)
    entry.pack(fill="x")
    apply_tk_input(entry, input_props({
        "value": "", "placeholder": "Username",
    }))
    rule = _rule(
        "input {padding: 8px; background-color: #f0f0f0; "
        "border: 1px solid #ccc; border-radius: 4px;}", "input"
    )
    renderer.apply_css(TkHandle("Input", entry, {}), rule)
    tk_root.update()
    name = str(entry.cget("style"))
    style = ttk.Style(entry)
    assert style.lookup(name, "fieldbackground") == "#f0f0f0"
    assert tuple(int(v) for v in style.lookup(name, "padding")) == (8, 8, 8, 8)
    assert style.layout(name)[0][1]["border"] == 0
    assert len(entry._psx_css_input_corners) == 4
    assert len(entry._psx_css_border_edges) == 4
    assert entry.var.get() == ""
    assert not any(isinstance(w, tk.Label) for w in entry.winfo_children())
    renderer.close()


def test_css_painted_button_uses_css_padding_not_theme_bezel(tk_root):
    renderer = TkinterRenderer(root=tk_root)
    button = ttk.Button(tk_root)
    apply_tk_button(button, {
        "label": "Sign In", "font_size": 14, "enabled": True,
    })
    button.pack(fill="x")
    rule = _rule(
        "button {padding: 8px; border: none; border-radius: 4px; "
        "background-color: #007bff; color: white;}", "button"
    )
    renderer.apply_css(TkHandle("Button", button, {}), rule)
    tk_root.update()
    name = str(button.cget("style"))
    layout = ttk.Style(button).layout(name)
    assert layout[0][0] == "Button.padding"
    assert tuple(int(v) for v in ttk.Style(button).lookup(name, "padding")) == (8, 8, 8, 8)
    renderer.close()


def test_css_padding_is_not_counted_twice_by_cinnamon(tk_root):
    renderer = TkinterRenderer(root=tk_root)
    for node_type, widget, style_css in (
        ("Input", _tk_input_factory(tk_root),
         "input {padding: 8px; background-color: #f0f0f0;}"),
        ("Button", ttk.Button(tk_root),
         "button {padding: 8px; border: none; background-color: #007bff;}"),
    ):
        if node_type == "Input":
            apply_tk_input(widget, input_props({
                "value": "", "placeholder": "Username",
            }))
        else:
            apply_tk_button(widget, {
                "label": "Sign In", "font_size": 14, "enabled": True,
            })
        widget.pack()
        renderer.apply_css(TkHandle(node_type, widget, {}), _rule(
            style_css, "input" if node_type == "Input" else "button"
        ))
        tk_root.update_idletasks()
        assert widget._psx_css_measured_padding == (8, 8, 8, 8)
        source = TkMeasurementSource({"field": widget})
        constraints = LayoutConstraints(
            AvailableSize(440, True), AvailableSize(300, True)
        )
        measured = source.measure(MeasurementRequest(
            "field", constraints, 1, 1
        )).intrinsic
        assert widget.winfo_reqheight() - measured.preferred_height == 16
        assert widget.winfo_reqwidth() - measured.preferred_width == 16
    renderer.close()
