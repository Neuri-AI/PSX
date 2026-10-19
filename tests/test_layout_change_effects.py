"""Internal change-effect classification and detached signature regression tests."""
from psx.sfle.layout_change_effects import (
    ChangeEffect, classify_change, detached_literal,
    partition_dependency_signature,
)


def test_effect_categories_are_conservative_and_explicit():
    assert classify_change("Text", "color") is ChangeEffect.PAINT
    assert classify_change("Text", "value") is ChangeEffect.MEASUREMENT
    assert classify_change("Image", "source") is ChangeEffect.MEASUREMENT
    assert classify_change("Text", "layout_width") is ChangeEffect.GEOMETRY
    assert classify_change("Flex", "gap") is ChangeEffect.GEOMETRY
    assert classify_change("Text", "key") is ChangeEffect.STRUCTURE
    assert classify_change("Text", "enabled") is ChangeEffect.INTERACTION
    assert classify_change("Custom", "color") is ChangeEffect.GEOMETRY
    assert classify_change("Text", "unrecognized") is ChangeEffect.GEOMETRY


def test_only_existing_text_color_is_excluded_from_layout_dependencies():
    base = (("root", "Flex", 1, {"width": "120px"}),
            ("child", "Text", 2, {"value": "hello", "color": "#111"}))
    color = (("root", "Flex", 1, {"width": "120px"}),
             ("child", "Text", 2, {"value": "hello", "color": "#222"}))
    width = (("root", "Flex", 1, {"width": "120px"}),
             ("child", "Text", 2, {"value": "hello", "color": "#222",
                                    "layout_width": "75px"}))
    first, safe = partition_dependency_signature(base, ("viewport", 120))
    second, other_safe = partition_dependency_signature(color, ("viewport", 120))
    third, width_safe = partition_dependency_signature(width, ("viewport", 120))
    assert safe and other_safe and width_safe
    assert first[0] == second[0]
    assert first[1] != second[1]
    assert second[0] != third[0]
    different_viewport, _ = partition_dependency_signature(color, ("viewport", 200))
    assert second[0] != different_viewport[0]


def test_callbacks_mutable_owners_and_unrecognized_props_disable_reuse():
    owner = object()
    callback = lambda: None
    for value in (owner, callback, {"nested": 1}, ["mutable"]):
        assert detached_literal(value)[0] is False
        signature, safe = partition_dependency_signature((
            ("root", "Text", 7, {"color": "#111", "unknown": value}),
        ), "viewport")
        assert not safe
        assert value is not signature and not any(
            part is value for part in signature
        )
    assert detached_literal(("width", 12, ("height", 8))) == (
        True, ("width", 12, ("height", 8)),
    )


def test_dirty_layout_nodes_ignores_paint_but_detects_measurement_and_geometry():
    from psx.sfle.layout_change_effects import dirty_layout_nodes
    before = (
        ("root", "Flex", 1, {"gap": "10px"}),
        ("a", "Text", 2, {"value": "one", "color": "#111"}),
        ("b", "Text", 3, {"value": "two"}),
    )
    recolored = (
        before[0],
        ("a", "Text", 2, {"value": "one", "color": "#222"}),
        before[2],
    )
    assert dirty_layout_nodes(before, recolored) == frozenset()
    rewritten = (
        before[0],
        ("a", "Text", 2, {"value": "changed", "color": "#222"}),
        before[2],
    )
    assert dirty_layout_nodes(before, rewritten) == frozenset({"a"})
    widened = (("root", "Flex", 1, {"gap": "20px"}), *before[1:])
    assert dirty_layout_nodes(before, widened) == frozenset({"root"})
    assert dirty_layout_nodes(before, recolored, constraints_changed=True) is None
    assert dirty_layout_nodes(None, recolored) is None


def test_dirty_layout_nodes_fails_closed_on_structure_or_unsafe_values():
    from psx.sfle.layout_change_effects import dirty_layout_nodes
    before = (("a", "Text", 1, {"value": "ok"}),)
    assert dirty_layout_nodes(before, ()) is None
    assert dirty_layout_nodes(before, (("a", "Text", 2, {"value": "ok"}),)) is None
    assert dirty_layout_nodes(before, (("a", "Text", 1, {"key": "new"}),)) is None
    assert dirty_layout_nodes(before, (("a", "Text", 1, {"value": object()}),)) is None
    assert dirty_layout_nodes(before, (("a", "Text", 1, {"value": "ok"}),
                                       ("a", "Text", 1, {}))) is None


def test_flex_context_planner_preserves_independent_sibling_context():
    from psx.sfle.layout_change_effects import affected_flex_contexts
    parents = {
        "root": None, "left": "root", "left_text": "left",
        "right": "root", "right_text": "right",
    }
    flex = frozenset({"root", "left", "right"})
    assert affected_flex_contexts(
        frozenset({"left_text"}), parent_by_id=parents,
        flex_node_ids=flex,
    ) == frozenset({"root", "left"})
    assert affected_flex_contexts(
        frozenset(), parent_by_id=parents, flex_node_ids=flex,
    ) == frozenset()
    assert affected_flex_contexts(
        frozenset({"root"}), parent_by_id=parents, flex_node_ids=flex,
    ) == flex
    assert affected_flex_contexts(
        None, parent_by_id=parents, flex_node_ids=flex,
    ) is None
    assert affected_flex_contexts(
        frozenset({"missing"}), parent_by_id=parents, flex_node_ids=flex,
    ) is None


def test_flex_planner_rejects_invalid_parent_graph():
    from psx.sfle.layout_change_effects import affected_flex_contexts
    assert affected_flex_contexts(
        frozenset({"x"}), parent_by_id={"x": "missing"},
        flex_node_ids=frozenset({"x"}),
    ) is None
    assert affected_flex_contexts(
        frozenset({"x"}), parent_by_id={"x": "x"},
        flex_node_ids=frozenset({"x"}),
    ) is None
