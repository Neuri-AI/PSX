"""Explicit CSS outer/inner display semantics and fail-closed defaults."""
import pytest

from psx.sfle.display_context import (
    DisplayMode, InnerDisplay, OuterDisplay, display_change_requires_reflow,
    resolve_display,
)


@pytest.mark.parametrize(
    ("tag", "outer"),
    [
        ("div", OuterDisplay.BLOCK),
        ("span", OuterDisplay.INLINE),
        ("p", OuterDisplay.BLOCK),
        ("h1", OuterDisplay.BLOCK),
        ("h6", OuterDisplay.BLOCK),
        ("section", OuterDisplay.BLOCK),
        ("main", OuterDisplay.BLOCK),
        ("header", OuterDisplay.BLOCK),
        ("footer", OuterDisplay.BLOCK),
        ("form", OuterDisplay.BLOCK),
        ("label", OuterDisplay.INLINE),
        ("ul", OuterDisplay.BLOCK),
        ("li", OuterDisplay.BLOCK),
    ],
)
def test_html_tag_default_outer_display(tag, outer):
    mode = resolve_display(tag)
    assert mode.outer is outer
    assert mode.inner is InnerDisplay.FLOW


@pytest.mark.parametrize(
    ("css", "outer", "inner"),
    [
        ("block", OuterDisplay.BLOCK, InnerDisplay.FLOW),
        ("inline", OuterDisplay.INLINE, InnerDisplay.FLOW),
        ("inline-block", OuterDisplay.INLINE, InnerDisplay.FLOW_ROOT),
        ("flow-root", OuterDisplay.BLOCK, InnerDisplay.FLOW_ROOT),
        ("flex", OuterDisplay.BLOCK, InnerDisplay.FLEX),
        ("inline-flex", OuterDisplay.INLINE, InnerDisplay.FLEX),
    ],
)
def test_display_values_separate_outer_and_inner_types(css, outer, inner):
    mode = resolve_display("div", css)
    assert mode == DisplayMode(outer, inner)
    assert mode.establishes_independent_formatting_context == (
        inner is not InnerDisplay.FLOW
    )


def test_change_from_block_to_inline_requires_reflow():
    before = resolve_display("div")
    after = resolve_display("div", "inline")
    assert display_change_requires_reflow(before, after)
    assert not display_change_requires_reflow(after, after)


@pytest.mark.parametrize("value", ["grid", "none", "table", "contents", "inline grid", 2])
def test_unimplemented_display_fails_closed(value):
    with pytest.raises(ValueError, match="Unsupported CSS display"):
        resolve_display("div", value)


def test_legacy_components_do_not_inherit_html_defaults():
    with pytest.raises(ValueError, match="Unsupported HTML-like"):
        resolve_display("Flex")
