"""Differential SFLE contract runner: identical v1 snapshot, Python and Rust.

No xfail/skip is permitted in CI: unsupported-but-required alpha cases fail.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "sfle"))
from test_f2_acceptance_contract_red import case_snapshot  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine  # noqa: E402
from psx.sfle.errors import SFLEError  # noqa: E402
from psx.sfle.lengths import Length  # noqa: E402

CORPUS = json.loads((ROOT / "tests/sfle/fixtures/f2_alpha_acceptance.json").read_text())
RUST_ROOT = ROOT / "rust/sfle-core"


def _axis(value):
    return {"value": value.value, "definite": value.definite}


def _constraints(value):
    return {"width": _axis(value.width), "height": _axis(value.height)}


def _snapshot_wire(snapshot):
    def style_value(value):
        return {"kind": value.kind.value, "value": value.value} if isinstance(value, Length) else value
    def metric(record):
        m=record.intrinsic
        return {
            "node_id":record.node_id,
            "constraints":_constraints(record.constraints),
            "revision":record.revision,
            "intrinsic":{
                "min_content_width":m.min_content_width,
                "max_content_width":m.max_content_width,
                "min_content_height":m.min_content_height,
                "max_content_height":m.max_content_height,
                "preferred_width":m.preferred_width,
                "preferred_height":m.preferred_height,
                "baseline":m.baseline,
            },
        }
    return {
        "schema_version":snapshot.schema_version,
        "generation":snapshot.generation,
        "direction":snapshot.direction.value,
        "constraints":_constraints(snapshot.constraints),
        "nodes":[{
            "node_id":n.node_id,"parent_id":n.parent_id,
            "component":n.component,"style":{k:style_value(v) for k,v in n.style},
        } for n in snapshot.nodes],
        "measurements":[metric(m) for m in snapshot.measurements],
    }


@pytest.fixture(scope="session")
def rust_binary():
    subprocess.run(
        ["cargo","build","--quiet","--bin","sfle_f2_fixture_runner"],
        cwd=RUST_ROOT,check=True,timeout=240,
    )
    filename="sfle_f2_fixture_runner.exe" if sys.platform=="win32" else "sfle_f2_fixture_runner"
    result=RUST_ROOT / "target/debug" / filename
    assert result.exists(), "Rust CLI build did not produce binary"
    return result


def _python_compute(snapshot):
    try:
        return {"ok":True,"result":PythonLayoutEngine().compute(snapshot)}
    except SFLEError as exc:
        return {"ok":False,"error":{"code":exc.code.value,"message":str(exc),"node_id":exc.node_id}}


def _rust_compute(binary,snapshot):
    run=subprocess.run(
        [str(binary)],input=json.dumps(_snapshot_wire(snapshot)),
        text=True,capture_output=True,check=True,timeout=30,
    )
    return json.loads(run.stdout)


def _rects(result):
    if isinstance(result,dict):
        return {box["node_id"]:box for box in result["boxes"]}
    def rect(value):
        return {axis:getattr(value,axis) for axis in ("x","y","width","height")}
    return {
        node_id:{"node_id":node_id,"content":rect(box.content),
                 "border":rect(box.border),"padding":rect(box.padding),
                 "margin":rect(box.margin)}
        for node_id,box in result.boxes
    }


@pytest.mark.parametrize("case",CORPUS["cases"],ids=lambda case:case["id"])
def test_shared_normalized_input_rust_python_and_expected_geometry(case,rust_binary):
    snapshot=case_snapshot(case["id"])
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    if case["id"]=="C99":
        for side in (py,rs):
            assert side["ok"] is False
            assert side["error"]["code"]==case["expected"]["diagnostic"]
            assert side["error"]["node_id"]==case["expected"]["node"]
            assert all(token in side["error"]["message"].lower()
                       for token in ("multi-node","percentage","cycle"))
        return
    assert py["ok"],f"{case['id']} Python failure: {py.get('error')}"
    assert rs["ok"],f"{case['id']} Rust failure: {rs.get('error')}"
    python_result=py["result"]
    rust_result=rs["result"]
    assert python_result.generation==rust_result["generation"]==snapshot.generation
    pboxes=_rects(python_result)
    rboxes=_rects(rust_result)
    ordered_python=[node_id for node_id,_ in python_result.boxes]
    ordered_rust=[box["node_id"] for box in rust_result["boxes"]]
    assert ordered_python==ordered_rust==[n.node_id for n in snapshot.nodes]
    for node_id in ordered_python:
        for box_type in ("content","border","padding","margin"):
            for axis in ("x","y","width","height"):
                a=pboxes[node_id][box_type][axis]
                b=rboxes[node_id][box_type][axis]
                assert math.isclose(a,b,rel_tol=0,abs_tol=CORPUS["tolerance_px"]),(
                    f"{case['id']} {node_id}.{box_type}.{axis}: Python={a}, Rust={b}"
                )
    for key,expected in case["expected"].items():
        if isinstance(expected,bool) or not isinstance(expected,(int,float)):
            continue
        if key in ("intrinsic_gap","used_gap","generation","commits_from_stale_generation",
                   "max_iterations","commits_after_cycle"):
            continue
        if "." not in key: continue
        node_id,axis=key.split(".",1)
        if axis=="padding_top":
            value=pboxes[node_id]["content"]["y"]-pboxes[node_id]["padding"]["y"]
        elif axis in ("x","y","width","height"):
            value=pboxes[node_id]["content"][axis]
        else:
            raise AssertionError(f"No numeric acceptance mapping for {case['id']} {key}")
        assert math.isclose(value,expected,rel_tol=0,abs_tol=CORPUS["tolerance_px"]),(
            f"{case['id']} expected {key}={expected}, computed={value}"
        )
