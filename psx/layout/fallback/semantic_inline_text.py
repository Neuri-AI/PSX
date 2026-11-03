"""Optional standalone Python Cinnamon inline numerical solver.

Importing the shared inline contract or using Rust must not import this file.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence

from psx.layout.contracts.fixed_point import nearest_layout_px
from psx.layout.inline.semantic_inline_text import (
    InlineTextSource, InlineTextMetrics, InlineTextFragment,
    InlineTextLayout,
)


def python_layout_inline_text(
    sources: Sequence[InlineTextSource],
    available_width: float,
    measure: Callable[[str, str], InlineTextMetrics],
    *,
    text_align: str = "left",
) -> InlineTextLayout:
    if not math.isfinite(available_width) or available_width < 0:
        raise ValueError("Inline containing width must be finite and nonnegative.")
    if text_align not in ("left", "right", "center"):
        raise ValueError("Unsupported inline text alignment.")

    px = nearest_layout_px
    limit = px(available_width)
    # Each item is (source, content, start, end, intrinsic). Only line-break
    # opportunities separate words; a CSS span boundary alone is NOT a break.
    lines: list[list[tuple[InlineTextSource, str, int, int, InlineTextMetrics]]] = []
    line: list[tuple[InlineTextSource, str, int, int, InlineTextMetrics]] = []
    cursor = 0.0
    pending_space: tuple[InlineTextSource, int, int] | None = None
    prior_content = False

    def flush() -> None:
        nonlocal line, cursor
        if line:
            lines.append(line)
            line = []
            cursor = 0.0

    for source in sources:
        for match in re.finditer(r"\s+|\S+", source.text):
            content = match.group()
            if content.isspace():
                if prior_content and pending_space is None:
                    pending_space = (source, match.start(), match.end())
                continue

            measured = measure(source.node_id, content)
            word_width = px(measured.width)
            gap = None
            gap_width = 0.0
            if pending_space is not None and line:
                gap_owner, start, end = pending_space
                gap_measure = measure(gap_owner.node_id, " ")
                gap = (gap_owner, " ", start, end, gap_measure)
                gap_width = px(gap_measure.width)

            # Do not wrap merely because a style/span boundary is crossed:
            # a whitespace opportunity must separate the two words.
            if line and gap is not None and px(cursor + gap_width + word_width) > limit:
                flush()
                gap = None
                gap_width = 0.0

            if gap is not None:
                line.append(gap)
                cursor = px(cursor + gap_width)
            line.append((source, content, match.start(), match.end(), measured))
            cursor = px(cursor + word_width)
            pending_space = None
            prior_content = True

    flush()
    y = 0.0
    fragments: list[InlineTextFragment] = []
    max_used = 0.0
    for line_index, atoms in enumerate(lines):
        ascent = max(px(item[4].baseline) for item in atoms)
        descent = max(px(item[4].height - item[4].baseline) for item in atoms)
        used = px(sum(px(item[4].width) for item in atoms))
        max_used = max(max_used, used)
        offset = px(max(0.0, limit - used) * (
            0.5 if text_align == "center" else 1.0 if text_align == "right" else 0.0
        ))
        x = offset
        for source, text, start, end, intrinsic in atoms:
            fragments.append(InlineTextFragment(
                source.node_id, text, start, end, line_index,
                x, px(y + ascent - intrinsic.baseline),
                px(intrinsic.width), px(intrinsic.height), px(intrinsic.baseline),
            ))
            x = px(x + intrinsic.width)
        y = px(y + ascent + descent)
    return InlineTextLayout(tuple(fragments), max_used, y, len(lines))

# Historical Python-only entry point: importing this module explicitly must
# continue to choose the Python numerical solver even if Rust is installed.
def layout_inline_text(
    sources: Sequence[InlineTextSource],
    available_width: float,
    measure: Callable[[str, str], InlineTextMetrics],
    *,
    text_align: str = "left",
    engine: object | None = None,
) -> InlineTextLayout:
    """Historical fallback entry point; preserve explicit Rust differential use.

    Omitted engine selects Python only because the caller explicitly imported
    the optional Python fallback module. Calls with an engine keep dispatching
    through the shared engine-neutral entry point.
    """
    if engine is None:
        return python_layout_inline_text(
            sources, available_width, measure, text_align=text_align,
        )
    from psx.layout.inline.semantic_inline_text import (
        layout_inline_text as selected_layout_inline_text,
    )
    return selected_layout_inline_text(
        sources, available_width, measure, text_align=text_align, engine=engine,
    )
