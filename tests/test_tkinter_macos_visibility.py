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
def test_aqua_empty_grid_does_not_draw_native_border_under_details():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(420, True), AvailableSize(180, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #0000ff">
                <div><h3>Detalles</h3><Grid gap="16px"></Grid></div>
            </div>
        """))
        root.update()
        empty_grid = mounted.children[0].children[1].handle.widget
        assert isinstance(empty_grid, tk.Frame)
        assert str(empty_grid.cget("background")) == "#0000ff"
        assert int(empty_grid.cget("borderwidth")) == 0
        assert int(empty_grid.cget("highlightthickness")) == 0
        assert not getattr(empty_grid, "_psx_css_side_borders", None)
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_grid_gaps_use_ancestor_css_background():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(540, True), AvailableSize(280, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #0000ff">
              <div><Grid gap="16px">
                <GridItem span="6"><div style="background: #ffffff">A</div></GridItem>
                <GridItem span="6"><div style="background: #ffffff">B</div></GridItem>
              </Grid></div>
            </div>
        """))
        root.update()
        grid = mounted.children[0].children[0]
        for instance in (grid, *grid.children):
            widget = instance.handle.widget
            assert getattr(widget, "_psx_css_layout_surface", False)
            assert isinstance(widget, tk.Frame)
            assert str(widget.cget("background")) == "#0000ff"
            assert int(widget.cget("borderwidth")) == 0
            assert int(widget.cget("highlightthickness")) == 0
        assert str(grid.children[0].children[0].handle.widget._psx_css_background) == "#ffffff"
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_card_corners_have_single_fill_and_explicit_border_color():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(350, True), AvailableSize(170, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #0000ff">
              <div style="background: #ffffff; border: 1px solid #e0e0e0;
                          border-radius: 8px">Card</div>
            </div>
        """))
        root.update()
        card = mounted.children[0].handle.widget
        corners = card._psx_css_background_corners
        assert len(corners) == 4
        assert not hasattr(card, "_psx_css_border_corners")
        for corner in corners:
            assert corner.cget("background") == "#0000ff"
            items = corner.find_all()
            assert len(items) == 2
            assert corner.itemcget(items[0], "fill") == "#e0e0e0"
            assert corner.itemcget(items[1], "fill") == "#ffffff"
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_unstyled_details_do_not_acquire_header_bottom_border():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(380, True), AvailableSize(220, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #0000ff">
              <div key="header" style="border-bottom: 1px solid #cccccc">Header</div>
              <div key="details"><h3>Detalles</h3></div>
              <div key="activity"><p style="border-bottom: 1px solid #cccccc">Row</p></div>
            </div>
        """))
        root.update()
        header, details, activity = mounted.children
        assert set(header.handle.widget._psx_css_side_borders) == {"bottom"}
        assert not getattr(details.handle.widget, "_psx_css_side_borders", None)
        assert not getattr(details.children[0].handle.widget, "_psx_css_side_borders", None)
        assert set(activity.children[0].handle.widget._psx_css_side_borders) == {"bottom"}
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires live macOS Aqua WindowServer")
def test_aqua_unstyled_nested_blocks_expose_nearest_css_surface():
    root = tk.Tk()
    renderer = TkinterRenderer(root=root, sfle_constraints=LayoutConstraints(
        AvailableSize(480, True), AvailableSize(300, True)),
        engine=PythonLayoutEngine())
    reconciler = Reconciler(renderer)
    try:
        mounted = reconciler.render(psx("""
            <div style="background: #ff0000">
                <div class="container"><div class="details">
                    <h3>Detalles</h3>
                </div></div>
                <div style="background: #ffffff"><p>Tarjeta</p></div>
            </div>
        """))
        root.update()
        host = mounted.children[0].handle.widget
        nested = mounted.children[0].children[0].handle.widget
        assert host._psx_css_background is None
        assert nested._psx_css_background is None
        assert str(host._psx_css_fill_canvas.cget("background")) == "#ff0000"
        assert str(nested._psx_css_fill_canvas.cget("background")) == "#ff0000"
    finally:
        reconciler.unmount()
        renderer.close()
        root.destroy()


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
        assert isinstance(button._psx_css_button_paint, tk.Canvas)
        assert button._psx_css_button_paint.winfo_manager() == "place"
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
