"""Chromium reads the same source JSON as Python and Rust.

A01 browser control renders deterministic three-line text with fixed line
height; this does not yet compare the actual engine result (not certified).
"""
import json
from pathlib import Path
import pytest

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "sfle" / "fixtures" /
     "f2_alpha_acceptance.json").read_text(encoding="utf-8")
)["cases"]


@pytest.fixture(scope="module")
def chromium_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=1)
        finally:
            browser.close()


def test_a01_chromium_final_auto_parent_height(chromium_page):
    case = next(case for case in CASES if case["id"] == "A01")
    chromium_page.set_content("""
        <!doctype html><html><body style="margin:0">
          <div id="root" style="display:flex;width:120px;align-items:flex-start">
            <div style="flex:0 0 40px;height:10px;min-width:0"></div>
            <div id="column" style="display:flex;flex-direction:column;flex:0 0 80px;min-width:0">
              <div id="text" style="width:100%;height:auto;font:16px/20px monospace">
                <div style="height:20px">line 1</div>
                <div style="height:20px">line 2</div>
                <div style="height:20px">line 3</div>
              </div>
            </div>
          </div>
        </body></html>
    """)
    actual = chromium_page.evaluate("""() => Object.fromEntries(
        ['root','column','text'].map(id =>
          [id, document.getElementById(id).getBoundingClientRect().height])
    )""")
    for node_id in ("root", "column", "text"):
        assert actual[node_id] == pytest.approx(
            case["expected"][f"{node_id}.height"], abs=0.01
        )
