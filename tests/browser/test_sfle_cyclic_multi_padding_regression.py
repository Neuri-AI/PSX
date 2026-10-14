"""F2.1 RED: CSS cyclic percentage padding with multiple auto-inline siblings.

Chromium provides true intrinsic parent width, then resolves each sibling's
percentage padding against that used width. Rejecting the graph solely because
it has two siblings violates CSS; old N06 unrelated indefinite-root cases
still MUST reject. Both engines and every border rectangle are required.
"""
from __future__ import annotations

import json
import subprocess
import pytest

from fuzz_dimension_helpers import _typed, rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
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


@pytest.mark.parametrize("index",range(8))
def test_auto_inline_parent_multiple_percentage_padding_siblings(index,page,rust_binary):
    root_width=220+index*7
    a_width=24+index
    b_width=36+index
    pad_a=10+(index%3)*5
    pad_b=5+(index%4)*5
    snapshot=LayoutInput(
        1,420+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(100,True)),
        (
            LayoutNode("root",None,"Flex",_typed({
                "direction":"row","width":f"{root_width}px","height":"100px",
                "align_items":"flex-start",
            })),
            LayoutNode("wrapper","root","Flex",_typed({
                "direction":"row","width":"auto","height":"auto",
                "flex_basis":"auto","flex_grow":0,"flex_shrink":0,
                "min_width":"0px","align_items":"flex-start",
            })),
            LayoutNode("a","wrapper","Box",_typed({
                "width":f"{a_width}px","height":"20px",
                "flex_basis":f"{a_width}px","flex_shrink":0,
                "layout_padding_left":f"{pad_a}%",
            })),
            LayoutNode("b","wrapper","Box",_typed({
                "width":f"{b_width}px","height":"16px",
                "flex_basis":f"{b_width}px","flex_shrink":0,
                "layout_padding_right":f"{pad_b}%",
            })),
        ),(),
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_width}px;height:100px;"
        "align-items:flex-start;box-sizing:content-box'>"
        "<div id='wrapper' style='display:flex;flex-direction:row;flex:0 0 auto;"
        "width:auto;height:auto;min-width:0;align-items:flex-start;box-sizing:content-box'>"
        f"<div id='a' style='width:{a_width}px;height:20px;flex:0 0 {a_width}px;"
        f"padding-left:{pad_a}%;box-sizing:content-box'></div>"
        f"<div id='b' style='width:{b_width}px;height:16px;flex:0 0 {b_width}px;"
        f"padding-right:{pad_b}%;box-sizing:content-box'></div>"
        "</div></div></body></html>"
    )
    observed=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(element=>{
            const rect=element.getBoundingClientRect();
            return [element.id,{x:rect.x,y:rect.y,
                width:rect.width,height:rect.height}];
        })
    )""")
    python=dict(PythonLayoutEngine().compute(snapshot).boxes)
    process=subprocess.run(
        [str(rust_binary)],input=serialize_snapshot(snapshot),
        capture_output=True,text=True,check=True,timeout=30,
    )
    native=json.loads(process.stdout)
    assert native["ok"],f"Rust rejected CSS-permitted cyclic siblings: {native.get('error')}"
    rust={entry["node_id"]:entry["border"] for entry in native["result"]["boxes"]}
    assert set(python)==set(rust)==set(observed)
    assert abs(observed["wrapper"]["width"]-(a_width+b_width))<=0.01
    for node_id,rectangle in observed.items():
        for axis,wanted in rectangle.items():
            pv=getattr(python[node_id].border,axis)
            rv=rust[node_id][axis]
            assert abs(pv-wanted)<=0.01,(
                f"cyclic multi sibling[{index}] Python {node_id}.{axis}={pv} Chromium={wanted}"
            )
            assert abs(rv-wanted)<=0.01,(
                f"cyclic multi sibling[{index}] Rust {node_id}.{axis}={rv} Chromium={wanted}"
            )
            assert pv==rv,("Rust/Python raw geometry mismatch",index,node_id,axis,pv,rv)


@pytest.mark.parametrize("seed",(0xC0A551,0xC0A552,0xC0A553))
@pytest.mark.parametrize("index",range(16))
def test_cyclic_padding_randomized_fixed_sibling_groups(
    seed,index,page,rust_binary,
):
    """Positive CSS cycles beyond the original two-item special case."""
    import random
    rng=random.Random(seed+index*17)
    n=rng.randint(3,6)
    root_w=260+index*7
    gap=rng.choice((0,2,4,8))
    entries=[(rng.randint(16,48),rng.choice((5,10,15,20,30)),rng.choice((True,False)))
             for _ in range(n)]
    nodes=[
        LayoutNode("root",None,"Flex",_typed({
            "direction":"row","width":f"{root_w}px","height":"80px",
            "align_items":"flex-start",
        })),
        LayoutNode("wrapper","root","Flex",_typed({
            "direction":"row","width":"auto","height":"auto",
            "flex_basis":"auto","flex_shrink":0,
            "min_width":"0px","column_gap":f"{gap}px",
            "align_items":"flex-start",
        })),
    ]
    dom=[]
    for i,(size,pct,on_left) in enumerate(entries):
        edge="layout_padding_left" if on_left else "layout_padding_right"
        css="padding-left" if on_left else "padding-right"
        nodes.append(LayoutNode(f"n{i}","wrapper","Box",_typed({
            "width":f"{size}px","height":"20px",
            "flex_basis":f"{size}px","flex_shrink":0,
            edge:f"{pct}%",
        })))
        dom.append(
            f"<div id='n{i}' style='width:{size}px;height:20px;"
            f"flex:0 0 {size}px;{css}:{pct}%;box-sizing:content-box'></div>"
        )
    snapshot=LayoutInput(
        1,55000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_w,True),AvailableSize(80,True)),
        tuple(nodes),(),
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_w}px;height:80px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='wrapper' style='display:flex;flex-direction:row;"
        f"width:auto;height:auto;flex:0 0 auto;min-width:0;"
        f"column-gap:{gap}px;align-items:flex-start;box-sizing:content-box'>"
        +"".join(dom)+"</div></div></body></html>"
    )
    observed=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    process=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30)
    result=json.loads(process.stdout)
    assert result["ok"],result.get("error")
    rs={item["node_id"]:item["border"] for item in result["result"]["boxes"]}
    assert set(py)==set(rs)==set(observed)
    for node,rect in observed.items():
        for axis,wanted in rect.items():
            pv=getattr(py[node].border,axis)
            rv=rs[node][axis]
            assert abs(pv-wanted)<=0.01,(
                f"cycle {seed:x} index={index} {node}.{axis}: "
                f"Python={pv}, Chromium={wanted}, siblings={entries}"
            )
            assert abs(rv-wanted)<=0.01,(
                f"cycle {seed:x} index={index} {node}.{axis}: "
                f"Rust={rv}, Chromium={wanted}, siblings={entries}"
            )
            assert pv==rv,(seed,index,node,axis,pv,rv)
