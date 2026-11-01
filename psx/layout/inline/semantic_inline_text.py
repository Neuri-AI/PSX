"""Renderer-neutral inline text fragmentation without expanding the VNode tree.

This module consumes *source* Text leaves. A source Text leaf may paint in many
line fragments; those fragments are geometry records, not reconciler children
or native widgets. In particular, an HTML span is never discarded or flattened
away, so cascade, keys and refs retain their semantic identities.

This is a bounded CSS white-space:normal / LTR word-wrapping kernel. Complex
text shaping, bidi, inline box decoration and intrinsic inline object placement
need a richer layout contract and are NOT claimed to be implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from collections.abc import Callable, Sequence



@dataclass(frozen=True, slots=True)
class InlineTextSource:
    node_id: str
    text: str

    def __post_init__(self):
        if not isinstance(self.node_id, str) or not self.node_id:
            raise ValueError("An inline text source needs a stable node ID.")
        if not isinstance(self.text, str):
            raise TypeError("Inline text must be a string.")


@dataclass(frozen=True, slots=True)
class InlineTextMetrics:
    width: float
    height: float
    baseline: float

    def __post_init__(self):
        if any(not math.isfinite(v) for v in (self.width, self.height, self.baseline)):
            raise ValueError("Invalid inline metrics.")
        if self.width < 0 or self.height < 0 or not 0 <= self.baseline <= self.height:
            raise ValueError("Invalid inline metrics.")


@dataclass(frozen=True, slots=True)
class InlineTextFragment:
    node_id: str
    text: str
    start: int
    end: int
    line_index: int
    x: float
    y: float
    width: float
    height: float
    baseline: float


@dataclass(frozen=True, slots=True)
class InlineTextLayout:
    fragments: tuple[InlineTextFragment, ...]
    width: float
    height: float
    line_count: int


def _measured_inline_atoms(
    sources: Sequence[InlineTextSource],
    measure: Callable[[str, str], InlineTextMetrics],
) -> list[dict[str, object]]:
    """Shared tokenization + native measurement wire for the Rust kernel.

    Tokenization/Unicode shaping is a frontend concern. Rust and Python
    receive the same source identities, offsets and native glyph metrics.
    Only line breaking/placement differs between engine implementations.
    """
    atoms: list[dict[str, object]] = []
    preceding_word = False
    pending_space: tuple[InlineTextSource, int, int] | None = None

    def append(source: InlineTextSource, text: str,
               start: int, end: int, space: bool) -> None:
        metrics = measure(source.node_id, text)
        atoms.append({
            "node_id": source.node_id, "text": text,
            "start": start, "end": end, "space": space,
            "width": metrics.width, "height": metrics.height,
            "baseline": metrics.baseline,
        })

    for source in sources:
        for match in re.finditer(r"\s+|\S+", source.text):
            text = match.group()
            if text.isspace():
                if preceding_word and pending_space is None:
                    pending_space = (source, match.start(), match.end())
                continue
            if pending_space is not None:
                owner, start, end = pending_space
                append(owner, " ", start, end, True)
                pending_space = None
            append(source, text, match.start(), match.end(), False)
            preceding_word = True
    return atoms


def layout_inline_text(
    sources: Sequence[InlineTextSource],
    available_width: float,
    measure: Callable[[str, str], InlineTextMetrics],
    *,
    text_align: str = "left",
    engine: object | None = None,
) -> InlineTextLayout:
    """Compute breakable ink fragments while preserving each source VNode.

    measure(node_id, fragment) must use the *same font* the native backend
    uses to paint that source. Spaces are measured, but omitted at wrapped
    line edges per CSS white-space:normal. Line baselines derive from the
    native measurements, not a fixed font-size multiple.
    """
    if not math.isfinite(available_width) or available_width < 0:
        raise ValueError("Inline containing width must be finite and nonnegative.")
    if text_align not in ("left", "right", "center"):
        raise ValueError("Unsupported inline text alignment.")

    # Select the numerical backend before computing; never fall through to
    # Python because callers omitted the optional engine argument.
    if engine is None:
        from psx.layout.engine.backend import load_layout_engine
        engine = load_layout_engine()
    compute = getattr(engine, "layout_inline_text", None)
    if not callable(compute):
        raise TypeError("Inline layout requires an engine with layout_inline_text().")
    return compute(
        sources, available_width, measure, text_align=text_align,
    )
