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
