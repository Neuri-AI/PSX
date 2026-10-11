"""Independent Chromium oracle for expanded SFLE F2.2/F2.3 dimensions.

Each dimension has its own RED test module/commit; a rejected supported case is
FAIL, never a silent passed 'unsupported' count.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import random
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "interop"))
from test_sfle_f2_differential import rust_binary  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError
from psx.sfle.lengths import parse_length
from psx.sfle.model import LayoutInput, LayoutNode, LayoutConstraints, AvailableSize, WritingDirection
from psx.sfle.native_wire import serialize_snapshot

TOLERANCE = 0.01
DIMENSION_SEEDS = {
    "rtl": 0x7120A,
    "reverse": 0x7120B,
    "wrap_fixed": 0x7120C,
    "nested_columns": 0x7120D,
    "min_max": 0x7120E,
    "alignment": 0x7120F,
    "margins": 0x71210,
    "align_items": 0x71211,
    "align_self": 0x71212,
    "align_content": 0x71213,
}
ROWS_PER_DIMENSION = 8


def generate_dimension(
    dimension: str, *, seed: int | None = None, count: int = ROWS_PER_DIMENSION,
):
    # Existing 8-case dimensions retain their original fixture seeds exactly.
    # Independent multi-dimensional certification supplies fresh, disjoint
    # seeds and 200 cases without changing the original regression suite.
    rng = random.Random(DIMENSION_SEEDS[dimension] if seed is None else seed)
    for index in range(count):
        a = rng.choice((20, 24, 30))
        b = rng.choice((32, 40, 48))
        root_w = 120 + 8 * (index % 3)
        direction = "row"
        writing = "ltr"
        extra = {}
        items = [
            ("a", {"width": f"{a}px", "height": "20px", "flex_basis": f"{a}px", "flex_shrink": 0, "min_width": "0px"},
             f"width:{a}px;height:20px;flex:0 0 {a}px;min-width:0"),
            ("b", {"width": f"{b}px", "height": "24px", "flex_basis": f"{b}px", "flex_shrink": 0, "min_width": "0px"},
             f"width:{b}px;height:24px;flex:0 0 {b}px;min-width:0"),
        ]
        nested = False
        if dimension == "rtl":
            writing = "rtl"
        elif dimension == "reverse":
            direction = rng.choice(("row-reverse", "column-reverse"))
        elif dimension == "wrap_fixed":
            root_w = a + b - 8
            extra["wrap"] = "wrap"
        elif dimension == "nested_columns":
            nested = True
            root_w = 120
        elif dimension == "min_max":
            items[1][1]["max_width"] = f"{b-12}px"
            items[1] = (items[1][0], items[1][1], items[1][2] + f";max-width:{b-12}px")
        elif dimension == "alignment":
            extra["justify_content"] = "space-between"
        elif dimension == "margins":
            extra_margin = (index % 3 + 1) * 4
            items[0][1]["layout_margin_left"] = f"{extra_margin}px"
            items[0] = (items[0][0], items[0][1], items[0][2] + f";margin-left:{extra_margin}px")
        elif dimension == "align_items":
            extra["align_items"] = ("center", "flex-end", "flex-start", "stretch")[index % 4]
        elif dimension == "align_self":
            self_align = ("center", "flex-end", "flex-start", "stretch")[index % 4]
            items[0][1]["align_self"] = self_align
            items[0] = (items[0][0], items[0][1], items[0][2] + f";align-self:{self_align}")
        elif dimension == "align_content":
            root_w = a + b - 8
            extra["wrap"] = "wrap"
            extra["align_content"] = ("center", "flex-end", "flex-start", "space-between")[index % 4]
        root_style = {
            "direction": direction, "width": f"{root_w}px", "height": "90px",
            "align_items": "flex-start", "column_gap": "4px", "row_gap": "4px", **extra,
        }
        if direction in ("column", "column-reverse"):
            # CSS gap:4px sets both axes; SFLE needs row_gap for a column's
            # main axis. Without this, the test was comparing different CSS.
            root_style["row_gap"] = "4px"
        if nested:
            # Root row -> nested column with two fixed children; verify its own
            # final height and each descendant, not just the top-level row.
            items = [
                ("a", {"width": "30px", "height": "10px", "flex_basis": "30px", "flex_shrink": 0, "min_width": "0px"},
                 "width:30px;height:10px;flex:0 0 30px;min-width:0"),
                ("column", {"direction": "column", "width": "90px", "height": "auto", "flex_basis": "90px",
                            "flex_shrink": 0, "min_width": "0px"},
                 "display:flex;flex-direction:column;width:90px;height:auto;flex:0 0 90px;min-width:0"),
                ("text_a", {"width": "100%", "height": "20px", "flex_basis": "20px", "min_width": "0px"},
                 "width:100%;height:20px;flex:0 0 20px;min-width:0"),
                ("text_b", {"width": "100%", "height": "30px", "flex_basis": "30px", "min_width": "0px"},
                 "width:100%;height:30px;flex:0 0 30px;min-width:0"),
            ]
            root_style["height"] = "auto"
        yield index, root_w, writing, root_style, items, nested


def _typed(style):
    return tuple((k, parse_length(v) if isinstance(v, str) and (
        v == "auto" or v.endswith("px") or v.endswith("%")) else v) for k, v in style.items())


def run_dimension(page, rust_binary, dimension: str, case):
    index, width, writing, root_style, items, nested = case
    height = None if nested else 90
    root = LayoutNode("root", None, "Flex", _typed(root_style))
    nodes = [root]
    for node_id, style, _css in items:
        parent = "column" if nested and node_id.startswith("text_") else "root"
        component = "Flex" if node_id == "column" else "Box"
        nodes.append(LayoutNode(node_id, parent, component, _typed(style)))
    snapshot = LayoutInput(
        1, 17, WritingDirection(writing),
        LayoutConstraints(AvailableSize(width, True), AvailableSize(height, height is not None)),
        tuple(nodes), (),
    )
    try:
        python_result = PythonLayoutEngine().compute(snapshot)
    except SFLEError as e:
        pytest.fail(f"{dimension}[{index}]: supported CSS geometry rejected by Python: {e}", pytrace=False)
    actual_rust = subprocess.run(
        [str(rust_binary)], input=serialize_snapshot(snapshot),
        capture_output=True, text=True, check=True, timeout=30,
    )
    rust = json.loads(actual_rust.stdout)
    assert rust["ok"], f"{dimension}[{index}]: Rust refused supported CSS: {rust.get('error')}"
    assert [id_ for id_, _ in python_result.boxes] == [n.node_id for n in nodes]
    assert [b["node_id"] for b in rust["result"]["boxes"]] == [n.node_id for n in nodes]

    direction = root_style["direction"]
    css_root = f"display:flex;flex-direction:{direction};direction:{writing};width:{width}px;"
    css_root += f"height:{'auto' if nested else '90px'};gap:4px;align-items:{root_style['align_items']};"
    if "wrap" in root_style: css_root += "flex-wrap:wrap;"
    if "justify_content" in root_style: css_root += f"justify-content:{root_style['justify_content']};"
    if "align_content" in root_style: css_root += f"align-content:{root_style['align_content']};"
    dom_children = []
    if nested:
        column = items[1]
        inner = "".join(f'<div id="{id_}" style="{css};box-sizing:content-box"></div>'
                        for id_, _, css in items[2:])
        dom_children = [
            f'<div id="a" style="{items[0][2]};box-sizing:content-box"></div>',
            f'<div id="column" style="{column[2]};box-sizing:content-box">{inner}</div>',
        ]
    else:
        dom_children = [f'<div id="{id_}" style="{css};box-sizing:content-box"></div>'
                        for id_, _, css in items]
    page.set_content('<!doctype html><html><body style="margin:0">'
                     f'<div id="root" style="{css_root}">' + "".join(dom_children)
                     + '</div></body></html>')
    observed = page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('[id]')].map(el => {
            const r = el.getBoundingClientRect();
            return [el.id, {x:r.x,y:r.y,width:r.width,height:r.height}];
        })
    )""")
    actual_py = dict(python_result.boxes)
    actual_rs = {v["node_id"]: v for v in rust["result"]["boxes"]}
    assert set(observed) == set(actual_py) == set(actual_rs)
    for node_id in observed:
        for axis in ("x", "y", "width", "height"):
            expected = observed[node_id][axis]
            py = getattr(actual_py[node_id].border, axis)
            rs = actual_rs[node_id]["border"][axis]
            assert abs(py - expected) <= TOLERANCE and abs(rs - expected) <= TOLERANCE, (
                f"{dimension}[{index}] {node_id}.{axis}: Chromium={expected} "
                f"Python={py} Rust={rs}; complete tree={snapshot.nodes}"
            )
