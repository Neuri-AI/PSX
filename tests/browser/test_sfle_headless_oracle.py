"""Independent live Chromium vs *actual Headless measurement port* + SFLE.

Unlike an intrinsic mock with hand-written final dimensions, the test asks
Chromium 153 to measure the width-constrained text on each real measurement
round; HeadlessMeasurementSource transports those immutable intrinsic metrics.
Both Python and Rust must converge to browser-observed border geometry.
"""
from dataclasses import replace
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "interop"))
sys.path.insert(0, str(ROOT / "tests" / "sfle"))

from test_sfle_differential import rust_binary  # noqa: E402
from test_acceptance_contract_regression import case_snapshot  # noqa: E402
from test_sfle_live_text_chromium import html_for, DATA  # noqa: E402
from width_measurement_helpers import rust_compute  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine  # noqa: E402
from psx.sfle.headless_measurement import HeadlessMeasurementSource  # noqa: E402
from psx.sfle.measurement_plan import MeasurementRequest  # noqa: E402
from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes  # noqa: E402
from psx.sfle.remeasure_session import compute_with_width_measurements  # noqa: E402


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version()
            yield browser.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            browser.close()


@pytest.mark.parametrize("case_id", ("A01", "A04", "A05"))
@pytest.mark.parametrize("backend", ("python", "rust"))
def test_live_browser_headless_port_round_trip(case_id,backend,page,rust_binary):
    live=next(entry for entry in DATA["cases"] if entry["id"]==case_id)["live_text"]
    page.set_content('<!doctype html><html><body style="margin:0">'
                     +html_for(case_id,live["text"])+'</body></html>')
    names=("a","b") if case_id=="A05" else ("text",)
    calls=[]
    snapshot=replace(case_snapshot(case_id),measurements=())

    def host_intrinsic(node_id,width):
        observed_height=page.evaluate("""({id,width}) => {
            const element=document.getElementById(id);
            const original={
                flex:element.style.flex,
                alignSelf:element.style.alignSelf,
                height:element.style.height,
                width:element.style.width
            };
            element.style.flex='none';
            element.style.alignSelf='flex-start';
            element.style.height='auto';
            element.style.width=width+'px';
            const measured=element.getBoundingClientRect().height;
            for (const [key,value] of Object.entries(original)) element.style[key]=value;
            return measured;
        }""",{"id":node_id,"width":width})
        metrics=IntrinsicSizes(0,100 if case_id=="A05" else 210,20,
                                observed_height,width,observed_height)
        source=HeadlessMeasurementSource(((node_id,metrics),))
        request=MeasurementRequest(
            node_id,
            LayoutConstraints(AvailableSize(width,True),AvailableSize(None,False)),
            snapshot.generation,0,
        )
        measured=source.port().measure(request)
        assert measured.node_id==node_id
        assert measured.constraints==request.constraints
        assert measured.revision==0
        calls.append((node_id,width,observed_height))
        return measured.intrinsic

    engine=PythonLayoutEngine()
    pure=(engine.compute if backend=="python"
          else lambda s:rust_compute(rust_binary,s))
    provisional=(engine.compute_provisional if backend=="python"
                 else lambda s:rust_compute(rust_binary,s,provisional=True))
    result=compute_with_width_measurements(
        snapshot,pure,host_intrinsic,
        compute_provisional=provisional,
        initial_widths={name:live["initial_width_px"] for name in names},
    )
    assert len(calls)==len(names)*live["expected_measurements_per_leaf"]
    for node in names:
        widths=[width for name,width,_ in calls if name==node]
        assert widths==pytest.approx(
            [live["initial_width_px"],live["final_width_px"]],abs=0.01,
        )
    actual=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el => {
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    assert tuple(actual)==tuple(node.node_id for node in snapshot.nodes)
    for node_id,box in result.boxes:
        for axis in ("x","y","width","height"):
            prediction=getattr(box.border,axis)
            observed=actual[node_id][axis]
            assert abs(prediction-observed)<=DATA["tolerance_px"],(
                f"{backend} headless port {case_id}.{node_id}.{axis}: "
                f"engine={prediction} independent Chromium={observed}"
            )


@pytest.mark.parametrize("root_width,share",((241,40),(260,50),(255,65),(280,75)))
@pytest.mark.parametrize("content",(
    "AAAA BBBBBBB CCCCC DDDDD EEEEE FFFFF GGGGG HHHHH",
    "alpha beta gamma delta epsilon zeta theta iota kappa lambda",
))
@pytest.mark.parametrize("backend",("python","rust"))
def test_nested_definite_percent_width_real_text_height_for_width(
    root_width,share,content,backend,page,rust_binary,
):
    """Live UI-thread-like Chromium measurement of a percentage nested column.

    Tests recursive cross-axis auto height after a measured Text leaf receives
    an exact percentage width from its definite grandparent. Both engines
    must agree with Chromium's actual rendered text line breaks and geometry.
    """
    from psx.sfle.model import LayoutInput,LayoutNode,WritingDirection
    from fuzz_dimension_helpers import _typed
    generation=642
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;flex-direction:row;"
        f"width:{root_width}px;height:auto;align-items:flex-start;"
        f"box-sizing:content-box'>"
        f"<div id='wrapper' style='display:flex;flex-direction:column;"
        f"width:{share}%;height:auto;flex:0 0 {share}%;min-width:0;"
        f"align-items:flex-start;box-sizing:content-box'>"
        "<div id='text' style='width:100%;height:auto;flex:0 0 auto;"
        f"min-width:0;font:10px/20px monospace;white-space:normal;"
        f"box-sizing:content-box'>{content}</div></div></div></body></html>"
    )
    snapshot=LayoutInput(
        1,generation,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(None,False)),
        (
            LayoutNode("root",None,"Flex",_typed({
                "direction":"row","width":f"{root_width}px","height":"auto",
                "align_items":"flex-start",
            })),
            LayoutNode("wrapper","root","Flex",_typed({
                "direction":"column","width":f"{share}%","height":"auto",
                "flex_basis":f"{share}%","flex_grow":0,"flex_shrink":0,
                "min_width":"0px","align_items":"flex-start",
            })),
            LayoutNode("text","wrapper","Text",_typed({
                "width":"100%","height":"auto","flex_basis":"auto",
                "flex_grow":0,"flex_shrink":0,"min_width":"0px",
            })),
        ),(),
    )
    requests=[]
    def host_intrinsic(node_id,width):
        assert node_id=="text"
        observed_height=page.evaluate("""({id,width})=>{
            const e=document.getElementById(id);
            const old={width:e.style.width,height:e.style.height,flex:e.style.flex,
                       alignSelf:e.style.alignSelf};
            e.style.width=width+'px'; e.style.height='auto';
            e.style.flex='none'; e.style.alignSelf='flex-start';
            const actual=e.getBoundingClientRect().height;
            for(const [key,value] of Object.entries(old))e.style[key]=value;
            return actual;
        }""",{"id":node_id,"width":width})
        intrinsic=IntrinsicSizes(0,600,20,observed_height,width,observed_height)
        port=HeadlessMeasurementSource(((node_id,intrinsic),)).port()
        request=MeasurementRequest(
            node_id,LayoutConstraints(
                AvailableSize(width,True),AvailableSize(None,False),
            ),snapshot.generation,0,
        )
        measured=port.measure(request)
        assert measured.constraints==request.constraints
        requests.append((width,observed_height))
        return measured.intrinsic

    engine=PythonLayoutEngine()
    pure=engine.compute if backend=="python" else lambda s:rust_compute(rust_binary,s)
    provisional=(engine.compute_provisional if backend=="python"
                 else lambda s:rust_compute(rust_binary,s,provisional=True))
    result=compute_with_width_measurements(
        snapshot,pure,host_intrinsic,compute_provisional=provisional,
        initial_widths={"text":80},
    )
    assert requests,"No actual intrinsic measuring occurred"
    actual=page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el=>{
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    assert set(actual)=={"root","wrapper","text"}
    assert requests[-1][0]==pytest.approx(actual["text"]["width"],abs=0.01)
    for node_id,box in result.boxes:
        for axis in ("x","y","width","height"):
            prediction=getattr(box.border,axis)
            expected=actual[node_id][axis]
            assert abs(prediction-expected)<=0.01,(
                f"nested text pct {share}% root {root_width} {backend}"
                f" {node_id}.{axis}={prediction} browser={expected}"
            )
