"""A08 installed abi3 PyO3 wheel must compute every accepted F2 snapshot.

This file runs only in the dedicated maturin wheel job. It is intentionally
not collected in the generic SFLE Core suite (which may lack the extension).
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sfle'))

import pytest
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from test_f2_acceptance_contract_red import case_snapshot


@pytest.mark.parametrize("case_id",[
    "A01","A02","A03","A04","A05","A06","A07",
    "C01","C02","C03","C04","C05","C06","C99",
    "N01","N02","N03","N04","N05","N06","N07","N08",
    "F01","F02","F04","F05","A09-LTR","A09-RTL",
])
def test_A08_installed_pyo3_wheel_parity(case_id):
    engine=load_layout_engine()
    assert engine.backend_name=="rust", "The installed native wheel must select Rust"
    fallback=PythonLayoutEngine()
    snapshot=case_snapshot(case_id)
    if case_id in ("C99","N01","N02","N03","N04","N06","N07","N08"):
        with pytest.raises(SFLEError) as native:
            engine.compute(snapshot)
        with pytest.raises(SFLEError) as py:
            fallback.compute(snapshot)
        assert native.value.code==py.value.code==DiagnosticCode.UNSUPPORTED_FEATURE
        assert native.value.node_id==py.value.node_id
        return
    a=engine.compute(snapshot)
    b=fallback.compute(snapshot)
    assert a.generation==b.generation
    assert [node_id for node_id,_ in a.boxes]==[node_id for node_id,_ in b.boxes]
    for (_,box_a),(_,box_b) in zip(a.boxes,b.boxes):
        for name in ("content","padding","border","margin"):
            for axis in ("x","y","width","height"):
                a_raw = getattr(getattr(box_a,name),axis)*64
                b_raw = getattr(getattr(box_b,name),axis)*64
                assert a_raw==b_raw and a_raw==int(a_raw), (
                    f"{case_id} {name}.{axis} Python/Rust not bit identical: {a_raw} vs {b_raw}"
                )


def test_A08_native_wheel_real_multileaf_intrinsic_convergence():
    """Rust's *actual* PyO3 engine must obey the multi-round UI measurement bridge."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sfle"))
    from test_f2_b1_real_multi_leaf_convergence_red import (
        assert_real_engine_remeasurement_converges,
    )
    engine = load_layout_engine()
    assert engine.backend_name == "rust", "This native-wheel regression may not run on Python fallback."
    assert_real_engine_remeasurement_converges(engine)


def test_A08_rust_worker_headless_ui_measuring_and_observed_commit():
    """Installed PyO3 executes on a real worker; native port stays UI-owned."""
    import threading
    from dataclasses import replace
    from psx.sfle.worker_lifecycle import start_native_worker_layout
    from psx.sfle.measurement_plan import MeasurementRequest
    from psx.sfle.model import AvailableSize, LayoutConstraints
    from test_f2_native_worker_portable_red import _UIQueue, _source

    engine = load_layout_engine()
    assert engine.backend_name == "rust"
    ui = _UIQueue()
    source = _source("headless")
    snapshot = replace(case_snapshot("A04"), measurements=())
    computed_threads = []
    measured_threads = []
    outcomes = []
    applied = []
    observed = {"text": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}}
    generation = [snapshot.generation]

    def compute_on_worker(data, method):
        computed_threads.append(threading.get_ident())
        assert threading.get_ident() != ui.thread
        return method(data)

    def measure_on_ui(node_id, width):
        measured_threads.append(threading.get_ident())
        assert threading.get_ident() == ui.thread
        request = MeasurementRequest(node_id, LayoutConstraints(
            AvailableSize(width, True), AvailableSize(None, False),
        ), generation[0], 0)
        return source.port().measure(request).intrinsic

    def commit_on_ui(result):
        assert threading.get_ident() == ui.thread
        applied.append(result.generation)
        bounds = dict(result.boxes)["text"].border
        observed["text"] = {key: getattr(bounds, key) for key in ("x", "y", "width", "height")}

    def restore_on_ui(original):
        assert threading.get_ident() == ui.thread
        observed.clear()
        observed.update({key: dict(box) for key, box in original.items()})

    handle = start_native_worker_layout(
        snapshot,
        compute=lambda data: compute_on_worker(data, engine.compute),
        provisional=lambda data: compute_on_worker(data, engine.compute_provisional),
        measure_on_ui=measure_on_ui,
        is_ui_thread=lambda: threading.get_ident() == ui.thread and source.port().is_ui_thread(),
        current_generation=lambda: generation[0],
        apply_geometry=commit_on_ui,
        observed_geometry=lambda: {key: dict(box) for key, box in observed.items()},
        restore_geometry=restore_on_ui,
        initial_widths={"text": 100},
        post_to_ui=ui.post,
        on_finished=lambda result, error: outcomes.append((result, error)),
    )
    ui.drain(handle)
    assert len(outcomes) == 1
    result, error = outcomes[0]
    assert error is None and result is not None
    assert computed_threads and all(thread != ui.thread for thread in computed_threads)
    assert measured_threads and all(thread == ui.thread for thread in measured_threads)
    assert applied == [snapshot.generation]
    assert observed["text"]["width"] == 150.0
    assert result.measurement_error is None and result.engine_error is None
    assert result.geometry_commit_error is not None
    assert 0.0 <= result.geometry_commit_error <= 1.0
