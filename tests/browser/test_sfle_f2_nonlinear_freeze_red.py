"""F2.1 deterministic out-of-sample nonlinear flex min/max freeze oracle.

200 seeded multi-item snapshots exercise positive and negative free-space,
freezing of items at opposing bounds, shrink factors and contradictory
min/max (minimum precedence). Every observed Chromium rectangle is compared
against both real SFLE engines; unsupported or approximate verdicts fail.
"""
from __future__ import annotations
import json
import random
import subprocess
import pytest
from f2_fuzz_dimension_helpers import _typed, rust_binary
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize,LayoutConstraints,LayoutInput,LayoutNode,WritingDirection
from psx.sfle.native_wire import serialize_snapshot

SEEDS=(0xA1B001,0xA1B002,0xA1B003,0xA1B004,0xA1B005)


def generate():
    for seed in SEEDS:
        rng=random.Random(seed)
        for index in range(40):
            width=rng.choice((140,210,260,315,440))
            gap=rng.choice((0,2,4,8))
            count=rng.randint(2,6)
            items=[]
            for _ in range(count):
                basis=rng.choice((14,20,28,40,65,85,105))
                minimum=rng.choice((0,0,12,24,40,60,110,160))
                maximum=rng.choice((None,None,18,24,40,65,85,120,180))
                items.append((basis,rng.choice((0,1,2,3)),
                    rng.choice((0,1,2,3)),minimum,maximum))
            yield seed,index,width,gap,items


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


@pytest.mark.parametrize("case",tuple(generate()),
    ids=lambda case:f"seed-{case[0]:x}-case-{case[1]:02d}")
def test_browser_iterative_flex_freeze_with_heterogeneous_bounds(
    case,page,rust_binary,
):
    seed,index,width,gap,items=case
    nodes=[LayoutNode("root",None,"Flex",_typed({
        "direction":"row","width":f"{width}px","height":"90px",
        "column_gap":f"{gap}px","align_items":"flex-start",
    }))]
    dom=[]
    for i,(basis,grow,shrink,minimum,maximum) in enumerate(items):
        style={"width":f"{basis}px","height":"20px",
               "flex_basis":f"{basis}px","flex_grow":grow,
               "flex_shrink":shrink,"min_width":f"{minimum}px"}
        css=(f"width:{basis}px;height:20px;flex:{grow} {shrink} {basis}px;"
             f"min-width:{minimum}px;box-sizing:content-box;")
        if maximum is not None:
            style["max_width"]=f"{maximum}px"
            css+=f"max-width:{maximum}px;"
        nodes.append(LayoutNode(f"n{i}","root","Box",_typed(style)))
        dom.append(f"<div id='n{i}' style='{css}'></div>")
    snapshot=LayoutInput(
        1,95000+index,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(width,True),AvailableSize(90,True)),
        tuple(nodes),(),
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{width}px;height:90px;"
        f"column-gap:{gap}px;align-items:flex-start;box-sizing:content-box'>"
        +"".join(dom)+"</div></body></html>"
    )
    expected=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    python=dict(PythonLayoutEngine().compute(snapshot).boxes)
    process=subprocess.run([str(rust_binary)],
        input=serialize_snapshot(snapshot),capture_output=True,text=True,
        check=True,timeout=30)
    wire=json.loads(process.stdout)
    assert wire["ok"],(case,wire.get("error"))
    rust={v["node_id"]:v["border"] for v in wire["result"]["boxes"]}
    assert set(python)==set(rust)==set(expected)
    for node,rect in expected.items():
        for axis,wanted in rect.items():
            p=getattr(python[node].border,axis)
            r=rust[node][axis]
            assert abs(p-wanted)<=0.01,(
                f"freeze seed={seed:x} index={index} {node}.{axis}: "
                f"Python={p}, Chromium={wanted}, items={items}"
            )
            assert abs(r-wanted)<=0.01,(
                f"freeze seed={seed:x} index={index} {node}.{axis}: "
                f"Rust={r}, Chromium={wanted}, items={items}"
            )
            assert p==r,("Rust/Python raw flex freeze divergence",case,node,axis,p,r)
