"""Source-preserving native mixed paragraph projection.

The existing Flex pass provides the *containing paragraph's* used width.
Inline line breaking is then solved in a separate renderer-neutral pass and
fed back as the paragraph's content height. Unlike the old approach, no word
or whitespace VNodes (and no per-word native widgets) are manufactured.

The paint plan consists of glyph fragments owned by the original Text leaves.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import re

from psx.layout.contracts.fixed_point import nearest_layout_px
from psx.layout.contracts.lengths import LengthKind, parse_length
from psx.layout.contracts.model import BoxRect, LayoutInput, LayoutNode, LayoutResult, Rect
from psx.layout.inline.semantic_inline_text import (
    InlineTextFragment, InlineTextLayout, InlineTextSource,
    InlineTextMetrics, layout_inline_text,
)

_PARAGRAPH_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6"})
_INLINE_TAGS = frozenset({"span", "label"})


def _edges(styles: dict, group: str) -> tuple[float, float, float, float]:
    result = []
    for side in ("top", "right", "bottom", "left"):
        value = styles.get(f"layout_{group}_{side}")
        if value is None:
            result.append(0.0)
            continue
        length = parse_length(value)
        if length.kind is not LengthKind.PX:
            # Percent/viewport inline decoration fragmentation is not
            # silently guessed from viewport size.
            raise ValueError("Semantic inline decoration needs resolved pixel edges.")
        result.append(float(length.value))
    return tuple(result)


def _box(rect: Rect) -> BoxRect:
    return BoxRect(rect, rect, rect, rect)


def _union(rects: list[Rect], x: float, y: float) -> Rect:
    if not rects:
        return Rect(x, y, 0, 0)
    left = min(r.x for r in rects)
    top = min(r.y for r in rects)
    right = max(r.x + r.width for r in rects)
    bottom = max(r.y + r.height for r in rects)
    px = nearest_layout_px
    return Rect(px(left), px(top), px(right-left), px(bottom-top))


def _paragraphs(snapshot: LayoutInput, origins: dict[str, object]):
    direct = defaultdict(list)
    indexed = {n.node_id: n for n in snapshot.nodes}
    for node in snapshot.nodes:
        if node.parent_id is not None:
            direct[node.parent_id].append(node.node_id)

    for node in snapshot.nodes:
        origin = origins[node.node_id]
        # Semantic root paragraphs use Cinnamon's Block/Inline compositor;
        # a paragraph inside a CSS Flex column is projected as Flex. Both
        # must share the same source-preserving glyph fragmentation.
        if origin.type not in _PARAGRAPH_TAGS or node.component not in (
            "Flex", *_PARAGRAPH_TAGS,
        ):
            continue
        children = direct[node.node_id]
        if not children or not any(origins[c].type in _INLINE_TAGS for c in children):
            continue
        source_ids = []
        wrapper_for = {}
        safe = True
        for identifier in children:
            item = origins[identifier]
            if item.type == "Text":
                source_ids.append(identifier)
            elif item.type in _INLINE_TAGS:
                nested = direct[identifier]
                if len(nested) != 1 or origins[nested[0]].type != "Text":
                    safe = False
                    break
                child_id = nested[0]
                source_ids.append(child_id)
                wrapper_for[child_id] = identifier
            else:
                safe = False
                break
        if safe and source_ids:
            yield node, tuple(source_ids), wrapper_for, indexed


def compute_semantic_inline_native(
    snapshot: LayoutInput,
    identities: tuple[tuple[str, object], ...],
    initial: LayoutResult,
    measure,
    recompute,
    *,
    engine=None,
) -> tuple[LayoutResult, dict[str, tuple[InlineTextFragment, ...]]]:
    """Return immutable source-node boxes and per-source native paint fragments.

    `measure(source_id, text)` reads an existing widget's actual font.
    `recompute(adjusted_input)` runs the same selected Rust/Python layout
    engine so ancestors (including centered Flex columns) adopt the real
    paragraph height. No native widgets are touched in this function.
    """
    origins = dict(identities)
    paragraphs = tuple(_paragraphs(snapshot, origins))
    if not paragraphs:
        return initial, {}

    styles = {n.node_id: dict(n.style) for n in snapshot.nodes}
    fixed_heights = {}
    result = initial

    def compute_runs(layout_result):
        by_id = dict(layout_result.boxes)
        runs = []
        for para, source_ids, wrappers, _ in paragraphs:
            if para.node_id not in by_id:
                continue
            paragraph_rect = by_id[para.node_id].content
            width = paragraph_rect.width
            sources = tuple(InlineTextSource(
                item_id, str(origins[item_id].props["value"]),
            ) for item_id in source_ids)
            padding = {}
            for item_id, owner_id in wrappers.items():
                owner_padding = _edges(styles[owner_id], "padding")
                owner_border = _edges(styles[owner_id], "border")
                edges = tuple(a+b for a, b in zip(owner_padding, owner_border))
                # An inline span consisting of one unbreakable word can be
                # measured as one decorated atom; multiword span slicing is
                # intentionally left to the full inline-decoration contract.
                if len(re.findall(r"\S+", origins[item_id].props["value"])) == 1:
                    padding[item_id] = edges

            def decorated(node_id, text):
                metric = measure(node_id, text)
                top, right, bottom, left = padding.get(node_id, (0, 0, 0, 0))
                return InlineTextMetrics(metric.width + left + right,
                                         metric.height + top + bottom,
                                         metric.baseline + top)

            computed = origins[para.node_id].css_computed
            text_align = (
                computed.properties.get("text-align", "left")
                if computed is not None else "left"
            )
            if text_align not in ("left", "center", "right"):
                text_align = "left"
            inline = layout_inline_text(
                sources, width, decorated, text_align=text_align, engine=engine,
            )
            runs.append((para, source_ids, wrappers, padding, inline))
        return runs

    for _ in range(2):
        runs = compute_runs(result)
        updates = {}
        for para, _, _, _, inline in runs:
            if "layout_height" not in styles[para.node_id] and "height" not in styles[para.node_id]:
                updates[para.node_id] = inline.height
        if not updates or updates == fixed_heights:
            break
        fixed_heights = updates
        changed = tuple(
            replace(node, style=tuple(sorted((*node.style, ("layout_height", updates[node.node_id])))))
            if node.node_id in updates else node for node in snapshot.nodes
        )
        result = recompute(replace(snapshot, nodes=changed))

    runs = compute_runs(result)
    output = dict(result.boxes)
    paint: dict[str, tuple[InlineTextFragment, ...]] = {}
    for para, source_ids, wrappers, padding, inline in runs:
        paragraph = output[para.node_id].content
        grouped = defaultdict(list)
        for fragment in inline.fragments:
            grouped[fragment.node_id].append(fragment)
        for identifier in source_ids:
            fragments = grouped[identifier]
            edges = padding.get(identifier, (0, 0, 0, 0))
            top, right, bottom, left = edges
            painted = []
            for f in fragments:
                raw = measure(identifier, f.text)
                painted.append(replace(
                    f, x=nearest_layout_px(paragraph.x + f.x + left),
                    y=nearest_layout_px(paragraph.y + f.y + top),
                    width=nearest_layout_px(raw.width),
                    height=nearest_layout_px(raw.height),
                    baseline=nearest_layout_px(raw.baseline),
                ))
            paint[identifier] = tuple(painted)
            area = _union([Rect(f.x, f.y, f.width, f.height) for f in painted],
                          paragraph.x, paragraph.y)
            output[identifier] = _box(area)
        for identifier in set(wrappers.values()):
            descendants = [child_id for child_id, owner_id in wrappers.items()
                           if owner_id == identifier]
            content = _union([output[i].content for i in descendants],
                             paragraph.x, paragraph.y)
            # The background belongs to the authored span, not to the Text
            # leaves. Keep the native host border box around the decorated
            # fragment without inventing another semantic node.
            t, r, b, l = padding.get(descendants[0], (0, 0, 0, 0))
            border = Rect(
                nearest_layout_px(content.x-l), nearest_layout_px(content.y-t),
                nearest_layout_px(content.width+l+r),
                nearest_layout_px(content.height+t+b),
            )
            output[identifier] = BoxRect(content, border, border, border)

    return replace(result, boxes=tuple((node.node_id, output[node.node_id])
                                      for node in snapshot.nodes)), paint
