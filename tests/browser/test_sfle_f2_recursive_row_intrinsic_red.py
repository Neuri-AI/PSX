"""RED F2.1 nowrap row Flex min/max-content bounds across nested children.

Both CSS flex children are definite no-shrink with fixed widths. The row's
intrinsic inline contribution must include each outer width and fixed gap.
"""
from __future__ import annotations
import json
import subprocess
import pytest
from f2_fuzz_dimension_helpers import _typed,rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize,LayoutConstraints,LayoutInput,LayoutNode,WritingDirection
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


@pytest.mark.parametrize("index",range(16))
def test_intrinsic_row_nowrap_multi_item_bound(index,page,rust_binary):
    mode=("min-content","max-content")[index%2]
    upper=(index//2)%2==1
    nested=(index//4)%2==1
    initial="220px" if upper else "8px"
    a=20+index*2
    b=30+index*3
    gap=(0,3,6,9)[index%4]
    bound="max_width" if upper else "min_width"
    nodes=[
        LayoutNode("root",None,"Flex",_typed({
            "direction":"row","width":"400px","height":"120px",
            "align_items":"flex-start",
        })),
        LayoutNode("outer","root","Flex",_typed({
            "direction":"row","width":initial,"height":"auto",
            "flex_basis":"auto","flex_shrink":0,
            "wrap":"nowrap","min_width":"0px" if upper else mode,
            **({"max_width":mode} if upper else {}),
            "align_items":"flex-start",
            "column_gap":f"{gap}px" if not nested else "0px",
        })),
    ]
    parent="outer"
    middle_open=middle_close=""
    if nested:
        nodes.append(LayoutNode("inner","outer","Flex",_typed({
            "direction":"row","width":"auto","height":"auto",
            "flex_basis":"auto","flex_shrink":0,"min_width":"0px",
            "wrap":"nowrap","column_gap":f"{gap}px",
            "align_items":"flex-start",
        })))
        parent="inner"
        middle_open=(
            f"<div id='inner' style='display:flex;flex-direction:row;"
            f"flex:0 0 auto;width:auto;height:auto;min-width:0;"
            f"column-gap:{gap}px;align-items:flex-start;box-sizing:content-box'>"
        )
        middle_close="</div>"
    for child,width in (("a",a),("b",b)):
        nodes.append(LayoutNode(child,parent,"Box",_typed({
            "width":f"{width}px","height":"20px",
            "flex_basis":f"{width}px","flex_shrink":0,"min_width":"0px",
        })))
    snapshot=LayoutInput(
        1,91000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(400,True),AvailableSize(120,True)),
        tuple(nodes),(),
    )
    bound_css=f"max-width:{mode};min-width:0;" if upper else f"min-width:{mode};"
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;width:400px;height:120px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='outer' style='display:flex;flex-direction:row;"
        f"width:{initial};height:auto;flex:0 0 auto;"
        f"flex-wrap:nowrap;align-items:flex-start;"
        f"column-gap:{gap if not nested else 0}px;{bound_css}box-sizing:content-box'>"
        +middle_open
        +f"<div id='a' style='width:{a}px;height:20px;flex:0 0 {a}px;"
        "min-width:0;box-sizing:content-box'></div>"
        +f"<div id='b' style='width:{b}px;height:20px;flex:0 0 {b}px;"
        "min-width:0;box-sizing:content-box'></div>"
        +middle_close+"</div></div></body></html>"
    )
    observed=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const rect=el.getBoundingClientRect();
            return [el.id,{x:rect.x,y:rect.y,width:rect.width,height:rect.height}];
        })
    )""")
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    run=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        capture_output=True,text=True,check=True,timeout=30)
    wire=json.loads(run.stdout)
    assert wire["ok"],wire.get("error")
    rs={item["node_id"]:item["border"] for item in wire["result"]["boxes"]}
    assert set(py)==set(rs)==set(observed)
    for name,rect in observed.items():
        for axis,want in rect.items():
            p=getattr(py[name].border,axis)
            r=rs[name][axis]
            assert abs(p-want)<=0.01,(index,name,axis,"python",p,"chrome",want)
            assert abs(r-want)<=0.01,(index,name,axis,"rust",r,"chrome",want)
            assert p==r,(index,name,axis,p,r)
