"""RED integration acceptance gates: v1 immutable layout snapshots.

These intentionally exercise the complete LayoutEngine.compute boundary,
rather than declaring narrow helper behavior to be accepted CSS semantics.
"""
import pytest
import json
from pathlib import Path

_ACCEPTANCE = {case['id']: case['expected'] for case in json.loads((Path(__file__).parent / 'fixtures' / 'f2_alpha_acceptance.json').read_text())['cases']}

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.lengths import Length, LengthKind
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, MeasuredBox, WritingDirection,
)


def snapshot(spec, *, width=120, height=None, direction=WritingDirection.LTR):
    nodes = tuple(
        LayoutNode(node_id, parent, component, tuple(style.items()))
        for node_id, parent, component, style in spec
    )
    constraints = LayoutConstraints(
        AvailableSize(width, width is not None),
        AvailableSize(height, height is not None),
    )
    # Intrinsic input is fixed so differential inputs have exactly the same
    # measurements, independent of UI fonts or toolkit.
    intrinsic = IntrinsicSizes(20, 100, 20, 60, 100, 60)
    measurements = tuple(
        MeasuredBox(n.node_id, intrinsic, constraints, 0)
        for n in nodes
    )
    return LayoutInput(1, 17, direction, constraints, nodes, measurements)


def boxes(result):
    return {b.node_id: b for b in result.boxes}


def test_A02_auto_parent_and_auto_flex_basis_use_intrinsic_content():
    s = snapshot([
        ("root", None, "Flex", {"direction": "row", "layout_width": Length(LengthKind.AUTO)}),
        ("child", "root", "Text", {"flex_basis": Length(LengthKind.AUTO), "layout_width": Length(LengthKind.AUTO)}),
    ], width=None)
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.width == pytest.approx(_ACCEPTANCE["A02"]["root.width"], abs=0.01)
    assert boxes(result)["child"].content.width == pytest.approx(_ACCEPTANCE["A02"]["child.width"], abs=0.01)


def test_A03_indefinite_percentage_reference_preserved_then_css_resolved():
    s = snapshot([
        ("root", None, "Flex", {"direction": "column", "layout_height": Length(LengthKind.AUTO)}),
        ("inner", "root", "Flex", {"layout_height": Length.percent(0.5)}),
    ], height=None)
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A03"]["root.height"], abs=0.01)
    assert boxes(result)["inner"].content.height == pytest.approx(_ACCEPTANCE["A03"]["inner.height"], abs=0.01)


def test_A04_grow_remeasures_final_text_width_and_parent_height():
    s = snapshot([
        ("root", None, "Flex", {"direction": "row", "layout_width": Length.px(150), "layout_height": Length(LengthKind.AUTO)}),
        ("text", "root", "Text", {"flex_grow": 1, "flex_basis": Length(LengthKind.AUTO), "layout_height": Length(LengthKind.AUTO)}),
    ], width=150)
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["text"].content.width == pytest.approx(_ACCEPTANCE["A04"]["text.width"], abs=0.01)
    assert boxes(result)["text"].content.height == pytest.approx(_ACCEPTANCE["A04"]["text.height"], abs=0.01)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A04"]["root.height"], abs=0.01)


def test_A05_shrink_remeasures_both_items_at_35px():
    s = snapshot([
        ("root", None, "Flex", {"direction": "row", "layout_width": Length.px(70), "layout_height": Length(LengthKind.AUTO)}),
        ("a", "root", "Text", {"flex_basis": Length.px(50), "flex_shrink": 1, "layout_min_width": Length.px(0)}),
        ("b", "root", "Text", {"flex_basis": Length.px(50), "flex_shrink": 1, "layout_min_width": Length.px(0)}),
    ], width=70)
    result = PythonLayoutEngine().compute(s)
    for name in ("a", "b"):
        assert boxes(result)[name].content.width == pytest.approx(_ACCEPTANCE["A05"][f"{name}.width"], abs=0.01)
        assert boxes(result)[name].content.height == pytest.approx(_ACCEPTANCE["A05"][f"{name}.height"], abs=0.01)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A05"]["root.height"], abs=0.01)


