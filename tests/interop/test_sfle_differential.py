"""Differential SFLE contract runner: identical v1 snapshot, Python and Rust.

No xfail/skip is permitted in CI: unsupported-but-required alpha cases fail.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "sfle"))
from test_acceptance_contract_regression import case_snapshot  # noqa: E402
from psx.sfle.engine import PythonLayoutEngine  # noqa: E402
from psx.sfle.errors import SFLEError  # noqa: E402
from psx.sfle.lengths import Length  # noqa: E402

CORPUS = json.loads((ROOT / "tests/sfle/fixtures/f2_alpha_acceptance.json").read_text())
RUST_ROOT = ROOT / "rust/sfle-core"


def _axis(value):
    return {"value": value.value, "definite": value.definite}


def _constraints(value):
    return {"width": _axis(value.width), "height": _axis(value.height)}


def _snapshot_wire(snapshot):
    def style_value(value):
        return {"kind": value.kind.value, "value": value.value} if isinstance(value, Length) else value
    def metric(record):
        m=record.intrinsic
        return {
            "node_id":record.node_id,
            "constraints":_constraints(record.constraints),
            "revision":record.revision,
            "intrinsic":{
                "min_content_width":m.min_content_width,
                "max_content_width":m.max_content_width,
                "min_content_height":m.min_content_height,
                "max_content_height":m.max_content_height,
                "preferred_width":m.preferred_width,
                "preferred_height":m.preferred_height,
                "baseline":m.baseline,
            },
        }
    return {
        "schema_version":snapshot.schema_version,
        "generation":snapshot.generation,
        "direction":snapshot.direction.value,
        "constraints":_constraints(snapshot.constraints),
        "nodes":[{
            "node_id":n.node_id,"parent_id":n.parent_id,
            "component":n.component,"style":{k:style_value(v) for k,v in n.style},
        } for n in snapshot.nodes],
        "measurements":[metric(m) for m in snapshot.measurements],
    }


@pytest.fixture(scope="session")
def rust_binary():
    subprocess.run(
        ["cargo","build","--quiet","--bin","sfle_f2_fixture_runner"],
        cwd=RUST_ROOT,check=True,timeout=240,
    )
    filename="sfle_f2_fixture_runner.exe" if sys.platform=="win32" else "sfle_f2_fixture_runner"
    result=RUST_ROOT / "target/debug" / filename
    assert result.exists(), "Rust CLI build did not produce binary"
    return result


def _python_compute(snapshot):
    try:
        return {"ok":True,"result":PythonLayoutEngine().compute(snapshot)}
    except SFLEError as exc:
        return {"ok":False,"error":{"code":exc.code.value,"message":str(exc),"node_id":exc.node_id}}


def _rust_compute(binary,snapshot):
    run=subprocess.run(
        [str(binary)],input=json.dumps(_snapshot_wire(snapshot)),
        text=True,capture_output=True,check=True,timeout=30,
    )
    return json.loads(run.stdout)


def _rects(result):
    if isinstance(result,dict):
        return {box["node_id"]:box for box in result["boxes"]}
    def rect(value):
        return {axis:getattr(value,axis) for axis in ("x","y","width","height")}
    return {
        node_id:{"node_id":node_id,"content":rect(box.content),
                 "border":rect(box.border),"padding":rect(box.padding),
                 "margin":rect(box.margin)}
        for node_id,box in result.boxes
    }


@pytest.mark.parametrize("case",CORPUS["cases"],ids=lambda case:case["id"])
def test_shared_normalized_input_rust_python_and_expected_geometry(case,rust_binary):
    snapshot=case_snapshot(case["id"])
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    if case["expected"].get("diagnostic") == "SFLE_UNSUPPORTED_FEATURE":
        for side in (py,rs):
            assert side["ok"] is False
            assert side["error"]["code"]==case["expected"]["diagnostic"]
            assert side["error"]["node_id"]==case["expected"]["node"]
            assert all(token.lower() in side["error"]["message"].lower()
                       for token in case["expected"]["cycle_kind"].split())
        return
    assert py["ok"],f"{case['id']} Python failure: {py.get('error')}"
    assert rs["ok"],f"{case['id']} Rust failure: {rs.get('error')}"
    python_result=py["result"]
    rust_result=rs["result"]
    assert python_result.generation==rust_result["generation"]==snapshot.generation
    pboxes=_rects(python_result)
    rboxes=_rects(rust_result)
    ordered_python=[node_id for node_id,_ in python_result.boxes]
    ordered_rust=[box["node_id"] for box in rust_result["boxes"]]
    assert ordered_python==ordered_rust==[n.node_id for n in snapshot.nodes]
    for node_id in ordered_python:
        for box_type in ("content","border","padding","margin"):
            for axis in ("x","y","width","height"):
                a=pboxes[node_id][box_type][axis]
                b=rboxes[node_id][box_type][axis]
                assert a*64.0 == math.trunc(a*64.0) and b*64.0 == math.trunc(b*64.0), (
                    f"{case['id']} {node_id}.{box_type}.{axis} not on LayoutUnit grid: Python={a}, Rust={b}"
                )
                assert a == b,(
                    f"{case['id']} {node_id}.{box_type}.{axis}: Python={a}, Rust={b}"
                )
    for key,expected in case["expected"].items():
        if isinstance(expected,bool) or not isinstance(expected,(int,float)):
            continue
        if key in ("intrinsic_gap","used_gap","generation","commits_from_stale_generation",
                   "max_iterations","commits_after_cycle"):
            continue
        if "." not in key: continue
        node_id,axis=key.split(".",1)
        if axis=="padding_top":
            value=pboxes[node_id]["content"]["y"]-pboxes[node_id]["padding"]["y"]
        elif axis in ("x","y","width","height"):
            value=pboxes[node_id]["content"][axis]
        else:
            raise AssertionError(f"No numeric acceptance mapping for {case['id']} {key}")
        assert math.isclose(value,expected,rel_tol=0,abs_tol=CORPUS["tolerance_px"]),(
            f"{case['id']} expected {key}={expected}, computed={value}"
        )


def test_canonical_box_lengths_match_rust_and_python_geometry(rust_binary):
    """Both engines consume exactly the same canonical item style payload."""
    from psx import Flex
    from psx.core.layout_tree import normalize_flex_tree
    from psx.sfle.model import AvailableSize, LayoutConstraints
    from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot

    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(Flex(
            Flex(height="10px", flex_basis="40px", flex_shrink=0,
                 layout_width="40px", layout_padding_left="6px",
                 layout_border_right="2px", layout_margin_top="-3px"),
            width="120px", height="40px",
        )),
        LayoutConstraints(AvailableSize(160, True), AvailableSize(90, True)),
        generation=19,
    )
    canonical = prepared.canonical_snapshot()
    original = prepared.snapshot
    assert dict(canonical.nodes[1].style)["layout_width"] == Length.px(40)
    assert PythonLayoutEngine().compute(canonical).boxes == PythonLayoutEngine().compute(original).boxes
    py = _python_compute(canonical)
    rust = _rust_compute(rust_binary, canonical)
    assert py["ok"], py.get("error")
    assert rust["ok"], rust.get("error")
    for node_id in (node.node_id for node in canonical.nodes):
        for box in ("content", "padding", "border", "margin"):
            for axis in ("x", "y", "width", "height"):
                value_python = _rects(py["result"])[node_id][box][axis]
                value_rust = _rects(rust["result"])[node_id][box][axis]
                assert abs(value_python - value_rust) <= 0.01, (
                    f"{node_id}.{box}.{axis}: Python={value_python}, Rust={value_rust}"
                )


@pytest.mark.parametrize("root_display", ("block", "inline"))
def test_semantic_flow_snapshot_rust_python_geometry_parity(rust_binary, root_display):
    """Require actual Rust/Python parity on nested semantic flow snapshots."""
    from psx.sfle.model import (
        AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
        LayoutNode, MeasuredBox, WritingDirection,
    )

    constraints = LayoutConstraints(
        AvailableSize(100, True), AvailableSize(140, True),
    )
    if root_display == "block":
        nodes = (
            LayoutNode("root", None, "div", (("display", "block"),)),
            LayoutNode("heading", "root", "h1", (("display", "block"),)),
            LayoutNode("heading-text", "heading", "Text", ()),
            LayoutNode("paragraph", "root", "p", (("display", "block"),)),
            LayoutNode("span", "paragraph", "span", (("display", "inline"),)),
            LayoutNode("a", "span", "Text", ()),
            LayoutNode("b", "span", "Text", ()),
            LayoutNode("button", "root", "Button", ()),
        )
    else:
        nodes = (
            LayoutNode("root", None, "div", (("display", "inline"),)),
            LayoutNode("span", "root", "span", (("display", "inline"),)),
            LayoutNode("a", "span", "Text", ()),
            LayoutNode("b", "span", "Text", ()),
            LayoutNode("button", "root", "Button", ()),
        )
    measurements = tuple(MeasuredBox(
        node.node_id,
        IntrinsicSizes(
            70.3 if node.node_id in ("a", "heading-text") else 45.4,
            70.3 if node.node_id in ("a", "heading-text") else 45.4,
            14.7, 14.7,
            70.3 if node.node_id in ("a", "heading-text") else 45.4,
            14.7,
            baseline=10.2,
        ),
        constraints, 1,
    ) for node in nodes if node.component in ("Text", "Button"))
    snapshot = LayoutInput(
        1, 19, WritingDirection.LTR, constraints, nodes, measurements,
    )
    py = _python_compute(snapshot)
    rs = _rust_compute(rust_binary, snapshot)
    assert py["ok"], py.get("error")
    assert rs["ok"], rs.get("error")
    py_rects, rs_rects = _rects(py["result"]), _rects(rs["result"])
    assert tuple(py_rects) == tuple(rs_rects) == tuple(node.node_id for node in nodes)
    for node_id in py_rects:
        for kind in ("border", "content", "padding", "margin"):
            for axis in ("x", "y", "width", "height"):
                actual = py_rects[node_id][kind][axis]
                expected = rs_rects[node_id][kind][axis]
                assert actual == expected, (
                    root_display, node_id, kind, axis, actual, expected,
                )


def test_semantic_flow_missing_native_measurement_fails_both_engines(rust_binary):
    from psx.sfle.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
        WritingDirection,
    )

    constraints = LayoutConstraints(
        AvailableSize(100, True), AvailableSize(80, True),
    )
    snapshot = LayoutInput(
        1, 23, WritingDirection.LTR, constraints,
        (
            LayoutNode("root", None, "div", (("display", "block"),)),
            LayoutNode("text", "root", "Text", ()),
        ),
        (),
    )
    py = _python_compute(snapshot)
    rs = _rust_compute(rust_binary, snapshot)
    assert not py["ok"] and not rs["ok"]
    assert py["error"]["code"] == rs["error"]["code"] == "SFLE_UNSUPPORTED_MEASUREMENT"
    assert py["error"]["node_id"] == rs["error"]["node_id"] == "text"


@pytest.mark.parametrize(("tag", "display"), [
    ("form", "block"), ("label", "inline"),
    ("ul", "block"), ("li", "block"),
])
def test_semantic_form_label_and_list_snapshots_match_rust_python(
    rust_binary, tag, display,
):
    from psx.sfle.model import (
        AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
        LayoutNode, MeasuredBox, WritingDirection,
    )
    viewport = LayoutConstraints(
        AvailableSize(120, True), AvailableSize(80, True),
    )
    nodes = (
        LayoutNode("root", None, tag, (("display", display),)),
        LayoutNode("text", "root", "Text", ()),
    )
    measured = (
        MeasuredBox(
            "text", IntrinsicSizes(45, 45, 16, 16, 45, 16, baseline=12),
            viewport, 1,
        ),
    )
    snapshot = LayoutInput(
        1, 32, WritingDirection.LTR, viewport, nodes, measured,
    )
    py = _python_compute(snapshot)
    rust = _rust_compute(rust_binary, snapshot)
    assert py["ok"], py.get("error")
    assert rust["ok"], rust.get("error")
    assert _rects(py["result"]) == _rects(rust["result"])
    expected_width = 45 if display == "inline" else 120
    assert _rects(py["result"])["text"]["border"]["width"] == expected_width


@pytest.mark.parametrize("case", ("nested-edges", "min-over-max", "inline-edges"))
def test_css_flow_box_geometry_matches_rust_and_python(rust_binary, case):
    """Compare actual content, padding, border and margin on identical inputs."""
    from psx.sfle.model import (
        AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
        LayoutNode, MeasuredBox, WritingDirection,
    )

    def node(name, parent, component, **props):
        return LayoutNode(name, parent, component, tuple(sorted(props.items())))

    constraints = LayoutConstraints(AvailableSize(200, True), AvailableSize(120, True))
    root = node("root", None, "div", display="block")
    if case == "nested-edges":
        middle = node(
            "middle", "root", "div", display="block",
            layout_width=Length.px(150),
            layout_margin_top=Length.px(3), layout_margin_left=Length.px(4),
            layout_margin_bottom=Length.px(3),
            layout_padding_top=Length.px(8), layout_padding_left=Length.percent(.1),
            layout_padding_right=Length.px(8), layout_padding_bottom=Length.px(8),
            layout_border_top=Length.px(2), layout_border_left=Length.px(2),
            layout_border_right=Length.px(2), layout_border_bottom=Length.px(2),
        )
        nodes = (root, middle, node("leaf", "middle", "Button", layout_width=Length.percent(.5)))
    elif case == "min-over-max":
        nodes = (root, node("leaf", "root", "Button",
            layout_width=Length.px(190), layout_min_width=Length.px(110),
            layout_max_width=Length.px(100), layout_height=Length.px(60),
            layout_max_height=Length.px(30)))
    else:
        nodes = (root, node("line", "root", "span", display="inline"),
                 node("leaf", "line", "Button", layout_width=Length.px(30),
                      layout_padding_left=Length.px(4),
                      layout_border_left=Length.px(2),
                      layout_margin_top=Length.px(3)))
    measurements = tuple(
        MeasuredBox(n.node_id, IntrinsicSizes(20, 20, 10, 10, 20, 10), constraints, 1)
        for n in nodes if n.component == "Button"
    )
    snapshot = LayoutInput(1, 52, WritingDirection.LTR, constraints, nodes, measurements)
    py, rs = _python_compute(snapshot), _rust_compute(rust_binary, snapshot)
    assert py["ok"], py.get("error")
    assert rs["ok"], rs.get("error")
    actual, expected = _rects(py["result"]), _rects(rs["result"])
    for item in actual:
        for box in ("content", "padding", "border", "margin"):
            for axis in ("x", "y", "width", "height"):
                assert actual[item][box][axis] == expected[item][box][axis], (
                    case, item, box, axis,
                    actual[item][box][axis], expected[item][box][axis],
                )


@pytest.mark.parametrize("scenario", ("auto-margin", "inline-owner-padding"))
def test_unimplemented_css_flow_cases_fail_closed_in_both_engines(rust_binary, scenario):
    from psx.sfle.lengths import LengthKind
    from psx.sfle.model import (
        AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
        LayoutNode, MeasuredBox, WritingDirection,
    )
    size = LayoutConstraints(AvailableSize(200, True), AvailableSize(100, True))
    root = LayoutNode("root", None, "div", (("display", "block"),))
    if scenario == "auto-margin":
        nodes = (root, LayoutNode("leaf", "root", "Button",
                                (("layout_margin_left", Length(LengthKind.AUTO)),)))
    else:
        nodes = (root,
                 LayoutNode("owner", "root", "span",
                            (("display", "inline"), ("layout_padding_left", Length.px(4)))),
                 LayoutNode("leaf", "owner", "Button", ()))
    measures = (
        MeasuredBox("leaf", IntrinsicSizes(20, 20, 10, 10, 20, 10), size, 1),
    )
    snapshot = LayoutInput(1, 1, WritingDirection.LTR, size, nodes, measures)
    python, rust = _python_compute(snapshot), _rust_compute(rust_binary, snapshot)
    assert python["ok"] is False, scenario
    assert rust["ok"] is False, scenario
    assert python["error"]["code"] == rust["error"]["code"] == "SFLE_UNSUPPORTED_FEATURE"
