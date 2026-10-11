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


@pytest.mark.parametrize("index",range(32))
def test_flex_shrink_and_intrinsic_text_constraints_against_chromium(
    index,page,rust_binary,
):
    """Measured min/max-content Text bounds participate in nonlinear flex.

    Independent Chromium supplies actual text intrinsic min/max widths.
    Items can shrink, grow and hit conflicting minimum/maximum constraints.
    """
    word=("BBBBBBBB","abcdefghijkl","ABCDEFGHIJKLMN")[index%3]
    text=f"AAA {word} CCCC DDDD EEEEE"
    root_width=(125,180,230,310)[index%4]
    basis=(70,110,150,205)[(index//2)%4]
    grow=(index//4)%2
    shrink=1+(index//8)%2
    lower=("min-content","max-content")[index%2]
    upper=(None,"max-content","80px","125px")[(index//3)%4]
    bounds=f"min-width:{lower};"+(f"max-width:{upper};" if upper else "")
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_width}px;height:60px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='text' style='width:auto;height:20px;flex:{grow} {shrink} {basis}px;"
        f"font:10px/20px monospace;white-space:normal;{bounds}"
        f"box-sizing:content-box'>{text}</div>"
        "<div id='fixed' style='width:40px;height:20px;"
        "flex:0 0 40px;min-width:0;box-sizing:content-box'></div>"
        "</div></body></html>"
    )
    observed=page.evaluate("""() => {
        const leaf=document.getElementById('text');
        const measure={};
        for(const mode of ['min-content','max-content']){
            const probe=leaf.cloneNode(true);
            probe.removeAttribute('id');
            probe.style.position='absolute';
            probe.style.flex='none';
            probe.style.width=mode;
            probe.style.height='auto';
            probe.style.minWidth='0';
            probe.style.maxWidth='none';
            document.body.appendChild(probe);
            measure[mode]=probe.getBoundingClientRect().width;
            probe.remove();
        }
        return {
            measure,
            rectangles:Object.fromEntries(
                [...document.querySelectorAll('[id]')].map(el=>{
                    const r=el.getBoundingClientRect();
                    return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
                })
            )
        };
    }""")
    low=observed["measure"]["min-content"]
    high=observed["measure"]["max-content"]
    assert 0<low<high,(index,observed["measure"])
    style={
        "width":"auto","height":"20px","flex_basis":f"{basis}px",
        "flex_grow":grow,"flex_shrink":shrink,"min_width":lower,
    }
    if upper is not None:style["max_width"]=upper
    snapshot=LayoutInput(
        1,100000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(60,True)),
        (
            LayoutNode("root",None,"Flex",_typed({
                "direction":"row","width":f"{root_width}px","height":"60px",
                "align_items":"flex-start",
            })),
            LayoutNode("text","root","Text",_typed(style)),
            LayoutNode("fixed","root","Box",_typed({
                "width":"40px","height":"20px","flex_basis":"40px",
                "flex_grow":0,"flex_shrink":0,"min_width":"0px",
            })),
        ),
        (MeasuredBox("text",IntrinsicSizes(low,high,20,20,high,20),
            LayoutConstraints(AvailableSize(None,False),AvailableSize(None,False)),0),),
    )
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    proc=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        capture_output=True,text=True,check=True,timeout=30)
    native=json.loads(proc.stdout)
    assert native["ok"],(index,native.get("error"))
    rs={entry["node_id"]:entry["border"] for entry in native["result"]["boxes"]}
    for node,rect in observed["rectangles"].items():
        for axis,want in rect.items():
            pv=getattr(py[node].border,axis)
            rv=rs[node][axis]
            assert abs(pv-want)<=0.01,(
                f"intrinsic text flex freeze case {index}: "
                f"Python {node}.{axis}={pv} Chromium={want}"
            )
            assert abs(rv-want)<=0.01,(
                f"intrinsic text flex freeze case {index}: "
                f"Rust {node}.{axis}={rv} Chromium={want}"
            )
            assert pv==rv,(index,node,axis,pv,rv)
