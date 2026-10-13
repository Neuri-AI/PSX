"""Independent Chromium numeric controls for intrinsic and cyclic F2 cases."""
import json
from pathlib import Path

import pytest

CORPUS=json.loads((Path(__file__).resolve().parents[1]/
    "sfle/fixtures/f2_alpha_acceptance.json").read_text())


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page(viewport={"width":800,"height":600},
                                   device_scale_factor=1)
        finally:
            browser.close()


_HTML={
    "A02":'<div id="root" style="display:inline-flex;width:auto"><div id="child" style="flex:0 0 auto;width:100px;height:20px"></div></div>',
    "A03":'<div id="root" style="display:flex;flex-direction:column;width:120px;height:auto"><div id="inner" style="height:50%;min-height:0"><div style="height:30px"></div></div></div>',
    "A05":'<div id="root" style="display:flex;width:70px;align-items:stretch"><div id="a" style="flex:0 1 50px;min-width:0;height:120px"></div><div id="b" style="flex:0 1 50px;min-width:0;height:120px"></div></div>',
    "C04":'<div id="root" style="display:inline-flex;width:auto;column-gap:10%"><div id="a" style="flex:0 0 20px;height:10px"></div><div id="b" style="flex:0 0 20px;height:10px"></div></div>',
    "C05":'<div id="root" style="display:flex;width:120px;height:auto"><div id="child" style="height:50%;min-height:0"><div style="height:30px"></div></div></div>',
    "C06":'<div id="root" style="display:flex;width:400px;height:100px"><div id="child" style="padding-top:10%;box-sizing:content-box"></div></div>',
    # Fractional acceptance cases match the fixed snapshots F01 and F02.
    "F01":'<div id="root" style="display:flex;width:96px;height:60px;column-gap:4px;align-items:flex-start">'
          '<div id="n0" style="width:30px;height:20px;flex:0 0 auto;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '<div id="n1" style="width:30px;height:20px;flex:0 0 40%;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '<div id="n2" style="width:25%;height:20px;flex:0 0 20px;min-width:0;padding-top:10%;box-sizing:content-box"></div>'
          '</div>',

    "F04":'<div id="root" style="display:flex;width:200px;height:60px;column-gap:4px;align-items:flex-start">'
          '<div id="n0" style="width:auto;height:20px;flex:1 0 25%;min-width:0;padding-top:4px;box-sizing:content-box"></div>'
          '<div id="n1" style="width:20px;height:20px;flex:1 1 40%;min-width:0;padding-top:10%;box-sizing:content-box"></div>'
          '<div id="n2" style="width:auto;height:20px;flex:0 1 20px;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '<div id="n3" style="width:30px;height:20px;flex:0 1 40%;min-width:0;padding-top:10%;box-sizing:content-box"></div>'
          '</div>',
    "F05":'<div id="root" style="display:flex;width:240px;height:60px;column-gap:5%;align-items:flex-start">'
          '<div id="n0" style="width:30px;height:20px;flex:1 0 20px;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '<div id="n1" style="width:20px;height:20px;flex:1 1 30px;min-width:0;padding-top:0px;box-sizing:content-box"></div>'
          '<div id="n2" style="width:25%;height:20px;flex:1 0 25%;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '<div id="n3" style="width:30px;height:20px;flex:2 0 20px;min-width:0;padding-top:5%;box-sizing:content-box"></div>'
          '</div>',
    # N05: old fail-closed freeze metadata now has a direct Chromium oracle.
    "N05":'<div id="root" style="display:flex;width:100px;height:60px">'
          '<div id="a" style="width:20px;height:20px;flex:0 0 20px;min-width:40px"></div>'
          '<div id="b" style="width:80px;height:20px;flex:0 1 80px;min-width:0"></div>'
          '</div>',
    "F02":'<div id="root" style="display:flex;width:96px;height:60px;column-gap:10%;align-items:flex-start">'
          '<div id="n0" style="width:20px;height:20px;flex:2 1 20px;min-width:0;padding-top:10%;box-sizing:content-box"></div>'
          '<div id="n1" style="width:auto;height:20px;flex:2 1 30px;min-width:0;padding-top:10%;box-sizing:content-box"></div>'
          '<div id="n2" style="width:20px;height:20px;flex:2 1 auto;min-width:0;padding-top:0px;box-sizing:content-box"></div>'
          '</div>',
}


@pytest.mark.parametrize("case_id",list(_HTML))
def test_numeric_css_reference_in_real_chromium(case_id,page):
    case=next(case for case in CORPUS["cases"] if case["id"]==case_id)
    page.set_content('<!doctype html><html><body style="margin:0">'+
                     _HTML[case_id]+'</body></html>')
    observed=page.evaluate("""() => Object.fromEntries(
        Array.from(document.querySelectorAll('[id]'),el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height,
                padding_top:parseFloat(getComputedStyle(el).paddingTop)}];
        })
    )""")
    expected=case["expected"]
    for key,wanted in expected.items():
        if isinstance(wanted,bool) or not isinstance(wanted,(float,int)):continue
        if key=="intrinsic_gap":continue
        if key=="used_gap":
            actual=observed["b"]["x"]-(observed["a"]["x"]+observed["a"]["width"])
        elif "." in key:
            node_id,field=key.split(".",1)
            actual=observed[node_id][field]
        else:continue
        assert actual==pytest.approx(wanted,abs=CORPUS["tolerance_px"]),(
            f"{case_id}: Chromium {key}={actual}, canonical expected={wanted}"
        )



@pytest.mark.parametrize("mode", ("main", "cross"))
def test_fractional_space_evenly_matches_chromium_layout_units(page, mode):
    """Chromium 153 is the external oracle, not the helper's own expected data."""
    from psx.sfle.align_content import AlignContent, distribute_cross_lines
    from psx.sfle.main_alignment import JustifyContent, resolve_main_alignment

    if mode == "main":
        page.set_content(
            '<!doctype html><html><body style="margin:0">'
            '<div style="display:flex;width:100px;height:100px;'
            'justify-content:space-evenly;column-gap:10px;align-items:flex-start">'
            '<div id="a" style="flex:0 0 20px;height:20px"></div>'
            '<div id="b" style="flex:0 0 20px;height:20px"></div>'
            '</div></body></html>'
        )
        result = resolve_main_alignment(
            JustifyContent.SPACE_EVENLY, 100, (20,20), gap=10
        )
        predicted = (result.leading_space,
                     result.leading_space + 20 + result.between_space)
        axis = "x"
    else:
        page.set_content(
            '<!doctype html><html><body style="margin:0">'
            '<div style="display:flex;flex-wrap:wrap;width:100px;height:100px;'
            'align-content:space-evenly;row-gap:10px;align-items:flex-start">'
            '<div id="a" style="flex:0 0 60px;height:20px"></div>'
            '<div id="b" style="flex:0 0 60px;height:20px"></div>'
            '</div></body></html>'
        )
        result = distribute_cross_lines(
            AlignContent.SPACE_EVENLY, 100, (20,20), gap=10
        )
        predicted = result.starts
        axis = "y"

    observed = page.evaluate("""axis => ['a','b'].map(id => {
        const rect=document.getElementById(id).getBoundingClientRect();
        return axis==='x' ? rect.x : rect.y;
    })""", axis)
    for index in range(2):
        assert abs(predicted[index] - observed[index]) <= CORPUS["tolerance_px"], (
            f"space-evenly {mode}[{index}]: SFLE={predicted[index]} "
            f"Chromium={observed[index]}"
        )
