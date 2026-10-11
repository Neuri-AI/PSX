"""RED F2.2.4.7: portable Qt-equivalent worker/UI/native commit lifecycle.

This executes the REAL Python SFLE engine in an OS worker, routes each
native measurement through each existing toolkit's NativeMeasurementPort,
uses generation-safe atomic commit+observation and independently checked
D-F1.11 geometry_commit_error. Fake host widgets exercise the adapters'
contracts without pretending an actual Kivy/Tk window is being rendered.
"""
from collections import deque
from dataclasses import replace
import threading
import time
import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from psx.sfle.worker_lifecycle import start_native_worker_layout
from psx.sfle.kivy_measurement import KivyMeasurementSource
from psx.sfle.tk_measurement import TkMeasurementSource
from psx.sfle.headless_measurement import HeadlessMeasurementSource
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, IntrinsicSizes,
)
from test_f2_acceptance_contract_red import case_snapshot


class _KivyLabel:
    texture_size = (100, 40)


class _TkLabel:
    def winfo_reqwidth(self): return 100
    def winfo_reqheight(self): return 40


def _source(backend):
    if backend == "kivy":
        return KivyMeasurementSource({"text": _KivyLabel()})
    if backend == "tk":
        return TkMeasurementSource({"text": _TkLabel()})
    if backend == "headless":
        return HeadlessMeasurementSource(((
            "text", IntrinsicSizes(0, 100, 20, 40, 100, 40),
        ),))
    raise AssertionError(f"unknown source: {backend}")


class _UIQueue:
    def __init__(self):
        self.thread = threading.get_ident()
        self.pending = deque()

    def post(self, callback):
        assert threading.get_ident() == self.thread
        self.pending.append(callback)

    def drain(self, handle, *, timeout=5.0):
        deadline=time.monotonic()+timeout
        while not handle.done() and time.monotonic()<deadline:
            if self.pending:
                self.pending.popleft()()
            else:
                time.sleep(0.001)
        assert handle.done(), "Worker/UI handshake timed out"
        assert not self.pending, "Unexpected post-completion UI callback"


@pytest.mark.parametrize("backend", ("kivy","tk","headless"))
def test_native_worker_routes_measurements_to_ui_and_commits_once(backend):
    ui = _UIQueue()
    source = _source(backend)
    engine = PythonLayoutEngine()
    pure_threads = []
    measured_threads = []
    generation = [17]
    outcomes = []
    old_geometry = {"text":{"x":4.0,"y":8.0,"width":3.0,"height":2.0}}
    applied = [0]
    observed = {k:dict(v) for k,v in old_geometry.items()}

    def compute(snapshot):
        pure_threads.append(threading.get_ident())
        assert threading.get_ident() != ui.thread
        return engine.compute(snapshot)

    def provisional(snapshot):
        pure_threads.append(threading.get_ident())
        assert threading.get_ident() != ui.thread
        return engine.compute_provisional(snapshot)

    def measure(node_id,width):
        assert threading.get_ident()==ui.thread
        measured_threads.append(threading.get_ident())
        request=MeasurementRequest(node_id, LayoutConstraints(
            AvailableSize(width, True),AvailableSize(None, False),
        ), generation[0],0)
        return source.port().measure(request).intrinsic

    def apply(result):
        assert threading.get_ident()==ui.thread
        assert generation[0]==17
        rect=dict(result.boxes)["text"].border
        observed["text"]={"x":rect.x,"y":rect.y,"width":rect.width,"height":rect.height}
        applied[0]+=1

    def restore(before):
        observed.clear()
        observed.update({k:dict(v) for k,v in before.items()})

    handle=start_native_worker_layout(
        replace(case_snapshot("A04"),measurements=()),
        compute=compute, provisional=provisional,
        measure_on_ui=measure,
        is_ui_thread=lambda:threading.get_ident()==ui.thread and source.port().is_ui_thread(),
        current_generation=lambda:generation[0],
        apply_geometry=apply,
        observed_geometry=lambda:{k:dict(v) for k,v in observed.items()},
        restore_geometry=restore,
        initial_widths={"text":100},
        post_to_ui=ui.post,
        on_finished=lambda value,error:outcomes.append((value,error)),
    )
    ui.drain(handle)
    assert len(outcomes)==1
    result,error=outcomes[0]
    assert error is None
    assert result is not None
    assert applied==[1]
    assert pure_threads and all(t!=ui.thread for t in pure_threads)
    assert measured_threads==[ui.thread,ui.thread]
    assert result.measurement_error is None
    assert result.engine_error is None
    assert result.geometry_commit_error is not None
    assert 0<=result.geometry_commit_error<=1.0
    assert observed["text"]["width"]==150.0


