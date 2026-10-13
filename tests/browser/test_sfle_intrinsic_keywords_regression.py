"""F2.1 RED: CSS min/max-content intrinsic keywords, live Chromium oracle.

The browser independently supplies measured intrinsic widths; no invented
expected geometry and no parsing-only test counts as support. Python and Rust
must match every border coordinate at 0.01 CSS px with identical snapshot.
Unsupported alternative intrinsic keywords remain outside this incremental
acceptance until independently certified.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from fuzz_dimension_helpers import _typed, rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput, LayoutNode,
    MeasuredBox, WritingDirection,
)
from psx.sfle.native_wire import serialize_snapshot

TOLERANCE=0.01
TEXTS=("AAAA BBBBBBB", "abcdefgh ij klmnopq", "alpha beta gamma delta")


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
@pytest.mark.parametrize("keyword",("min-content","max-content"))
@pytest.mark.parametrize("placement",("flex_basis","width"))
def test_chromium_intrinsic_keyword_uses_actual_measured_leaf_content(
    page,rust_binary,text,keyword,placement,
):
    root_width=260
    basis=keyword if placement=="flex_basis" else "auto"
    width=keyword if placement=="width" else "auto"
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;width:260px;height:70px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='leaf' style='font:10px/20px monospace;white-space:normal;"
        f"width:{width};height:20px;flex:0 0 {basis};min-width:0;"
        f"box-sizing:content-box'>{text}</div>"
        "</div></body></html>"
    )
    # Measure the content's min/max intrinsic widths separately under the
    # browser's own CSS algorithm. The measured values feed both engines.
    observed=page.evaluate("""() => {
        const leaf=document.getElementById('leaf');
        const sizes={};
        for(const mode of ['min-content','max-content']){
            const probe=leaf.cloneNode(true);
            probe.removeAttribute('id');
            probe.style.position='absolute';
            probe.style.display='block';
            probe.style.flex='none';
            probe.style.width=mode;
            probe.style.minWidth='0';
            document.body.appendChild(probe);
            sizes[mode]=probe.getBoundingClientRect().width;
            probe.remove();
        }
        const nodes={};
        for(const id of ['root','leaf']){
            const r=document.getElementById(id).getBoundingClientRect();
            nodes[id]={x:r.x,y:r.y,width:r.width,height:r.height};
        }
        return {nodes,sizes};
    }""")
    low=observed["sizes"]["min-content"]
    high=observed["sizes"]["max-content"]
    assert low < high,("Oracle text does not distinguish intrinsic modes",text,observed)
    sizes=IntrinsicSizes(low,high,20,20,high,20)
    snapshot=LayoutInput(
        1,300,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(70,True)),
        (
            LayoutNode("root",None,"Flex",_typed({
                "direction":"row","width":"260px","height":"70px",
                "align_items":"flex-start",
            })),
            LayoutNode("leaf","root","Text",_typed({
                "width":width,"height":"20px",
                "flex_basis":basis,"flex_grow":0,"flex_shrink":0,
                "min_width":"0px",
            })),
        ),
        (
            MeasuredBox(
                "leaf",sizes,LayoutConstraints(
                    AvailableSize(None,False),AvailableSize(None,False)
                ),0,
            ),
        ),
    )
    py=dict(PythonLayoutEngine().compute(snapshot).boxes)
    process=subprocess.run(
        [str(rust_binary)],input=serialize_snapshot(snapshot),
        text=True,capture_output=True,check=True,timeout=30,
    )
    native=json.loads(process.stdout)
    assert native["ok"],native.get("error")
    rs={box["node_id"]:box["border"] for box in native["result"]["boxes"]}
    for node,rect in observed["nodes"].items():
        for axis,wanted in rect.items():
            p=getattr(py[node].border,axis)
            r=rs[node][axis]
            assert abs(p-wanted)<=TOLERANCE,(
                f"{placement}={keyword} {node}.{axis} Python={p} Chromium={wanted}"
            )
            assert abs(r-wanted)<=TOLERANCE,(
                f"{placement}={keyword} {node}.{axis} Rust={r} Chromium={wanted}"
            )
            assert p==r,("Python/Rust intrinsic keyword geometry mismatch",node,axis,p,r)
