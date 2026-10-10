"""True Chromium line-wrapping references for A01/A04/A05.

No fabricated final intrinsic metrics enter this test. The live DOM's
height-for-width measurements feed one coordinator for Python and Rust.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "interop"))
sys.path.insert(0, str(ROOT / "tests" / "sfle"))
from test_sfle_f2_differential import rust_binary
from test_f2_acceptance_contract_red import case_snapshot
from width_measurement_helpers import rust_compute
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import IntrinsicSizes
from psx.sfle.remeasure_session import compute_with_width_measurements
from dataclasses import replace

DATA = json.loads((ROOT / "tests/sfle/fixtures/f2_alpha_acceptance.json").read_text())


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        try:
            yield instance.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            instance.close()


def html_for(case_id, text):
    font = "font:10px/20px monospace;white-space:normal;min-width:0"
    if case_id=="A01":
        return (f'<div id="root" style="display:flex;width:120px;align-items:stretch">'
            '<div id="fixed" style="flex:0 0 40px;width:40px;height:10px;min-width:0"></div>'
            '<div id="column" style="display:flex;flex-direction:column;flex:0 0 80px;width:80px;min-width:0">'
            f'<div id="text" style="width:100%;{font}">{text}</div></div></div>')
    if case_id=="A04":
        return (f'<div id="root" style="display:flex;width:150px;align-items:stretch">'
            f'<div id="text" style="flex:1 1 100px;{font}">{text}</div></div>')
    if case_id=="A05":
        return (f'<div id="root" style="display:flex;width:70px;align-items:stretch">'
            f'<div id="a" style="flex:0 1 50px;{font}">{text}</div>'
            f'<div id="b" style="flex:0 1 50px;{font}">{text}</div></div>')
    raise AssertionError(case_id)


@pytest.mark.parametrize("case_id", ["A01","A04","A05"])
@pytest.mark.parametrize("backend", ["python","rust"])
def test_real_text_browser_width_remeasurement_matches_sfle(case_id, backend, browser, rust_binary):
    case = next(case for case in DATA["cases"] if case["id"]==case_id)
    live = case["live_text"]
    browser.set_content('<!doctype html><html><body style="margin:0">'+
                        html_for(case_id, live["text"])+
                        '</body></html>')
    measured_ids = ["a","b"] if case_id=="A05" else ["text"]
    initial = {node_id:live["initial_width_px"] for node_id in measured_ids}
    calls=[]
    heights=[]
    def measure_fn(node_id, width):
        height = browser.evaluate("""({id,width}) => {
            const element=document.getElementById(id);
            const previous=element.style.width;
            const previousFlex=element.style.flex;
            const previousAlign=element.style.alignSelf;
            const previousHeight=element.style.height;
            element.style.alignSelf='flex-start';
            element.style.height='auto';
            element.style.flex='none';
            element.style.width=width+'px';
            const height=element.getBoundingClientRect().height;
            element.style.flex=previousFlex;
            element.style.alignSelf=previousAlign;
            element.style.height=previousHeight;
            element.style.width=previous;
            return height;
        }""",{"id":node_id,"width":width})
        calls.append((node_id,width))
        heights.append(height)
        return IntrinsicSizes(0,210 if case_id!="A05" else 100,20,
                              height,initial[node_id],height)
    snapshot=replace(case_snapshot(case_id), measurements=())
    compute=(PythonLayoutEngine().compute if backend=="python"
             else lambda request:rust_compute(rust_binary,request))
    provisional=(PythonLayoutEngine().compute_provisional if backend=="python"
                 else lambda request:rust_compute(rust_binary,request,provisional=True))
    result=compute_with_width_measurements(
        snapshot,compute,measure_fn,initial_widths=initial,
        compute_provisional=provisional,
    )
    assert len(calls)==len(measured_ids)*live["expected_measurements_per_leaf"]
    for node_id in measured_ids:
        widths=[width for name,width in calls if name==node_id]
        assert widths==pytest.approx([live["initial_width_px"],live["final_width_px"]],abs=0.01)
    for index,record in enumerate(calls):
        assert heights[index]==pytest.approx(
            live["initial_height_px"] if record[1]==live["initial_width_px"]
            else live["final_height_px"],abs=0.01)
    actual=browser.evaluate("""() => Object.fromEntries(
        ['root',...Array.from(document.querySelectorAll('#root *')).map(x=>x.id)]
        .filter(Boolean).map(id=>{
            const r=document.getElementById(id).getBoundingClientRect();
            return [id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    assert actual["root"]["height"]==pytest.approx(live["final_height_px"],abs=0.01)
    for node_id,box in result.boxes:
        for axis in ("x","y","width","height"):
            expected=actual[node_id][axis]
            measured=getattr(box.border,axis)
            assert measured==pytest.approx(expected,abs=DATA["tolerance_px"]),(
                f"{case_id} {backend} {node_id}.{axis}: sfle={measured}, chromium={expected}"
            )
