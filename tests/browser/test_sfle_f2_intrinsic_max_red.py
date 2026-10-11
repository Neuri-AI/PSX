"""RED B1: recursive intrinsic auto width must honor descendant max-width.

Eight independent Chromium rectangles exercise row -> auto column -> fixed
leaf with a cross-axis max-width clamp. Both pure engines are mandatory.
"""
import json
import subprocess

import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from psx.sfle.native_wire import serialize_snapshot
from f2_fuzz_dimension_helpers import _typed, rust_binary


@pytest.fixture(scope="module")
def page():
    """Pinned real Chromium, not the local browser or a simulated DOM."""
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version()
            yield browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=1)
        finally:
            browser.close()


@pytest.mark.parametrize("index", range(8))
def test_intrinsic_column_auto_width_honors_descendant_max_width_red(page, rust_binary, index):
    root_width = 230 + index * 7
    raw_width = 50 + index
    capped_width = 25 + index
    other_width = 20 + index
    first_height, other_height = 10 + index, 15 + index
    nodes = (
        LayoutNode("root", None, "Flex", _typed({
            "direction": "row", "width": f"{root_width}px",
            "height": "80px", "align_items": "flex-start",
        })),
        LayoutNode("column", "root", "Flex", _typed({
            "direction": "column", "width": "auto", "height": "auto",
            "flex_basis": "auto", "flex_shrink": 0, "min_width": "0px",
            "row_gap": "4px",
        })),
        LayoutNode("first", "column", "Box", _typed({
            "width": f"{raw_width}px", "max_width": f"{capped_width}px",
            "height": f"{first_height}px", "flex_basis": f"{first_height}px",
            "flex_shrink": 0,
        })),
        LayoutNode("other", "column", "Box", _typed({
            "width": f"{other_width}px", "height": f"{other_height}px",
            "flex_basis": f"{other_height}px", "flex_shrink": 0,
        })),
    )
    snapshot = LayoutInput(
        1, 71 + index, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width, True), AvailableSize(80, True)),
        nodes, (),
    )
    py = dict(PythonLayoutEngine().compute(snapshot).boxes)
    process = subprocess.run(
        [str(rust_binary)], input=serialize_snapshot(snapshot),
        text=True, capture_output=True, check=True, timeout=30,
    )
    native = json.loads(process.stdout)
    assert native["ok"], f"Rust rejected index={index}: {native.get('error')}"
    rs = {box["node_id"]: box for box in native["result"]["boxes"]}

    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;flex-direction:row;align-items:flex-start;"
        f"width:{root_width}px;height:80px;box-sizing:content-box'>"
        "<div id='column' style='display:flex;flex-direction:column;"
        "flex:0 0 auto;width:auto;height:auto;gap:4px;min-width:0;box-sizing:content-box'>"
        f"<div id='first' style='width:{raw_width}px;max-width:{capped_width}px;"
        f"height:{first_height}px;flex:0 0 {first_height}px;box-sizing:content-box'></div>"
        f"<div id='other' style='width:{other_width}px;height:{other_height}px;"
        f"flex:0 0 {other_height}px;box-sizing:content-box'></div>"
        "</div></div></body></html>"
    )
    browser = page.evaluate("""() => Object.fromEntries(
      [...document.querySelectorAll('[id]')].map(el => {
        const r = el.getBoundingClientRect();
        return [el.id, {x:r.x, y:r.y, width:r.width, height:r.height}];
      })
    )""")
    assert set(py) == set(rs) == set(browser)
    for node_id, expected in browser.items():
        for axis in ("x", "y", "width", "height"):
            python_value = getattr(py[node_id].border, axis)
            rust_value = rs[node_id]["border"][axis]
            assert abs(python_value - expected[axis]) <= 0.01, (
                f"B1 max[{index}] {node_id}.{axis}: Python={python_value}, Chromium={expected[axis]}"
            )
            assert abs(rust_value - expected[axis]) <= 0.01, (
                f"B1 max[{index}] {node_id}.{axis}: Rust={rust_value}, Chromium={expected[axis]}"
            )
