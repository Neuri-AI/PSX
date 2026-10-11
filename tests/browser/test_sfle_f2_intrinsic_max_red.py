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



@pytest.mark.parametrize("index", range(8))
def test_intrinsic_row_auto_cross_height_respects_min_max_red(page, rust_binary, index):
    """B1 independent RED: auto cross height is bounded after sizing children."""
    width = 120 + index * 2
    leaf_width = 20 + index
    mode = index % 4
    leaf_height = (40 if mode == 0 else 12 if mode == 1 else 45 if mode == 2 else 30) + index
    minimum = (30 + index if mode == 1 else 35 + index if mode == 2 else None)
    maximum = (10 + index if mode == 2 else 20 + index if mode in (0, 3) else None)
    nested_props = {
        "direction": "row", "width": f"{width}px", "height": "auto",
        "flex_basis": f"{width}px", "flex_shrink": 0, "align_items": "flex-start",
    }
    if minimum is not None:
        nested_props["min_height"] = f"{minimum}px"
    if maximum is not None:
        nested_props["max_height"] = f"{maximum}px"
    nodes = (
        LayoutNode("root", None, "Flex", _typed({
            "direction": "row", "width": "300px", "height": "150px",
            "align_items": "flex-start",
        })),
        LayoutNode("nested", "root", "Flex", _typed(nested_props)),
        LayoutNode("leaf", "nested", "Box", _typed({
            "width": f"{leaf_width}px", "height": f"{leaf_height}px",
            "flex_basis": f"{leaf_width}px", "flex_shrink": 0,
        })),
    )
    snapshot = LayoutInput(
        1, 91 + index, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(300, True), AvailableSize(150, True)),
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
    bounds_css = (
        (f"min-height:{minimum}px;" if minimum is not None else "")
        + (f"max-height:{maximum}px;" if maximum is not None else "")
    )
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        "<div id='root' style='display:flex;align-items:flex-start;"
        "width:300px;height:150px;box-sizing:content-box'>"
        f"<div id='nested' style='display:flex;flex-direction:row;align-items:flex-start;"
        f"width:{width}px;height:auto;flex:0 0 {width}px;{bounds_css}"
        "box-sizing:content-box'>"
        f"<div id='leaf' style='width:{leaf_width}px;height:{leaf_height}px;"
        f"flex:0 0 {leaf_width}px;box-sizing:content-box'></div>"
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
            py_value = getattr(py[node_id].border, axis)
            rust_value = rs[node_id]["border"][axis]
            assert abs(py_value - expected[axis]) <= 0.01, (
                f"B1 cross[{index}] {node_id}.{axis}: Python={py_value}, Chromium={expected[axis]}"
            )
            assert abs(rust_value - expected[axis]) <= 0.01, (
                f"B1 cross[{index}] {node_id}.{axis}: Rust={rust_value}, Chromium={expected[axis]}"
            )



