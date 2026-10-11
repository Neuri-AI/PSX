"""Seeded browser differential: silent geometry deviations are test failures.

Every case uses one immutable snapshot for Python and Rust, then actual DOM
geometry. Accepted cases must match all node border rectangles to 0.01px.
Rejected cases must agree on UNSUPPORTED_FEATURE, node ID and cycle class.
"""
from __future__ import annotations
import math
import random
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tests"/"interop"))
from test_sfle_f2_differential import rust_binary,_rust_compute
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize,LayoutConstraints,LayoutInput,LayoutNode,WritingDirection,
)
from psx.sfle.lengths import parse_length
from psx.sfle.errors import SFLEError,DiagnosticCode

SEED=0x5F1E2026
COUNT=24
TOLERANCE=0.01
FUZZ_STATUS={}


def fuzz_cases():
    rng=random.Random(SEED)
    for index in range(COUNT):
        width=rng.choice([96,120,160,200])
        gap=rng.choice(["0px","4px","10%"])
        n=rng.choice([2,3])
        items=[]
        for i in range(n):
            basis=rng.choice(["20px","30px","25%","auto"])
            specified=rng.choice(["20px","30px","25%"])
            grow=rng.choice([0,1,2])
            shrink=rng.choice([0,1])
            pad=rng.choice(["0px","4px","10%"])
            items.append(dict(basis=basis,width=specified,grow=grow,shrink=shrink,pad=pad))
        yield index,width,gap,items


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        instance=playwright.chromium.launch(headless=True)
        try:yield instance.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:instance.close()


@pytest.mark.parametrize("case",list(fuzz_cases()),ids=lambda case:f"seed-{SEED:x}-case-{case[0]:02d}")
def test_seeded_flex_differential_against_chromium(case,browser,rust_binary):
    index,width,gap,items=case
    def style_tuple(spec):
        return tuple((key,parse_length(value) if isinstance(value,str) and
            (value.endswith("px") or value.endswith("%") or value=="auto") else value)
                     for key,value in spec.items())
    nodes=[LayoutNode("root",None,"Flex",style_tuple({
        "direction":"row","width":f"{width}px","height":"60px",
        "column_gap":gap,"align_items":"flex-start",
    }))]
    elements=[]
    for i,item in enumerate(items):
        node_id=f"n{i}"
        nodes.append(LayoutNode(node_id,"root","Box",style_tuple({
            "width":item["width"],"height":"20px","flex_basis":item["basis"],
            "flex_grow":item["grow"],"flex_shrink":item["shrink"],
            "min_width":"0px","layout_padding_top":item["pad"],
        })))
        elements.append(
            f'<div id="{node_id}" style="height:20px;width:{item["width"]};'
            f'flex:{item["grow"]} {item["shrink"]} {item["basis"]};'
            f'min-width:0;padding-top:{item["pad"]};box-sizing:content-box"></div>'
        )
    snapshot=LayoutInput(1,17,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(width,True),AvailableSize(60,True)),
        tuple(nodes),())
    try:py={"ok":True,"result":PythonLayoutEngine().compute(snapshot)}
    except SFLEError as error:
        py={"ok":False,"code":error.code.value,"node":error.node_id,"kind":str(error)}
    # Use exactly the production-normalized serializer, not a hand-built Rust tree.
    from psx.sfle.native_wire import serialize_snapshot
    import json,subprocess
    run=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30)
    rs=json.loads(run.stdout)
    if not py["ok"] or not rs["ok"]:
        FUZZ_STATUS[index]='rejected'
        assert not py["ok"] and not rs["ok"],(
            f"Silent backend disagreement seed={SEED}, case={index}: {py}, {rs}")
        assert py["code"]==rs["error"]["code"]==DiagnosticCode.UNSUPPORTED_FEATURE.value
        assert py["node"]==rs["error"]["node_id"]
        for word in ("cycle","percentage"):
            assert word in py["kind"].lower() and word in rs["error"]["message"].lower()
        return
    browser.set_content('<!doctype html><html><body style="margin:0">'
        f'<div id="root" style="display:flex;width:{width}px;height:60px;'
        f'column-gap:{gap};align-items:flex-start">'+''.join(elements)
        +'</div></body></html>')
    observed=browser.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    FUZZ_STATUS[index]='matched'
    p=dict(py["result"].boxes)
    native={v["node_id"]:v for v in rs["result"]["boxes"]}
    for node_id,box in p.items():
        for axis in ("x","y","width","height"):
            expected=observed[node_id][axis]
            python_actual=getattr(box.border,axis)
            rust_actual=native[node_id]["border"][axis]
            if abs(python_actual-expected)>TOLERANCE:
                FUZZ_STATUS[index]='silent_discrepancy'
            assert abs(python_actual-expected)<=TOLERANCE, (
                f"SILENT GEOMETRY BUG seed={SEED} case={index} {node_id}.{axis} "
                f"Python={python_actual} Chromium={expected} input={case!r}")
            assert abs(rust_actual-expected)<=TOLERANCE, (
                f"SILENT GEOMETRY BUG seed={SEED} case={index} {node_id}.{axis} "
                f"Rust={rust_actual} Chromium={expected} input={case!r}")


def test_seeded_fuzz_audited_outcomes():
    """Report rejected, matching and silently divergent trees."""
    from collections import Counter
    assert len(FUZZ_STATUS)==COUNT
    counts=Counter(FUZZ_STATUS.values())
    print(f"SFLE FUZZ seed={SEED:#x} total={COUNT} matched={counts['matched']} rejected={counts['rejected']} silent_discrepancies={counts['silent_discrepancy']}")
    assert counts["silent_discrepancy"]==0, f"Silent geometry bugs: {counts}"
