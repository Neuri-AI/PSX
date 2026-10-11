"""F2.1 RED direct intrinsic min/max-content bounds on nested Flex columns.

Unlike leaf constraints, min/max-content on a Flex *container* depends on
descendant contributions. These 24 browser cases certify true recursive
column cross intrinsic constraints with fixed descendants.
"""
from __future__ import annotations
import json
import subprocess
import pytest
from f2_fuzz_dimension_helpers import _typed, rust_binary
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


@pytest.mark.parametrize("index",range(24))
def test_browser_nested_column_intrinsic_width_bound(index,page,rust_binary):
    mode=("min_min","min_max","max_min","max_max")[index%4]
    nested=index%3==0
    minwidth,maxwidth={
        "min_min":("min-content",None),
        "min_max":("max-content",None),
        "max_min":("0px","min-content"),
        "max_max":("0px","max-content"),
    }[mode]
    width="8px" if mode.startswith("min_") else "240px"
    a=30+index*2
    b=50+index
    root_style={"direction":"row","width":"400px","height":"100px",
        "align_items":"flex-start"}
    outer_style={"direction":"column","width":width,"height":"auto",
        "flex_basis":"auto","flex_shrink":0,"min_width":minwidth,
        "align_items":"flex-start"}
    if maxwidth is not None:outer_style["max_width"]=maxwidth
    nodes=[
        LayoutNode("root",None,"Flex",_typed(root_style)),
        LayoutNode("outer","root","Flex",_typed(outer_style)),
    ]
    leaf_parent="outer"
    inner_start=inner_end=""
    if nested:
        nodes.append(LayoutNode("inner","outer","Flex",_typed({
            "direction":"column","width":"auto","height":"auto",
            "flex_basis":"auto","flex_shrink":0,"min_width":"0px",
            "align_items":"flex-start",
        })))
        leaf_parent="inner"
        inner_start="<div id='inner' style='display:flex;flex-direction:column;flex:0 0 auto;width:auto;height:auto;min-width:0;align-items:flex-start;box-sizing:content-box'>"
        inner_end="</div>"
    nodes.extend((
        LayoutNode("a",leaf_parent,"Box",_typed({
            "width":f"{a}px","height":"20px",
            "flex_basis":"20px","flex_shrink":0,"min_width":"0px",
        })),
        LayoutNode("b",leaf_parent,"Box",_typed({
            "width":f"{b}px","height":"22px",
            "flex_basis":"22px","flex_shrink":0,"min_width":"0px",
        })),
    ))
    snapshot=LayoutInput(
        1,7000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(400,True),AvailableSize(100,True)),
        tuple(nodes),(),
    )
    css=(f"min-width:{minwidth};"
         +(f"max-width:{maxwidth};" if maxwidth is not None else ""))
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;width:400px;height:100px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='outer' style='display:flex;flex-direction:column;"
        f"width:{width};height:auto;flex:0 0 auto;align-items:flex-start;"
        f"{css}box-sizing:content-box'>"
        +inner_start
        +f"<div id='a' style='width:{a}px;height:20px;"
        "flex:0 0 20px;min-width:0;box-sizing:content-box'></div>"
        +f"<div id='b' style='width:{b}px;height:22px;"
        "flex:0 0 22px;min-width:0;box-sizing:content-box'></div>"
        +inner_end+"</div></div></body></html>"
    )
    expected=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    run=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30)
    wire=json.loads(run.stdout)
    assert wire["ok"],wire.get("error")
    rs={v["node_id"]:v["border"] for v in wire["result"]["boxes"]}
    for node,rect in expected.items():
        for axis,wanted in rect.items():
            p=getattr(py[node].border,axis)
            r=rs[node][axis]
            assert abs(p-wanted)<=0.01,(index,mode,nested,node,axis,"py",p,"chrome",wanted)
            assert abs(r-wanted)<=0.01,(index,mode,nested,node,axis,"rust",r,"chrome",wanted)
            assert p==r,(index,mode,nested,node,axis,p,r)


@pytest.mark.parametrize("index",range(24))
def test_browser_row_and_column_intrinsic_block_axis_constraints(
    index,page,rust_binary,
):
    """RED F2.1: container min/max-content on auto-independent block axis."""
    direction="column" if index%2==0 else "row"
    upper=(index//2)%2==1
    keyword=("min-content","max-content")[(index//4)%2]
    initial="180px" if upper else "8px"
    count=2+(index//8)%2
    gap=3+index%5
    sizes=tuple(17+index+i*13 for i in range(count))
    bounds=(f"max-height:{keyword};min-height:0;"
            if upper else f"min-height:{keyword};")
    outer_style={
        "direction":direction,"width":"150px","height":initial,
        "flex_basis":"150px","flex_shrink":0,
        "min_width":"0px","align_items":"flex-start",
        "row_gap":f"{gap}px" if direction=="column" else "0px",
    }
    if upper:
        outer_style["max_height"]=keyword
        outer_style["min_height"]="0px"
    else:
        outer_style["min_height"]=keyword
    nodes=[
        LayoutNode("root",None,"Flex",_typed({
            "direction":"row","width":"350px","height":"240px",
            "align_items":"flex-start",
        })),
        LayoutNode("outer","root","Flex",_typed(outer_style)),
    ]
    dom=[]
    for i,height in enumerate(sizes):
        nodes.append(LayoutNode(f"n{i}","outer","Box",_typed({
            "width":"25px","height":f"{height}px",
            "flex_basis":f"{height}px" if direction=="column" else "25px",
            "flex_shrink":0,"min_width":"0px","min_height":"0px",
        })))
        basis=f"{height}px" if direction=="column" else "25px"
        dom.append(
            f"<div id='n{i}' style='width:25px;height:{height}px;"
            f"flex:0 0 {basis};min-width:0;min-height:0;"
            f"box-sizing:content-box'></div>"
        )
    snapshot=LayoutInput(
        1,121000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(350,True),AvailableSize(240,True)),
        tuple(nodes),(),
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;width:350px;height:240px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='outer' style='display:flex;flex-direction:{direction};"
        f"width:150px;height:{initial};flex:0 0 150px;"
        f"min-width:0;align-items:flex-start;row-gap:{gap if direction=='column' else 0}px;"
        f"{bounds}box-sizing:content-box'>"
        +"".join(dom)+"</div></div></body></html>"
    )
    browser=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    proc=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        capture_output=True,text=True,check=True,timeout=30)
    wire=json.loads(proc.stdout)
    assert wire["ok"],wire.get("error")
    rs={v["node_id"]:v["border"] for v in wire["result"]["boxes"]}
    assert set(browser)==set(py)==set(rs)
    for name,rect in browser.items():
        for axis,want in rect.items():
            p=getattr(py[name].border,axis)
            r=rs[name][axis]
            assert abs(p-want)<=0.01,(index,name,axis,p,want,"python")
            assert abs(r-want)<=0.01,(index,name,axis,r,want,"rust")
            assert p==r,(index,name,axis,p,r)
