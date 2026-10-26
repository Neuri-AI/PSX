"""Actual macOS Aqua display regression for the Tkinter Cinnamon renderer."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

import pytest

from psx import psx
from psx.core.reconcile import Reconciler
from psx.renderers.tkinter.tkinter import TkinterRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_scroll_viewport_uses_nested_content_css_background():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(480, True), AvailableSize(300, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div><Grid>
              <GridItem><Scroll direction="vertical" height="100vh">
                <div><div style="height: 100vh; background: #ff0000">
                  <p>Contenido</p>
                </div></div>
              </Scroll></GridItem>
            </Grid></div>
        """))
        root.update()
        canvases = []
        def walk(widget):
            if hasattr(widget, "_psx_scroll_region"):
                canvases.append(widget._psx_canvas)
            for child in widget.winfo_children():
                walk(child)
        walk(root)
        assert canvases
        assert str(canvases[0].cget("background")) == "#ff0000"
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_button_css_color_and_radius_are_instance_painted():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(320, True), AvailableSize(140, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #1f2430">
                <button style="background: #3b6ef5; color: #ffffff;
                    border-radius: 8px; border: none; cursor: pointer">Resumen</button>
            </div>
        """))
        button = mounted.children[0].handle.widget
        assert isinstance(button, tk.Button)
        assert str(button.cget("background")) == "#3b6ef5"
        assert str(button.cget("foreground")) == "#ffffff"
        assert isinstance(button._psx_css_button_paint, tk.Canvas)\n        assert button._psx_css_button_paint.winfo_manager() == "place"
        root.update()
        assert button.winfo_ismapped()
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_original_scroll_griditem_nesting_is_visible():
    window = tk.Tk()
    window.geometry("800x500+50+50")
    # Match Qyro startup: render before the first Tk map/update cycle.
    renderer = TkinterRenderer(
        root=window,
        sfle_constraints=LayoutConstraints(
            AvailableSize(800, True), AvailableSize(500, True)),
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div>
                <Grid gap="0px">
                    <GridItem span="3">
                        <div style="height: 100vh; background: #1f2430">
                            <h5 style="color: #ffffff">Mi panel</h5>
                        </div>
                    </GridItem>
                    <Scroll direction="vertical" height="100vh">
                        <GridItem>
                            <div style="background: #f5f6f8; height: 100vh">
                                <h3>Resumen</h3>
                            </div>
                        </GridItem>
                    </Scroll>
                </Grid>
            </div>
        """))
        window.update()
        assert renderer.sfle_result is not None
        assert mounted.handle.widget.winfo_ismapped()
    finally:
        reconciler.unmount()
        renderer.close()
        window.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_dashboard_semantic_root_and_grid_are_mapped():
    window = tk.Tk()
    window.geometry("800x500+50+50")
    # Match Qyro startup: render before the first Tk map/update cycle.
    renderer = TkinterRenderer(
        root=window,
        sfle_constraints=LayoutConstraints(
            AvailableSize(800, True), AvailableSize(500, True)),
        engine=PythonLayoutEngine(),
    )
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="min-height: 100vh">
                <Grid gap="0px">
                    <GridItem span="3">
                        <div style="height: 100vh; background: #1f2430">
                            <h5 style="color: #ffffff">Mi panel</h5>
                        </div>
                    </GridItem>
                    <GridItem>
                        <Scroll direction="vertical" height="100vh">
                            <div style="background: #f5f6f8; min-height: 100vh">
                                <div style="background: #ffffff">
                                    <h3 style="color: #333333">Resumen</h3>
                                </div>
                            </div>
                        </Scroll>
                    </GridItem>
                </Grid>
            </div>
        """))
        window.update()
        assert renderer.sfle_result is not None
        assert mounted.handle.widget.winfo_ismapped()
        assert mounted.handle.widget.winfo_width() > 100
        native = []
        def collect(widget):
            native.append(widget)
            for child in widget.winfo_children():
                collect(child)
        collect(window)
        assert any(isinstance(w, (tk.Label, ttk.Label)) and w.winfo_ismapped() for w in native)
        assert sum(isinstance(w, ttk.Frame) and w.winfo_ismapped() for w in native) >= 3
    finally:
        reconciler.unmount()
        renderer.close()
        window.destroy()
