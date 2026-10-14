"""F2 native border geometry readback / single-authority adversarial checks.

Native Qt/Tk/Kivy coordinate conversion consumes real SFLE result rectangles.
These are fake toolkit handles; real Qt UI lifecycle is certified separately.
Production F3 renderers are NOT represented by these doubles.
"""
from dataclasses import replace
from types import SimpleNamespace
import threading

import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.worker_lifecycle import start_native_worker_layout
from test_acceptance_contract_regression import case_snapshot
from test_native_worker_portable_regression import _UIQueue, _source


class QtWidget:
    def __init__(self): self.rect=None
    def setGeometry(self,*values): self.rect=values


class TkWidget:
    def __init__(self): self.rect=None
    def place(self,**values):
        self.rect=tuple(values[name] for name in ("x","y","width","height"))


class KivyWidget:
    def __init__(self): self.pos=None; self.size=None


@pytest.mark.parametrize("case_id", ("A01","F01","N05"))
@pytest.mark.parametrize("backend",tuple(GeometryBackend))
def test_native_toolkit_coordinates_are_only_projections_of_sfle_rectangles(case_id,backend):
    snapshot=case_snapshot(case_id)
    result=PythonLayoutEngine().compute(snapshot)
    parents={node.node_id:node.parent_id for node in snapshot.nodes}
    # NativeGeometryCommitter intentionally accepts immutable node/parent
    # shape only. The real solver owns *all* sizes/positions.
    nodes=tuple(SimpleNamespace(node_id=node.node_id,parent_id=node.parent_id)
                for node in snapshot.nodes)
    factory={
        GeometryBackend.QT: QtWidget,
        GeometryBackend.TK: TkWidget,
        GeometryBackend.KIVY: KivyWidget,
    }[backend]
    widgets={name:factory() for name,parent in parents.items() if parent is not None}
    NativeGeometryCommitter(backend,nodes,widgets)(result)
    boxes={name:box.border for name,box in result.boxes}
    assert set(widgets)==set(parents)-{snapshot.nodes[0].node_id}
    for name,widget in widgets.items():
        child,parent=boxes[name],boxes[parents[name]]
        x=child.x-parent.x
        y=child.y-parent.y
        if backend==GeometryBackend.KIVY:
            y=parent.height-y-child.height
            actual=(*widget.pos,*widget.size)
        else:
            actual=widget.rect
        for expected,observed in zip((x,y,child.width,child.height),actual):
            assert abs(expected-observed)<=1.0,(case_id,backend,name,expected,observed)


def test_native_layout_recomputation_is_detected_and_rolled_back():
    """Even a valid SFLE result cannot authorize a second native flex solver."""
    ui=_UIQueue()
    snapshot=replace(case_snapshot("A04"),measurements=())
    engine=PythonLayoutEngine()
    source=_source("headless")
    observed={"text":{"x":3.0,"y":7.0,"width":19.0,"height":11.0}}
    original={key:dict(rect) for key,rect in observed.items()}
    outcomes=[]
    native_calls=[]

    def measure(node_id,width):
        request=MeasurementRequest(
            node_id,LayoutConstraints(
                AvailableSize(width,True),AvailableSize(None,False)
            ),snapshot.generation,0,
        )
        return source.port().measure(request).intrinsic

    def apply_with_illegal_layout(result):
        native_calls.append(1)
        rect=dict(result.boxes)["text"].border
        # Simulates a native BoxLayout/pack engine overriding the SFLE width.
        observed["text"]={
            "x":rect.x,"y":rect.y,"width":rect.width-5.0,"height":rect.height,
        }

    def restore(before):
        observed.clear()
        observed.update({key:dict(rect) for key,rect in before.items()})

    handle=start_native_worker_layout(
        snapshot, compute=engine.compute, provisional=engine.compute_provisional,
        measure_on_ui=measure,
        is_ui_thread=lambda:threading.get_ident()==ui.thread,
        current_generation=lambda:snapshot.generation,
        apply_geometry=apply_with_illegal_layout,
        observed_geometry=lambda:{key:dict(rect) for key,rect in observed.items()},
        restore_geometry=restore,
        initial_widths={"text":100.0},
        post_to_ui=ui.post,
        on_finished=lambda result,error:outcomes.append((result,error)),
        nodes_alive=lambda ids:set(ids)=={"root","text"},
    )
    ui.drain(handle)
    assert native_calls==[1]
    assert len(outcomes)==1
    result,error=outcomes[0]
    assert result is None and isinstance(error,SFLEError)
    assert error.code is DiagnosticCode.UNSUPPORTED_MEASUREMENT
    assert observed==original
