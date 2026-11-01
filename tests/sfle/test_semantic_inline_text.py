"""Semantic inline wrapping does not multiply the declarative VNode tree."""
from __future__ import annotations

import pytest

from psx.layout.fallback.semantic_inline_text import (
    InlineTextMetrics, InlineTextSource, layout_inline_text,
)


def mono(_node_id: str, text: str) -> InlineTextMetrics:
    return InlineTextMetrics(len(text) * 10, 20, 15)


def test_source_nodes_survive_arbitrary_wraps():
    source = (
        InlineTextSource("before", "Edit "),
        InlineTextSource("inside", "main.py"),
        InlineTextSource("after", " and save to test HMR"),
    )
    wide = layout_inline_text(source, 800, mono)
    narrow = layout_inline_text(source, 190, mono)
    assert wide.line_count == 1
    assert narrow.line_count > 1
    assert [fragment.node_id for fragment in wide.fragments if fragment.text.strip()] == [
        "before", "inside", "after", "after", "after", "after", "after",
    ]
    # The number of SOURCE nodes never changes; layout is a pure derivative.
    assert len(source) == 3
    assert tuple(s.text for s in source) == (
        "Edit ", "main.py", " and save to test HMR",
    )
    # The author's span boundary is not itself a wrapping opportunity.
    assert narrow.fragments[1].text == " "
    assert any(f.node_id == "inside" and f.text == "main.py" for f in narrow.fragments)


def test_space_at_wrap_boundary_is_elided_but_source_is_intact():
    result = layout_inline_text(
        (InlineTextSource("a", "alpha beta gamma"),), 100, mono,
    )
    assert result.line_count == 2
    assert [f.text for f in result.fragments] == ["alpha", " ", "beta", "gamma"]
    assert result.fragments[-1].x == 0
    assert result.fragments[-1].line_index == 1


def test_style_boundary_without_whitespace_does_not_create_a_break():
    result = layout_inline_text(
        (InlineTextSource("a", "hel"), InlineTextSource("b", "lo")), 35, mono,
    )
    assert result.line_count == 1
    assert [fragment.node_id for fragment in result.fragments] == ["a", "b"]
    assert result.width == 50


def test_native_metrics_control_line_baselines():
    def measure(owner, text):
        return InlineTextMetrics(len(text) * 10, 30 if owner == "big" else 20,
                                 25 if owner == "big" else 15)
    result = layout_inline_text(
        (InlineTextSource("normal", "Hi "), InlineTextSource("big", "there")),
        200, measure,
    )
    first = next(f for f in result.fragments if f.node_id == "normal")
    other = next(f for f in result.fragments if f.node_id == "big")
    assert first.y + first.baseline == other.y + other.baseline
    assert result.height == 30


@pytest.mark.parametrize("alignment,expected", [
    ("left", 0), ("center", 25), ("right", 50),
])
def test_inline_text_alignment(alignment, expected):
    result = layout_inline_text(
        (InlineTextSource("word", "hello"),), 100, mono, text_align=alignment,
    )
    assert result.fragments[0].x == expected


def test_empty_and_whitespace_only_text_produces_no_ink():
    assert layout_inline_text([InlineTextSource("a", " \n  ")], 100, mono).fragments == ()


def test_rejects_invalid_measurements_and_width():
    with pytest.raises(ValueError):
        layout_inline_text([InlineTextSource("a", "a")], float("nan"), mono)
    with pytest.raises(ValueError):
        InlineTextMetrics(2, 5, 6)
