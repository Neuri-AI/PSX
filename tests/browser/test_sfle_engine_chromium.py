"""A01 end-to-end: same canonical tree through Python SFLE and Chromium."""
import json
from pathlib import Path
import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.lengths import parse_length
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


@pytest.fixture(scope="module")
def chromium_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            browser.close()


def test_A01_python_engine_final_rectangles_match_chromium(chromium_page):
    payload = json.loads((Path(__file__).resolve().parents[1] /
        "sfle/fixtures/f2_alpha_acceptance.json").read_text())
    case = next(x for x in payload["cases"] if x["id"]=="A01")
    def normalize(value):
        return parse_length(value) if isinstance(value,str) and (
            value=="auto" or value.endswith("%") or value.endswith("px")
        ) else value
    nodes = tuple(LayoutNode(
        n["node_id"],n["parent_id"],n["component"],
        tuple((k,normalize(v)) for k,v in n["style"].items()),
    ) for n in case["nodes"])
    m = case["measurements"][0]
    metrics = IntrinsicSizes(20,80,20,60,80,60)
    snapshot = LayoutInput(1,29,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(120,True),AvailableSize(None,False)),
        nodes,(MeasuredBox(m["node"],metrics,LayoutConstraints(
            AvailableSize(m["at_width"],True),AvailableSize(m["height"],True)),0),))
    sfle = PythonLayoutEngine().compute(snapshot)
    chromium_page.set_content("""<!doctype html><html><body style="margin:0">
      <div id="root" style="display:flex;width:120px;align-items:stretch">
        <div id="fixed" style="flex:0 0 40px;width:40px;height:10px;min-width:0"></div>
        <div id="column" style="display:flex;flex-direction:column;flex:0 0 80px;width:80px;height:auto;min-width:0">
          <div id="text" style="width:100%;height:auto;min-width:0;font:16px/20px monospace">
            <div style="height:20px">line 1</div><div style="height:20px">line 2</div><div style="height:20px">line 3</div>
          </div>
        </div>
      </div></body></html>""")
    actual = chromium_page.evaluate("""() => Object.fromEntries(
      ['root','fixed','column','text'].map(id => {
        const r=document.getElementById(id).getBoundingClientRect();
        return [id,{x:r.x,y:r.y,width:r.width,height:r.height}];
      })
    )""")
    assert tuple(node_id for node_id,_ in sfle.boxes)==tuple(n["node_id"] for n in case["nodes"])
    for node_id,box in sfle.boxes:
        for axis in ("x","y","width","height"):
            assert getattr(box.border,axis)==pytest.approx(
                actual[node_id][axis],abs=payload["tolerance_px"]
            ), f"A01 {node_id}.{axis} SFLE vs Chromium"
    assert dict(sfle.boxes)["root"].content.height==pytest.approx(case["expected"]["root.height"],abs=0.01)
