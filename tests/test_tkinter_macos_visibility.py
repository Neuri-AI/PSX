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
def test_aqua_dashboard_semantic_root_and_grid_are_mapped():
    window = tk.Tk()
    window.geometry("800x500+50+50")
    window.update()
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
                    <GridItem span={{"base": 3, "md": 3, "lg": 2}}>
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
        assert any(isinstance(w, ttk.Label) and w.winfo_ismapped() for w in native)
        assert sum(isinstance(w, ttk.Frame) and w.winfo_ismapped() for w in native) >= 3
    finally:
        reconciler.unmount()
        renderer.close()
        window.destroy()
