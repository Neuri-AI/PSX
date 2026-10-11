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

from test_sfle_f2_differential import rust_binary  # noqa: E402
from test_f2_acceptance_contract_red import case_snapshot  # noqa: E402
from test_sfle_f2_live_text_chromium import html_for, DATA  # noqa: E402
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
