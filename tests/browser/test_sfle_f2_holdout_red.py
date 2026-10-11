"""Out-of-sample SFLE/Chromium holdout; these seeds were never used to tune rounding.

Every case runs real Python and Rust v1 snapshot compute, then real Chromium
where supported. Classification requires a *listed* unsupported class;
rejecting additional cases never improves a holdout pass rate.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "interop"))
from test_sfle_f2_differential import rust_binary  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import SFLEError, DiagnosticCode
from psx.sfle.lengths import parse_length
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection
from psx.sfle.native_wire import serialize_snapshot

SEEDS = (0x6A112026, 0x6A222026, 0x6A332026, 0x6A442026, 0x6A552026)
COUNT = 200
TOLERANCE = 0.01
# Fixed registry, not a regex accepting every UNSUPPORTED_FEATURE.
REJECTION_CLASSES = {
    "N01": "Unlisted indefinite inline percentage dependency cycle",
}
OUTPUT = Path(os.environ.get("SFLE_HOLDOUT_RESULTS", "/tmp/sfle-holdout-results"))


def generate(seed: int):
    rng = random.Random(seed)
    for index in range(COUNT):
        width = rng.choice((96, 120, 160, 200, 240, 320))
        gap = rng.choice(("0px", "4px", "10%", "5%", "8px"))
        count = rng.randint(1, 5)
        items = []
        for _ in range(count):
            items.append({
                "basis": rng.choice(("20px", "30px", "25%", "auto", "40%")),
                "width": rng.choice(("20px", "30px", "25%", "auto")),
                "grow": rng.choice((0, 1, 2)),
                "shrink": rng.choice((0, 1)),
                "pad": rng.choice(("0px", "4px", "10%", "5%")),
            })
        # A deliberately occasional, explicitly listed indefinite reference.
        if index % 17 == 0:
            width = None
            items[0]["width"] = "25%"
        yield index, width, gap, items


def _normalize(style):
    return tuple(
        (key, parse_length(value) if isinstance(value, str) and
         (value.endswith("px") or value.endswith("%") or value == "auto") else value)
        for key, value in style.items()
    )


def _snapshot(width, gap, items):
    root_width = "auto" if width is None else f"{width}px"
    nodes = [LayoutNode("root", None, "Flex", _normalize({
        "direction": "row", "width": root_width, "height": "60px",
        "column_gap": gap, "align_items": "flex-start",
    }))]
    for idx, item in enumerate(items):
        nodes.append(LayoutNode(f"n{idx}", "root", "Box", _normalize({
            "width": item["width"], "height": "20px",
            "flex_basis": item["basis"], "flex_grow": item["grow"],
            "flex_shrink": item["shrink"], "min_width": "0px",
            "layout_padding_top": item["pad"],
        })))
    return LayoutInput(
        1, 17, WritingDirection.LTR,
        LayoutConstraints(AvailableSize(width, width is not None), AvailableSize(60, True)),
        tuple(nodes), (),
    )


def _dom(width, gap, items):
    elements = [
        f'<div id="n{i}" style="height:20px;width:{item["width"]};'
        f'flex:{item["grow"]} {item["shrink"]} {item["basis"]};'
        f'min-width:0;padding-top:{item["pad"]};box-sizing:content-box"></div>'
        for i, item in enumerate(items)
    ]
    return (
        '<!doctype html><html><body style="margin:0">'
        f'<div id="root" style="display:flex;width:{width}px;height:60px;'
        f'column-gap:{gap};align-items:flex-start">' +
        "".join(elements) + '</div></body></html>'
    )


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version()
            yield browser.new_page(viewport={"width": 800, "height": 600}, device_scale_factor=1)
        finally:
            browser.close()


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"holdout-{s:08x}")
def test_unseen_seed_200_cases(seed, page, rust_binary):
    counts = Counter()
    failures = []
    rejected_by_class = Counter()
    for index, width, gap, items in generate(seed):
        snapshot = _snapshot(width, gap, items)
        try:
            py = {"ok": True, "result": PythonLayoutEngine().compute(snapshot)}
        except SFLEError as error:
            py = {"ok": False, "code": error.code.value,
                  "node": error.node_id, "message": str(error)}
        run = subprocess.run(
            [str(rust_binary)], input=serialize_snapshot(snapshot),
            capture_output=True, text=True, check=True, timeout=30,
        )
        rs = json.loads(run.stdout)
        details = {"seed": f"0x{seed:08x}", "index": index, "input": {
            "width": width, "gap": gap, "items": items,
        }}
        if not py["ok"] or not rs.get("ok"):
            matches = [
                name for name, phrase in REJECTION_CLASSES.items()
                if not py["ok"] and not rs.get("ok")
                and py["code"] == rs["error"]["code"] == DiagnosticCode.UNSUPPORTED_FEATURE.value
                and py["node"] == rs["error"]["node_id"]
                and phrase.lower() in py["message"].lower()
                and phrase.lower() in rs["error"]["message"].lower()
            ]
            if len(matches) == 1:
                counts["rejected"] += 1
                rejected_by_class[matches[0]] += 1
            else:
                counts["unlisted_rejection"] += 1
                failures.append({**details, "type": "unlisted_rejection", "python": str(py), "rust": rs})
            continue

        page.set_content(_dom(width, gap, items))
        observed = page.evaluate("""() => Object.fromEntries(
            [...document.querySelectorAll('[id]')].map(el => {
                const r = el.getBoundingClientRect();
                return [el.id, {x:r.x, y:r.y, width:r.width, height:r.height}];
            })
        )""")
        actual_py = dict(py["result"].boxes)
        actual_rs = {box["node_id"]: box for box in rs["result"]["boxes"]}
        expected_ids = [node.node_id for node in snapshot.nodes]
        if list(actual_py) != expected_ids or list(actual_rs) != expected_ids:
            counts["divergent"] += 1
            failures.append({**details, "type": "identity/order",
                             "python_ids": list(actual_py), "rust_ids": list(actual_rs)})
            continue
        errors = []
        for node_id in expected_ids:
            for kind in ("x", "y", "width", "height"):
                chrome = observed[node_id][kind]
                a = getattr(actual_py[node_id].border, kind)
                b = actual_rs[node_id]["border"][kind]
                if abs(a - chrome) > TOLERANCE or abs(b - chrome) > TOLERANCE or abs(a - b) > TOLERANCE:
                    errors.append({"node": node_id, "axis": kind, "chromium": chrome,
                                   "python": a, "rust": b})
        if errors:
            counts["divergent"] += 1
            failures.append({**details, "type": "geometry", "errors": errors})
        else:
            counts["matched"] += 1

    results = {
        "seed": f"0x{seed:08x}", "scenarios": COUNT,
        "dimensions": ["ltr", "row", "nowrap", "px/percent/auto basis",
                       "grow/shrink", "percentage cross padding", "gap"],
        "matched": counts["matched"],
        "rejected": counts["rejected"],
        "rejected_classes": dict(rejected_by_class),
        "divergent": counts["divergent"],
        "unlisted_rejection": counts["unlisted_rejection"],
        "failures": failures,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"seed-{seed:08x}.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print("SFLE HOLDOUT " + json.dumps({k: v for k, v in results.items() if k != "failures"}), flush=True)
    for failure in failures:
        print("SFLE_RED_FIXTURE " + json.dumps(failure, separators=(",", ":")), flush=True)
    assert sum(counts.values()) == COUNT
    assert not failures, (
        f"Seed 0x{seed:08x} has {len(failures)} new RED cases. "
        f"First: {json.dumps(failures[:3])}. Full results in seed-{seed:08x}.json"
    )
