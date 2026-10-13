"""F2.1 nested, definite percentage cross-axis and min/max dependencies.

Browser performs 24 independent nested flex layouts with three successively
computed percentage reference axes, including minimum-precedence conflicts.
No ID-dependent computed numbers enter the assertions.
"""
from __future__ import annotations
import json
import subprocess
import pytest

from fuzz_dimension_helpers import _typed, rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection
from psx.sfle.native_wire import serialize_snapshot


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


@pytest.mark.parametrize("index",range(24))
def test_nested_definite_percentages_cross_and_main_constraints(
    index,page,rust_binary,
):
    root_w=280+index*7
    root_h=180+index*3
    wrapper_w=(35,45,55,65)[index%4]
    wrapper_h=(40,50,60)[index%3]
    middle_w=(40,50,60)[(index//3)%3]
    middle_h=(30,40,50)[index%3]
    leaf_w=(30,60,90)[index%3]
    min_w=(20,70,100)[(index//4)%3]
    max_w=(35,55,80)[(index//7)%3]
    raw=[
        ("root",None,"Flex",{"direction":"row","width":f"{root_w}px",
            "height":f"{root_h}px","align_items":"flex-start"}),
        ("wrapper","root","Flex",{"direction":"column","width":f"{wrapper_w}%",
            "height":f"{wrapper_h}%","flex_basis":f"{wrapper_w}%",
            "flex_shrink":0,"min_width":"0px","align_items":"flex-start"}),
        ("middle","wrapper","Flex",{"direction":"row","width":f"{middle_w}%",
            "height":f"{middle_h}%","flex_basis":f"{middle_h}%",
            "flex_shrink":0,"min_width":"0px","align_items":"flex-start"}),
        ("leaf","middle","Box",{"width":f"{leaf_w}%","height":"20px",
            "flex_basis":f"{leaf_w}%","flex_shrink":0,
            "min_width":f"{min_w}%","max_width":f"{max_w}%"}),
    ]
    snapshot=LayoutInput(
        1,6000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_w,True),AvailableSize(root_h,True)),
        tuple(LayoutNode(node_id,parent,comp,_typed(style))
              for node_id,parent,comp,style in raw),(),
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_w}px;height:{root_h}px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='wrapper' style='display:flex;flex-direction:column;"
        f"width:{wrapper_w}%;height:{wrapper_h}%;flex:0 0 {wrapper_w}%;"
        "min-width:0;align-items:flex-start;box-sizing:content-box'>"
        f"<div id='middle' style='display:flex;flex-direction:row;"
        f"width:{middle_w}%;height:{middle_h}%;flex:0 0 {middle_h}%;"
        "min-width:0;align-items:flex-start;box-sizing:content-box'>"
        f"<div id='leaf' style='width:{leaf_w}%;height:20px;"
        f"flex:0 0 {leaf_w}%;min-width:{min_w}%;max-width:{max_w}%;"
        "box-sizing:content-box'></div>"
        "</div></div></div></body></html>"
    )
    observed=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    python=dict(PythonLayoutEngine().compute(snapshot).boxes)
    process=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30)
    wire=json.loads(process.stdout)
    assert wire["ok"],wire.get("error")
    rust={item["node_id"]:item["border"] for item in wire["result"]["boxes"]}
    assert set(python)==set(rust)==set(observed)
    for node,rect in observed.items():
        for axis,wanted in rect.items():
            p=getattr(python[node].border,axis)
            r=rust[node][axis]
            assert abs(p-wanted)<=0.01,(
                f"recursive percent[{index}] {node}.{axis} Python={p} Browser={wanted}"
            )
            assert abs(r-wanted)<=0.01,(
                f"recursive percent[{index}] {node}.{axis} Rust={r} Browser={wanted}"
            )
            assert p==r,("raw Rust/Python parity",index,node,axis,p,r)
