"""RED F2.1: intrinsic min/max-width constraints, including recursive auto Flex.

The browser independently computes min-content and max-content metrics and
the final rectangles. No hand-authored expected width, no silent skips.
"""
from __future__ import annotations
import json
import subprocess
import pytest
from f2_fuzz_dimension_helpers import _typed, rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.sfle.native_wire import serialize_snapshot

TEXTS=("AAAA BBBBBBB CCC", "abcdefgh ij klmnopq", "alpha beta gamma delta")


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            assert browser.version==reference_version()
            yield browser.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            browser.close()


@pytest.mark.parametrize("text",TEXTS)
@pytest.mark.parametrize("mode",("min_min","max_min","min_max","max_max","conflict"))
@pytest.mark.parametrize("nested",(False,True))
def test_browser_intrinsic_width_bounds_and_nested_contribution(
    page,rust_binary,text,mode,nested,
):
    min_key,max_key={
        "min_min":("min-content",None),
        "max_min":(None,"min-content"),
        "min_max":("max-content",None),
        "max_max":(None,"max-content"),
        "conflict":("max-content","min-content"),
    }[mode]
    leaf_width="280px" if max_key is not None else "12px"
    if mode=="conflict":leaf_width="80px"
    decls=(
        (f"min-width:{min_key};" if min_key is not None else "min-width:0;")
        +(f"max-width:{max_key};" if max_key is not None else "")
    )
    start=("<div id='wrapper' style='display:flex;flex-direction:column;"
           "width:auto;height:auto;flex:0 0 auto;min-width:0;"
           "align-items:flex-start;box-sizing:content-box'>") if nested else ""
    end="</div>" if nested else ""
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;width:400px;height:70px;"
        "align-items:flex-start;box-sizing:content-box'>"+start
        +f"<div id='leaf' style='font:10px/20px monospace;white-space:normal;"
        f"box-sizing:content-box;width:{leaf_width};height:20px;"
        f"flex:0 0 auto;{decls}'>{text}</div>"
        +end+"</div></body></html>"
    )
    observed=page.evaluate("""() => {
        const leaf=document.getElementById('leaf');
        const metrics={};
        for(const key of ['min-content','max-content']){
            const probe=leaf.cloneNode(true);
            probe.removeAttribute('id');
            probe.style.position='absolute';
            probe.style.flex='none';
            probe.style.width=key;
            probe.style.minWidth='0';
            probe.style.maxWidth='none';
            document.body.appendChild(probe);
            metrics[key]=probe.getBoundingClientRect().width;
            probe.remove();
        }
        const rects=Object.fromEntries(
            [...document.querySelectorAll('[id]')].map(el=>{
                const r=el.getBoundingClientRect();
                return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
            })
        );
        return {metrics,rects};
    }""")
    low,high=observed["metrics"]["min-content"],observed["metrics"]["max-content"]
    assert 0<low<high,observed["metrics"]
    nodes=[LayoutNode("root",None,"Flex",_typed({
        "direction":"row","width":"400px","height":"70px","align_items":"flex-start",
    }))]
    if nested:
        nodes.append(LayoutNode("wrapper","root","Flex",_typed({
            "direction":"column","width":"auto","height":"auto",
            "flex_basis":"auto","flex_grow":0,"flex_shrink":0,
            "min_width":"0px","align_items":"flex-start",
        })))
    style={
        "width":leaf_width,"height":"20px","flex_basis":"auto",
        "flex_grow":0,"flex_shrink":0,
        "min_width":min_key or "0px",
    }
    if max_key is not None:style["max_width"]=max_key
    nodes.append(LayoutNode("leaf","wrapper" if nested else "root","Text",_typed(style)))
    snapshot=LayoutInput(
        1,506,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(400,True),AvailableSize(70,True)),
        tuple(nodes),
        (MeasuredBox("leaf",IntrinsicSizes(low,high,20,20,high,20),
            LayoutConstraints(AvailableSize(None,False),AvailableSize(None,False)),0),),
    )
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    run=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30)
    rust=json.loads(run.stdout)
    assert rust["ok"],rust.get("error")
    rs={v["node_id"]:v["border"] for v in rust["result"]["boxes"]}
    for node,rect in observed["rects"].items():
        for axis,wanted in rect.items():
            left=getattr(py[node].border,axis)
            right=rs[node][axis]
            assert abs(left-wanted)<=0.01,(
                f"{mode} nested={nested} Python {node}.{axis}: {left} vs Chrome {wanted}"
            )
            assert abs(right-wanted)<=0.01,(
                f"{mode} nested={nested} Rust {node}.{axis}: {right} vs Chrome {wanted}"
            )
            assert left==right,(mode,nested,node,axis,left,right)
