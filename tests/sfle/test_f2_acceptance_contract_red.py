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
from psx.sfle.lengths import Length, LengthKind, parse_length
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



def case_snapshot(case_id: str):
    """Build the same normalized immutable snapshot from the shared corpus."""
    case = next(case for case in json.loads(
        (Path(__file__).parent / "fixtures" / "f2_alpha_acceptance.json").read_text()
    )["cases"] if case["id"] == case_id)
    def normalize(value):
        if isinstance(value, str) and (
            value == "auto" or value.endswith("px") or value.endswith("%")
        ):
            return parse_length(value)
        return value
    nodes = tuple(LayoutNode(
        n["node_id"], n["parent_id"], n["component"],
        tuple((key, normalize(value)) for key, value in n["style"].items()),
    ) for n in case["nodes"])
    viewport = case["viewport"]
    def axis(value):
        return AvailableSize(value, value is not None)
    measurements = []
    for record in case["measurements"]:
        preferred_width = record.get("preferred_width", record["at_width"])
        intrinsic = IntrinsicSizes(
            20, preferred_width, 20, record["height"],
            preferred_width, record["height"],
        )
        measurements.append(MeasuredBox(
            record["node"], intrinsic,
            LayoutConstraints(axis(record["at_width"]), axis(record["height"])),
            0,
        ))
    return LayoutInput(
        1, 17, WritingDirection(case["writing_direction"]),
        LayoutConstraints(axis(viewport["width"]), axis(viewport["height"])),
        nodes, tuple(measurements),
    )


def boxes(result):
    return dict(result.boxes)


def test_A02_auto_parent_and_auto_flex_basis_use_intrinsic_content():
    s = case_snapshot("A02")
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.width == pytest.approx(_ACCEPTANCE["A02"]["root.width"], abs=0.01)
    assert boxes(result)["child"].content.width == pytest.approx(_ACCEPTANCE["A02"]["child.width"], abs=0.01)


def test_A03_indefinite_percentage_reference_preserved_then_css_resolved():
    s = case_snapshot("A03")
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A03"]["root.height"], abs=0.01)
    assert boxes(result)["inner"].content.height == pytest.approx(_ACCEPTANCE["A03"]["inner.height"], abs=0.01)


def test_A04_grow_remeasures_final_text_width_and_parent_height():
    s = case_snapshot("A04")
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["text"].content.width == pytest.approx(_ACCEPTANCE["A04"]["text.width"], abs=0.01)
    assert boxes(result)["text"].content.height == pytest.approx(_ACCEPTANCE["A04"]["text.height"], abs=0.01)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A04"]["root.height"], abs=0.01)


def test_A05_shrink_remeasures_both_items_at_35px():
    s = case_snapshot("A05")
    result = PythonLayoutEngine().compute(s)
    for name in ("a", "b"):
        assert boxes(result)[name].content.width == pytest.approx(_ACCEPTANCE["A05"][f"{name}.width"], abs=0.01)
        assert boxes(result)[name].content.height == pytest.approx(_ACCEPTANCE["A05"][f"{name}.height"], abs=0.01)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A05"]["root.height"], abs=0.01)


def test_A06_generation_is_preserved_by_pure_layout_result():
    s = case_snapshot("A06")
    result = PythonLayoutEngine().compute(s)
    assert result.generation == _ACCEPTANCE["A06"]["generation"]


def test_A07_convergent_auto_layout_is_finite():
    s = case_snapshot("A07")
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.height == pytest.approx(_ACCEPTANCE["A07"]["root.height"], abs=0.01)



def test_A06_stale_generation_never_commits_native_geometry():
    from psx.sfle.native_lifecycle import NativeLayoutLifecycle, layout_and_commit
    from psx.sfle.native_measurement import NativeMeasurementPort
    from psx.sfle.headless_measurement import HeadlessMeasurementSource
    from test_recursive_measurement import NODES, SIZING, METRICS, snapshot as existing_snapshot
    current_generation = [5]
    commits = []

    def measure(request):
        current_generation[0] = 6
        return HeadlessMeasurementSource(((request.node_id, METRICS),)).measure(request)

    lifecycle = NativeLayoutLifecycle(
        lambda: current_generation[0],
        NativeMeasurementPort(lambda: True, measure),
        commits.append,
    )
    with pytest.raises(SFLEError) as failure:
        layout_and_commit(existing_snapshot(), NODES, lifecycle, child_sizing=SIZING)
    assert failure.value.code == DiagnosticCode.INVALID_SNAPSHOT
    assert len(commits) == _ACCEPTANCE["A06"]["commits_from_stale_generation"]


def test_A07_bounded_two_step_oscillation_rejected():
    from psx.sfle.convergence import begin_convergence, advance_convergence
    from psx.sfle.used_size_tree import UsedSizeTree
    def tree(width):
        return UsedSizeTree(17, (("root", LayoutConstraints(
            AvailableSize(width, True), AvailableSize(60, True))),), ())
    maximum = _ACCEPTANCE["A07"]["max_iterations"]
    state = begin_convergence(tree(100), max_iterations=maximum)
    _, state = advance_convergence(state, tree(120))
    with pytest.raises(SFLEError) as failure:
        advance_convergence(state, tree(100))
    assert failure.value.code.value == _ACCEPTANCE["A07"]["oscillation"]
    assert state.iterations < maximum


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_A09_directional_positioning_preserves_identity(direction):
    s = case_snapshot("A09-" + direction.upper())
    result = PythonLayoutEngine().compute(s)
    assert tuple(node_id for node_id, _ in result.boxes) == ("root", "a", "b")
    expected = _ACCEPTANCE["A09-" + direction.upper()]
    for node_id in ("a", "b"):
        assert boxes(result)[node_id].border.x == pytest.approx(
            expected[f"{node_id}.x"], abs=0.01
        )
        assert boxes(result)[node_id].border.width == pytest.approx(
            expected[f"{node_id}.width"], abs=0.01
        )


def test_A10_layout_output_contains_separate_error_channels():
    s = case_snapshot("A10")
    result = PythonLayoutEngine().compute(s)
    assert boxes(result)["root"].content.width == pytest.approx(_ACCEPTANCE["A10"]["root.width"], abs=0.01)
    for channel in ("measurement_error", "engine_error", "geometry_commit_error"):
        assert hasattr(result, channel), f"missing normative report field {channel}"
        assert getattr(result, channel) is _ACCEPTANCE["A10"][channel]



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


@pytest.mark.parametrize("case_id", ["F01", "F02", "F04", "F05"])
def test_F01_F02_fractional_browser_oracle_red(case_id):
    """RED: an end-to-end normalized snapshot must match independent Chromium sizes."""
    snapshot_value = case_snapshot(case_id)
    result = PythonLayoutEngine().compute(snapshot_value)
    actual = boxes(result)
    expected = _ACCEPTANCE[case_id]
    assert tuple(actual) == tuple(node.node_id for node in snapshot_value.nodes)
    for key, wanted in expected.items():
        node_id, axis = key.split(".")
        assert getattr(actual[node_id].content, axis) == pytest.approx(
            wanted, abs=0.01
        ), f"{case_id} {key} must match actual Chromium used geometry"
