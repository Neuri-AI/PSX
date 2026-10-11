"""RED first: Chromium nested_columns geometry, eight generated trees on Rust/Python."""
import pytest
from f2_fuzz_dimension_helpers import generate_dimension, run_dimension, rust_binary

DIMENSION = "nested_columns"

@pytest.mark.parametrize(
    "case", list(generate_dimension(DIMENSION)),
    ids=lambda case: f"nested_columns-case-{case[0]:02d}",
)
def test_chromium_dimension_nested_columns_red(case, page, rust_binary):
    run_dimension(page, rust_binary, DIMENSION, case)


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version()
            yield browser.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            browser.close()



@pytest.mark.parametrize("case_id", range(8))
def test_chromium_b1_orthogonal_intrinsic_padding_red(page, rust_binary, case_id):
    """RED B1: auto-height row must include a nested column's border/padding."""
    import json
    import subprocess

    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
    )
    from psx.sfle.native_wire import serialize_snapshot
    from f2_fuzz_dimension_helpers import _typed

    root_w = 200 + 8 * case_id
    a_h, b_h = 10 + 2 * case_id, 20 + case_id
    a_w, b_w = 30 + case_id, 50 + 2 * case_id
    top, bottom = 1 + case_id, 4 + case_id % 3
    left, right = 3, 5
    gap = 4 + case_id % 2
    nodes = (
        LayoutNode("root", None, "Flex", _typed({
            "direction": "row", "width": f"{root_w}px", "height": "auto",
            "align_items": "flex-start",
        })),
        LayoutNode("column", "root", "Flex", _typed({
            "direction": "column", "width": "auto", "height": "auto",
            "flex_basis": "auto", "flex_shrink": 0, "min_width": "0px",
            "row_gap": f"{gap}px",
            "layout_padding_top": f"{top}px",
            "layout_padding_bottom": f"{bottom}px",
            "layout_padding_left": f"{left}px",
            "layout_padding_right": f"{right}px",
        })),
        LayoutNode("a", "column", "Box", _typed({
            "width": f"{a_w}px", "height": f"{a_h}px",
            "flex_basis": f"{a_h}px", "flex_shrink": 0,
        })),
        LayoutNode("b", "column", "Box", _typed({
            "width": f"{b_w}px", "height": f"{b_h}px",
            "flex_basis": f"{b_h}px", "flex_shrink": 0,
        })),
    )
    snapshot = LayoutInput(
        1, 17 + case_id, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_w, True), AvailableSize(None, False)),
        nodes, (),
    )
    python = PythonLayoutEngine().compute(snapshot)
    process = subprocess.run(
        [str(rust_binary)], input=serialize_snapshot(snapshot),
        capture_output=True, text=True, check=True, timeout=30,
    )
    rust = json.loads(process.stdout)
    assert rust["ok"], f"Rust rejected B1 case {case_id}: {rust.get('error')}"
    column_css = (
        "display:flex;flex-direction:column;flex:0 0 auto;"
        f"width:auto;height:auto;gap:{gap}px;min-width:0;"
        f"padding:{top}px {right}px {bottom}px {left}px;box-sizing:content-box;"
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;flex-direction:row;align-items:flex-start;width:{root_w}px;height:auto;box-sizing:content-box'>"
        f"<div id='column' style='{column_css}'>"
        f"<div id='a' style='width:{a_w}px;height:{a_h}px;flex:0 0 {a_h}px;box-sizing:content-box'></div>"
        f"<div id='b' style='width:{b_w}px;height:{b_h}px;flex:0 0 {b_h}px;box-sizing:content-box'></div>"
        "</div></div></body></html>"
    )
    browser = page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el => {
            const r=el.getBoundingClientRect();
            return [el.id,{x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    py = dict(python.boxes)
    rs = {box["node_id"]: box for box in rust["result"]["boxes"]}
    assert set(browser) == set(py) == set(rs)
    for node_id, expected in browser.items():
        for axis in ("x", "y", "width", "height"):
            p = getattr(py[node_id].border, axis)
            r = rs[node_id]["border"][axis]
            assert abs(p - expected[axis]) <= 0.01 and abs(r - expected[axis]) <= 0.01, (
                f"B1[{case_id}] {node_id}.{axis} Chromium={expected[axis]} Python={p} Rust={r}"
            )
