"""F2.1 RED: transitive auto-row cyclic percentage padding contributions.

The leaf's percentage padding contributes zero while determining nested
auto-width intrinsic sizes, then resolves against the final used inline
size. Its containing block can be two to four auto-row ancestors away
from the definite root, not just the previous direct-parent special case.
Unknown indefinite-root dependencies must keep the existing N06 rejection.
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
def test_transitive_auto_inline_percentage_padding_through_nested_rows(
    index,page,rust_binary,
):
    depth=2+index%3
    root_width=230+index*3
    leaf_width=22+index
    percent=5+5*(index%7)
    side="left" if index%2 else "right"
    nodes=[LayoutNode("root",None,"Flex",_typed({
        "direction":"row","width":f"{root_width}px","height":"80px",
        "align_items":"flex-start",
    }))]
    wrappers=[]
    parent="root"
    for i in range(depth):
        node_id=f"w{i}"
        wrappers.append(node_id)
        nodes.append(LayoutNode(node_id,parent,"Flex",_typed({
            "direction":"row","width":"auto","height":"auto",
            "flex_basis":"auto","flex_shrink":0,
            "min_width":"0px","align_items":"flex-start",
        })))
        parent=node_id
    nodes.append(LayoutNode("leaf",parent,"Box",_typed({
        "width":f"{leaf_width}px","height":"20px",
        "flex_basis":f"{leaf_width}px","flex_shrink":0,
        f"layout_padding_{side}":f"{percent}%",
    })))
    snapshot=LayoutInput(
        1,76100+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(80,True)),
        tuple(nodes),(),
    )
    head=(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_width}px;height:80px;"
        f"align-items:flex-start;box-sizing:content-box'>"
    )
    for node_id in wrappers:
        head+=(
            f"<div id='{node_id}' style='display:flex;flex-direction:row;"
            "width:auto;height:auto;flex:0 0 auto;min-width:0;"
            "align-items:flex-start;box-sizing:content-box'>"
        )
    head+=(
        f"<div id='leaf' style='width:{leaf_width}px;height:20px;"
        f"flex:0 0 {leaf_width}px;padding-{side}:{percent}%;"
        "box-sizing:content-box'></div>"
        +"</div>"*(depth+1)+"</body></html>"
    )
    page.set_content(head)
    browser=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    assert abs(browser[wrappers[-1]]["width"]-leaf_width)<=0.01
    python=dict(PythonLayoutEngine().compute(snapshot).boxes)
    proc=subprocess.run([str(rust_binary)],input=serialize_snapshot(snapshot),
        capture_output=True,text=True,check=True,timeout=30)
    native=json.loads(proc.stdout)
    assert native["ok"],native.get("error")
    rust={box["node_id"]:box["border"] for box in native["result"]["boxes"]}
    assert set(browser)==set(python)==set(rust)
    for node,rect in browser.items():
        for axis,want in rect.items():
            p=getattr(python[node].border,axis)
            r=rust[node][axis]
            assert abs(p-want)<=0.01,(
                f"transitive padding index={index} {node}.{axis} "
                f"Python={p} Chromium={want}"
            )
            assert abs(r-want)<=0.01,(
                f"transitive padding index={index} {node}.{axis} "
                f"Rust={r} Chromium={want}"
            )
            assert p==r,(index,node,axis,p,r)
