"""RED fixture registry: every out-of-sample discrepancy remains a named oracle.

Fixtures are one file per new mismatch, committed independently BEFORE a fix.
No failure may disappear by removing or changing the holdout generator.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "interop"))
from test_sfle_f2_differential import rust_binary  # noqa: E402
from test_sfle_f2_holdout_red import _snapshot, _dom  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.native_wire import serialize_snapshot
import subprocess

DIR = ROOT / "tests/sfle/fixtures/holdout_red"
FIXTURES = sorted(DIR.glob("*.json"))
EXPECTED_REDS = 19


def test_every_discovered_holdout_divergence_has_an_individual_fixture():
    assert len(FIXTURES) == EXPECTED_REDS, (
        f"Discovered {EXPECTED_REDS} new mismatches; {len(FIXTURES)} "
        "individually named fixtures present. Missing REDs cannot be waived."
    )


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as p:
        engine = p.chromium.launch(headless=True)
        try:
            assert engine.version == reference_version()
            yield engine.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=1)
        finally:
            engine.close()


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_each_holdout_red_matches_independent_chromium(path, browser, rust_binary):
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["type"] == "geometry" and fixture["errors"]
    spec = fixture["input"]
    snapshot = _snapshot(spec["width"], spec["gap"], spec["items"])
    py = dict(PythonLayoutEngine().compute(snapshot).boxes)
    result = subprocess.run([str(rust_binary)], input=serialize_snapshot(snapshot),
                            text=True, capture_output=True, check=True, timeout=30)
    rs = json.loads(result.stdout)
    assert rs["ok"], f"Rust rejected established Chromium RED fixture {path.name}"
    boxes_rs = {box["node_id"]: box for box in rs["result"]["boxes"]}
    assert list(py) == list(boxes_rs) == [node.node_id for node in snapshot.nodes]
    browser.set_content(_dom(spec["width"], spec["gap"], spec["items"]))
    observed = browser.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el => {
            const r = el.getBoundingClientRect();
            return [el.id, {x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    # Full four-rectangle bit-for-bit parity for all nodes, not just RED axes.
    for node_id, py_box in py.items():
        rs_box = boxes_rs[node_id]
        for rect_name in ("content", "padding", "border", "margin"):
            p_rect = getattr(py_box, rect_name)
            for axis in ("x", "y", "width", "height"):
                p_raw = getattr(p_rect, axis) * 64
                r_raw = rs_box[rect_name][axis] * 64
                assert p_raw == r_raw and p_raw == int(p_raw), (
                    f"{path.name} {node_id}.{rect_name}.{axis}: "
                    f"Python raw={p_raw} Rust raw={r_raw}"
                )
    for error in fixture["errors"]:
        node_id, axis, expected = error["node"], error["axis"], error["chromium"]
        assert abs(observed[node_id][axis] - expected) < 0.000001, (
            f"Chromium changed its fixture oracle: {path.name} {node_id}.{axis}"
        )
        a, b = getattr(py[node_id].border, axis), boxes_rs[node_id]["border"][axis]
        assert abs(a - expected) <= 0.01 and abs(b - expected) <= 0.01, (
            f"{path.name} {node_id}.{axis}: Chromium {expected} Python {a} Rust {b}"
        )