@pytest.mark.parametrize("backend", ("kivy","tk","headless"))
def test_native_worker_stale_generation_rejects_all_partial_commits(backend):
    ui=_UIQueue()
    source=_source(backend)
    engine=PythonLayoutEngine()
    generation=[17]
    observed={"text":{"x":1.0,"y":2.0,"width":3.0,"height":4.0}}
    before={k:dict(v) for k,v in observed.items()}
    calls=[]
    commits=[]
    outcomes=[]

    def measure(node_id,width):
        assert threading.get_ident()==ui.thread
        calls.append(width)
        if len(calls)==2: generation[0]=18
        request=MeasurementRequest(node_id,LayoutConstraints(
            AvailableSize(width,True),AvailableSize(None,False)
        ),17,0)
        return source.port().measure(request).intrinsic

    handle=start_native_worker_layout(
        replace(case_snapshot("A04"),measurements=()),
        compute=engine.compute,provisional=engine.compute_provisional,
        measure_on_ui=measure,
        is_ui_thread=lambda:threading.get_ident()==ui.thread and source.port().is_ui_thread(),
        current_generation=lambda:generation[0],
        apply_geometry=lambda value:commits.append(value),
        observed_geometry=lambda:{k:dict(v) for k,v in observed.items()},
        restore_geometry=lambda original:observed.update(original),
        initial_widths={"text":100},
        post_to_ui=ui.post,
        on_finished=lambda result,error:outcomes.append((result,error)),
    )
    ui.drain(handle)
    assert calls==[100,150]
    assert len(outcomes)==1 and outcomes[0][0] is None
    assert isinstance(outcomes[0][1],SFLEError)
    assert outcomes[0][1].code==DiagnosticCode.INVALID_SNAPSHOT
    assert commits==[]
    assert observed==before


def test_native_worker_missing_observation_after_commit_rolls_back():
    """A missing native widget must not be treated as zero read-back error."""
    ui = _UIQueue()
    engine = PythonLayoutEngine()
    generation = 17
    outcomes = []
    applied = []
    observed = {
        "root": {"x": 9.0, "y": 9.0, "width": 10.0, "height": 10.0},
        "text": {"x": 4.0, "y": 8.0, "width": 3.0, "height": 2.0},
    }
    original = {name: dict(rect) for name, rect in observed.items()}

    def apply(result):
        applied.append(True)
        root = dict(result.boxes)["root"].border
        observed["root"] = {
            axis: getattr(root, axis) for axis in ("x", "y", "width", "height")
        }
        # The text widget vanishes after applying the native geometry.
        # A matching root cannot mask that missing read-back.
        del observed["text"]

    def restore(before):
        observed.clear()
        observed.update({name: dict(rect) for name, rect in before.items()})

    handle = start_native_worker_layout(
        replace(case_snapshot("A04"), measurements=()),
        compute=engine.compute,
        provisional=engine.compute_provisional,
        measure_on_ui=lambda node_id, width: IntrinsicSizes(
            0, 210, 20, 40, width, 40
        ),
        is_ui_thread=lambda: threading.get_ident() == ui.thread,
        current_generation=lambda: generation,
        apply_geometry=apply,
        observed_geometry=lambda: {name: dict(rect) for name, rect in observed.items()},
        restore_geometry=restore,
        initial_widths={"text": 100},
        post_to_ui=ui.post,
        on_finished=lambda result, error: outcomes.append((result, error)),
    )
    ui.drain(handle)

    assert applied == [True]
    assert len(outcomes) == 1
    result, error = outcomes[0]
    assert result is None
    assert isinstance(error, SFLEError)
    assert error.code is DiagnosticCode.INVALID_SNAPSHOT
    assert observed == original