def test_A06_generation_is_preserved_by_pure_layout_result():
    s = snapshot([("root", None, "Flex", {})], height=40)
    result = PythonLayoutEngine().compute(s)
    assert result.generation == _ACCEPTANCE["A06"]["generation"]


def test_A07_convergent_auto_layout_is_finite():
    s = snapshot([
        ("root", None, "Flex", {"layout_height": Length(LengthKind.AUTO)}),
        ("child", "root", "Text", {"layout_height": Length(LengthKind.AUTO)}),
    ], height=None)
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.height >= 0


@pytest.mark.parametrize("direction", [WritingDirection.LTR, WritingDirection.RTL])
def test_A09_directional_positioning_preserves_identity(direction):
    s = snapshot([
        ("root", None, "Flex", {"direction": "row", "layout_width": Length.px(120)}),
        ("a", "root", "Text", {"flex_basis": Length.px(20)}),
        ("b", "root", "Text", {"flex_basis": Length.px(30)}),
    ], height=60, direction=direction)
    result = PythonLayoutEngine().compute(s)
    assert tuple(b.node_id for b in result.boxes) == ("root", "a", "b")
    a, b = boxes(result)["a"], boxes(result)["b"]
    assert (a.border.x < b.border.x) == (direction is WritingDirection.LTR)


def test_A10_layout_output_contains_separate_error_channels():
    s = snapshot([("root", None, "Flex", {})], height=20)
    result = PythonLayoutEngine().compute(s)
    for channel in ("measurement_error", "engine_error", "geometry_commit_error"):
        assert hasattr(result, channel), f"missing normative report field {channel}"


def test_C99_unlisted_two_node_percent_cycle_fails_closed():
    s = snapshot([
        ("root", None, "Flex", {"layout_width": Length(LengthKind.AUTO), "layout_height": Length(LengthKind.AUTO)}),
        ("a", "root", "Flex", {"layout_width": Length.percent(0.5), "layout_height": Length.percent(0.5)}),
        ("b", "a", "Flex", {"layout_width": Length.percent(0.5), "layout_height": Length.percent(0.5)}),
    ], width=None, height=None)
    with pytest.raises(SFLEError) as exc:
        PythonLayoutEngine().compute(s)
    assert exc.value.code == DiagnosticCode.UNSUPPORTED_FEATURE
    assert exc.value.node_id == "a"
    assert "cycle" in str(exc.value).lower()
    assert "percentage" in str(exc.value).lower()
    assert "multi-node" in str(exc.value).lower()


def test_C99_supported_A01_is_not_diagnosed_as_unsupported():
    """An indiscriminate UNSUPPORTED_FEATURE placeholder must fail this gate."""
    from pathlib import Path
    import json
    case = next(c for c in json.loads((Path(__file__).parent / "fixtures" / "f2_alpha_acceptance.json").read_text())["cases"] if c["id"] == "A01")
    children = []
    for node in case["nodes"]:
        style = tuple((key, (Length(LengthKind.AUTO) if val == "auto" else Length.percent(float(val[:-1])/100) if isinstance(val,str) and val.endswith("%") else Length.px(float(val[:-2])) if isinstance(val,str) and val.endswith("px") else val)) for key,val in node["style"].items())
        children.append(LayoutNode(node["node_id"], node["parent_id"], node["component"], style))
    intrinsic = IntrinsicSizes(20,80,20,60,80,60)
    request = LayoutInput(1,17,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(120,True), AvailableSize(None,False)),
        tuple(children), tuple(MeasuredBox(n.node_id,intrinsic,
        LayoutConstraints(AvailableSize(80,True),AvailableSize(60,True)),0) for n in children if n.node_id=="text"))
    try:
        result = PythonLayoutEngine().compute(request)
    except SFLEError as exc:
        assert exc.code != DiagnosticCode.UNSUPPORTED_FEATURE, "A01 is supported by the approved alpha scope"
        raise
    assert dict(result.boxes)["root"].content.height == pytest.approx(case["expected"]["root.height"], abs=0.01)