@pytest.mark.parametrize("index", range(8))
def test_definite_row_percentage_min_width_and_conflicting_max_red(page, rust_binary, index):
    """B1 RED: definite parent percentage minimum is CSS-supported; min wins over max."""
    root_width = 240 + 7 * index
    maximum = 60 if index >= 4 else None
    first_props = {
        "width": "40px", "height": "20px", "flex_basis": "40px",
        "flex_grow": 0, "flex_shrink": 0, "min_width": "50%",
    }
    if maximum is not None:
        first_props["max_width"] = f"{maximum}px"
    nodes = (
        LayoutNode("root", None, "Flex", _typed({
            "direction": "row", "width": f"{root_width}px", "height": "100px",
            "align_items": "flex-start",
        })),
        LayoutNode("first", "root", "Box", _typed(first_props)),
        LayoutNode("other", "root", "Box", _typed({
            "width": "40px", "height": "20px", "flex_basis": "40px",
            "flex_grow": 0, "flex_shrink": 0,
        })),
    )
    snapshot = LayoutInput(
        1, 111 + index, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width, True), AvailableSize(100, True)),
        nodes, (),
    )
    py = dict(PythonLayoutEngine().compute(snapshot).boxes)
    process = subprocess.run(
        [str(rust_binary)], input=serialize_snapshot(snapshot),
        text=True, capture_output=True, check=True, timeout=30,
    )
    native = json.loads(process.stdout)
    assert native["ok"], f"Rust rejected valid percentage minimum index={index}: {native.get('error')}"
    rs = {box["node_id"]: box for box in native["result"]["boxes"]}
    max_css = f"max-width:{maximum}px;" if maximum is not None else ""
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_width}px;height:100px;"
        "align-items:flex-start;box-sizing:content-box'>"
        f"<div id='first' style='width:40px;height:20px;flex:0 0 40px;"
        f"min-width:50%;{max_css}box-sizing:content-box'></div>"
        "<div id='other' style='width:40px;height:20px;flex:0 0 40px;"
        "box-sizing:content-box'></div>"
        "</div></body></html>"
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
            pv = getattr(py[node_id].border, axis)
            rv = rs[node_id]["border"][axis]
            assert abs(pv - expected[axis]) <= 0.01, (
                f"B1 percent-min[{index}] {node_id}.{axis}: Python={pv}, Chromium={expected[axis]}"
            )
            assert abs(rv - expected[axis]) <= 0.01, (
                f"B1 percent-min[{index}] {node_id}.{axis}: Rust={rv}, Chromium={expected[axis]}"
            )



@pytest.mark.parametrize("index", range(8))
def test_cyclic_percentage_intrinsic_padding_zero_then_used_width_red(page, rust_binary, index):
    """B1 RED: cyclic percent inline padding contributes zero intrinsically,
    but resolves against the resulting auto parent's used inline width.
    """
    root_width = 300 + 7 * index
    leaf_width = 40 + index
    percent = 10 + 5 * index
    nodes = (
        LayoutNode("root", None, "Flex", _typed({
            "direction": "row", "width": f"{root_width}px",
            "height": "100px", "align_items": "flex-start",
        })),
        LayoutNode("nested", "root", "Flex", _typed({
            "direction": "row", "width": "auto", "height": "auto",
            "flex_basis": "auto", "flex_shrink": 0,
            "min_width": "0px", "align_items": "flex-start",
        })),
        LayoutNode("leaf", "nested", "Box", _typed({
            "width": f"{leaf_width}px", "height": "20px",
            "flex_basis": f"{leaf_width}px", "flex_shrink": 0,
            "layout_padding_left": f"{percent}%",
        })),
    )
    snapshot = LayoutInput(
        1, 131 + index, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width, True), AvailableSize(100, True)),
        nodes, (),
    )
    py = dict(PythonLayoutEngine().compute(snapshot).boxes)
    process = subprocess.run(
        [str(rust_binary)], input=serialize_snapshot(snapshot),
        text=True, capture_output=True, check=True, timeout=30,
    )
    native = json.loads(process.stdout)
    assert native["ok"], f"Rust rejected cyclic percentage contribution index={index}: {native.get('error')}"
    rs = {box["node_id"]: box for box in native["result"]["boxes"]}
    page.set_content(
        "<!doctype html><html><body style='margin:0'>"
        f"<div id='root' style='display:flex;width:{root_width}px;height:100px;"
        "align-items:flex-start;box-sizing:content-box'>"
        "<div id='nested' style='display:flex;flex-direction:row;width:auto;"
        "height:auto;flex:0 0 auto;min-width:0;align-items:flex-start;"
        "box-sizing:content-box'>"
        f"<div id='leaf' style='width:{leaf_width}px;height:20px;"
        f"flex:0 0 {leaf_width}px;padding-left:{percent}%;"
        "box-sizing:content-box'></div>"
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
            pv = getattr(py[node_id].border, axis)
            rv = rs[node_id]["border"][axis]
            assert abs(pv - expected[axis]) <= 0.01, (
                f"B1 cyclic-padding[{index}] {node_id}.{axis}: Python={pv}, Chromium={expected[axis]}"
            )
            assert abs(rv - expected[axis]) <= 0.01, (
                f"B1 cyclic-padding[{index}] {node_id}.{axis}: Rust={rv}, Chromium={expected[axis]}"
            )
