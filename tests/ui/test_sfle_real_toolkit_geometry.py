"""F2 UI certification against live native widget instances.

No production renderer is claimed migrated: this tests the existing pure
SFLE -> NativeGeometryCommitter -> widget read-back adapter boundary and the
real Tk/Kivy measurement sources. Qt real QLabel worker convergence is
separately enforced by SFLE Core and the installed Rust wheel jobs.
"""
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tests"/"sfle"))
from test_f2_acceptance_contract_red import case_snapshot  # noqa: E402

from psx.sfle.engine import PythonLayoutEngine  # noqa: E402
from psx.sfle.native_geometry import NativeGeometryCommitter, GeometryBackend  # noqa: E402
from psx.sfle.model import AvailableSize, LayoutConstraints  # noqa: E402
from psx.sfle.measurement_plan import MeasurementRequest  # noqa: E402
from psx.sfle.kivy_measurement import KivyMeasurementSource  # noqa: E402
from psx.sfle.tk_measurement import TkMeasurementSource  # noqa: E402


def sfle_case(case_id):
    snapshot=case_snapshot(case_id)
    result=PythonLayoutEngine().compute(snapshot)
    nodes=tuple(SimpleNamespace(node_id=n.node_id,parent_id=n.parent_id)
                for n in snapshot.nodes)
    parents={n.node_id:n.parent_id for n in snapshot.nodes}
    rects={node_id:box.border for node_id,box in result.boxes}
    return nodes,parents,rects,result


def check_widget_coordinates(backend,parents,rects,observed):
    assert set(observed)==set(rects)-{next(n for n,p in parents.items() if p is None)}
    for node_id,actual in observed.items():
        rect=rects[node_id]
        parent=rects[parents[node_id]]
        x=rect.x-parent.x
        y=rect.y-parent.y
        if backend==GeometryBackend.KIVY:
            y=parent.height-y-rect.height
        for axis,want,got in zip(("x","y","width","height"),
                                (x,y,rect.width,rect.height),actual):
            assert abs(want-got)<=1.0,(
                backend,node_id,axis,"SFLE",want,"native widget readback",got,
            )


@pytest.mark.parametrize("case_id",("A01","F01","N05"))
def test_qt_real_nested_widget_geometry(case_id):
    from PySide6 import QtWidgets
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    nodes,parents,rects,result=sfle_case(case_id)
    root_id=next(node for node,p in parents.items() if p is None)
    root=QtWidgets.QWidget()
    root.setGeometry(0,0,round(rects[root_id].width),round(rects[root_id].height))
    widgets={root_id:root}
    try:
        for node in nodes[1:]:
            widgets[node.node_id]=QtWidgets.QWidget(widgets[node.parent_id])
        root.show()
        NativeGeometryCommitter(
            GeometryBackend.QT,nodes,
            {name:widget for name,widget in widgets.items() if name!=root_id},
        )(result)
        for widget in widgets.values():
            widget.show()
        app.processEvents()
        observed={}
        for name,widget in widgets.items():
            if name!=root_id:
                rectangle=widget.geometry()
                observed[name]=(rectangle.x(),rectangle.y(),
                                rectangle.width(),rectangle.height())
        check_widget_coordinates(GeometryBackend.QT,parents,rects,observed)
    finally:
        root.close()
        root.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("case_id",("A01","F01","N05"))
def test_tk_real_nested_frame_geometry(case_id):
    import tkinter as tk
    nodes,parents,rects,result=sfle_case(case_id)
    root_id=next(node for node,p in parents.items() if p is None)
    root=tk.Tk()
    root.geometry(f"{round(rects[root_id].width)}x{round(rects[root_id].height)}+20+20")
    widgets={root_id:root}
    try:
        for node in nodes[1:]:
            widgets[node.node_id]=tk.Frame(widgets[node.parent_id])
        NativeGeometryCommitter(
            GeometryBackend.TK,nodes,
            {name:widget for name,widget in widgets.items() if name!=root_id},
        )(result)
        root.update_idletasks()
        root.update()
        observed={
            name:(widget.winfo_x(),widget.winfo_y(),
                  widget.winfo_width(),widget.winfo_height())
            for name,widget in widgets.items() if name!=root_id
        }
        check_widget_coordinates(GeometryBackend.TK,parents,rects,observed)
    finally:
        root.destroy()


@pytest.mark.parametrize("case_id",("A01","F01","N05"))
def test_kivy_real_window_nested_widget_geometry(case_id):
    from kivy.core.window import Window
    from kivy.uix.widget import Widget
    assert Window is not None,"Real Kivy SDL2 window provider is required"
    nodes,parents,rects,result=sfle_case(case_id)
    root_id=next(node for node,p in parents.items() if p is None)
    root=Widget(size_hint=(None,None),
                size=(rects[root_id].width,rects[root_id].height),pos=(0,0))
    widgets={root_id:root}
    Window.add_widget(root)
    try:
        for node in nodes[1:]:
            widget=Widget(size_hint=(None,None))
            widgets[node.node_id]=widget
            widgets[node.parent_id].add_widget(widget)
        NativeGeometryCommitter(
            GeometryBackend.KIVY,nodes,
            {name:widget for name,widget in widgets.items() if name!=root_id},
        )(result)
        observed={
            name:(*widget.pos,*widget.size)
            for name,widget in widgets.items() if name!=root_id
        }
        check_widget_coordinates(GeometryBackend.KIVY,parents,rects,observed)
    finally:
        Window.remove_widget(root)


def test_tk_real_wrap_measurement_keeps_original_widget_state():
    import tkinter as tk
    root=tk.Tk()
    try:
        label=tk.Label(root,text="wrap "*70,wraplength=400)
        label.pack()
        root.update_idletasks()
        source=TkMeasurementSource({"text":label})
        before=label.cget("wraplength")
        narrow=source.measure_width("text",60.0)
        wide=source.measure_width("text",220.0)
        assert narrow.preferred_height >= wide.preferred_height
        assert label.cget("wraplength")==before
        request=MeasurementRequest("text",LayoutConstraints(
            AvailableSize(60,True),AvailableSize(None,False),
        ), 19, 2)
        measured=source.port().measure(request)
        assert measured.revision==2 and measured.constraints==request.constraints
    finally:
        root.destroy()


def test_kivy_real_label_texture_measurement_preserves_text_size():
    from kivy.core.window import Window
    from kivy.uix.label import Label
    assert Window is not None
    label=Label(text="wrap "*70,font_size=14)
    label.texture_update()
    source=KivyMeasurementSource({"text":label})
    original=label.text_size
    narrow=source.measure_width("text",60.0)
    wide=source.measure_width("text",220.0)
    assert narrow.preferred_height >= wide.preferred_height
    assert label.text_size==original
    request=MeasurementRequest("text",LayoutConstraints(
        AvailableSize(60,True),AvailableSize(None,False),
    ),19,2)
    measured=source.port().measure(request)
    assert measured.revision==2 and measured.constraints==request.constraints
