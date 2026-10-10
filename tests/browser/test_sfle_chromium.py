"""Small opt-in Chromium geometry checkpoint for the resolved SFLE Flex kernel.

This compares *border-box rectangles* only for explicitly supported,
fully definite CSS inputs. It does not claim full CSS conformance.
Run with: python -m pytest -q tests/browser/test_sfle_chromium.py
Requires: playwright, plus 'python -m playwright install chromium'.
"""
from __future__ import annotations

from dataclasses import dataclass
import pytest

from psx.sfle.align_content import AlignContent
from psx.sfle.cross_alignment import CrossAlign
from psx.sfle.flex_math import FlexBasis
from psx.sfle.line_layout import FlexDirection, FlexWrap
from psx.sfle.main_alignment import JustifyContent
from psx.sfle.margin_flex_pipeline import MarginFlexItem, compute_margin_flex_layout
from psx.sfle.model import WritingDirection


@dataclass(frozen=True)
class Case:
    name: str
    width: float
    height: float
    items: tuple[MarginFlexItem, ...]
    style: str
    item_styles: tuple[str, ...]
    direction: FlexDirection = FlexDirection.ROW
    writing: WritingDirection = WritingDirection.LTR
    wrap: FlexWrap = FlexWrap.NOWRAP
    main_gap: float = 0
    cross_gap: float = 0
    justify: JustifyContent = JustifyContent.FLEX_START
    align_items: CrossAlign = CrossAlign.FLEX_START
    align_content: AlignContent = AlignContent.FLEX_START


def item(name: str, main: float, cross: float, *, auto_cross: bool = False) -> MarginFlexItem:
    return MarginFlexItem(
        name, FlexBasis(main, main, grow=0, shrink=0),
        cross, cross_size_auto=auto_cross,
    )


CASES = (
    Case(
        "centered row", 100, 100,
        (item("a", 20, 10), item("b", 20, 10)),
        "justify-content:center; align-items:center;",
        ("width:20px;height:10px;", "width:20px;height:10px;"),
        justify=JustifyContent.CENTER, align_items=CrossAlign.CENTER,
    ),
    Case(
        "RTL space-between", 100, 60,
        (item("a", 20, 10), item("b", 20, 10)),
        "direction:rtl;justify-content:space-between;",
        ("width:20px;height:10px;", "width:20px;height:10px;"),
        writing=WritingDirection.RTL, justify=JustifyContent.SPACE_BETWEEN,
    ),
    Case(
        "wrapped lines space-between", 100, 100,
        (item("a", 60, 20), item("b", 60, 20)),
        "flex-wrap:wrap;align-content:space-between;row-gap:10px;",
        ("width:60px;height:20px;", "width:60px;height:20px;"),
        wrap=FlexWrap.WRAP, cross_gap=10, align_content=AlignContent.SPACE_BETWEEN,
    ),
    Case(
        "wrapped lines stretch with centered children", 100, 100,
        (item("a", 60, 20), item("b", 60, 20)),
        "flex-wrap:wrap;align-content:stretch;align-items:center;row-gap:10px;",
        ("width:60px;height:20px;", "width:60px;height:20px;"),
        wrap=FlexWrap.WRAP, cross_gap=10,
        align_content=AlignContent.STRETCH, align_items=CrossAlign.CENTER,
    ),
    Case(
        "auto cross-size stretch", 100, 100,
        (item("a", 20, 0, auto_cross=True),),
        "align-items:stretch;",
        ("width:20px;height:auto;",),
        align_items=CrossAlign.STRETCH,
    ),
    Case(
        "column RTL center", 100, 100,
        (item("a", 20, 10),),
        "flex-direction:column;direction:rtl;align-items:center;",
        ("height:20px;width:10px;",),
        direction=FlexDirection.COLUMN, writing=WritingDirection.RTL,
        align_items=CrossAlign.CENTER,
    ),
)


@pytest.fixture(scope="module")
def chromium_page():
    # Not collected by the general SFLE pytest job (tests/sfle).
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 800, "height": 600},
                                    device_scale_factor=1)
            yield page
        finally:
            browser.close()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_resolved_border_rectangles_match_chromium(case: Case, chromium_page):
    from html import escape

    # Position relative to the container border box; no viewport offset.
    # Set zero margin/padding/border and flex:0 0 <definite size> explicitly.
    html_items = "".join(
        f'<div id="{escape(box.node_id)}" style="'
        f'flex:0 0 {box.flex.basis}px;min-width:0;min-height:0;'
        f'box-sizing:content-box;{style}"></div>'
        for box, style in zip(case.items, case.item_styles, strict=True)
    )
    html = (
        '<!doctype html><html><body style="margin:0;padding:0">'
        f'<div id="root" style="display:flex;box-sizing:content-box;'
        f'width:{case.width}px;height:{case.height}px;'
        f'border:0;padding:0;gap:0;{case.style}">{html_items}</div>'
        '</body></html>'
    )
    chromium_page.set_content(html)
    actual = chromium_page.evaluate("""() => {
      const root = document.getElementById('root').getBoundingClientRect();
      return Array.from(document.getElementById('root').children, child => {
        const rect = child.getBoundingClientRect();
        return { id: child.id, x: rect.left-root.left, y: rect.top-root.top,
                 width: rect.width, height: rect.height };
      });
    }""")
    expected = compute_margin_flex_layout(
        case.items, case.width, case.height,
        direction=case.direction, writing=case.writing, wrap=case.wrap,
        main_gap=case.main_gap, cross_gap=case.cross_gap, justify=case.justify,
        align_items=case.align_items, align_content=case.align_content,
    )
    by_id = {rect["id"]: rect for rect in actual}
    assert set(by_id) == {box.node_id for box in expected.boxes}
    for box in expected.boxes:
        browser_box = by_id[box.node_id]
        for field in ("x", "y", "width", "height"):
            assert getattr(box.border, field) == pytest.approx(
                browser_box[field], abs=0.05,
            ), f"{case.name}: {box.node_id}.{field}: SFLE vs Chromium"


def test_nested_resolved_flex_boxes_match_chromium(chromium_page):
    """First true nested reference geometry check, limited to zero-edge boxes."""
    from psx.sfle.resolved_tree import ResolvedTreeNode, compute_resolved_tree

    def basis(value: float) -> FlexBasis:
        return FlexBasis(value, value, grow=0, shrink=0, min_size=0)

    nodes = (
        ResolvedTreeNode("root", None, 200, 80, main_gap=10),
        ResolvedTreeNode("a", "root", 40, 20, basis(40)),
        ResolvedTreeNode("b", "root", 100, 40, basis(100)),
        ResolvedTreeNode("c", "b", 30, 10, basis(30)),
    )
    chromium_page.set_content(
        '<!doctype html><html><body style="margin:0">'
        '<div id="root" style="display:flex;width:200px;height:80px;'
        'gap:10px;align-items:flex-start">'
        '<div id="a" style="flex:0 0 40px;width:40px;height:20px;min-width:0"></div>'
        '<div id="b" style="display:flex;flex:0 0 100px;width:100px;height:40px;'
        'align-items:flex-start;min-width:0">'
        '<div id="c" style="flex:0 0 30px;width:30px;height:10px;min-width:0"></div>'
        '</div></div></body></html>'
    )
    actual = chromium_page.evaluate("""() => {
      const result = {};
      for (const id of ['root', 'a', 'b', 'c']) {
        const rect = document.getElementById(id).getBoundingClientRect();
        result[id] = {x:rect.x,y:rect.y,width:rect.width,height:rect.height};
      }
      return result;
    }""")
    expected = compute_resolved_tree(nodes, generation=8)
    for node_id, box in expected.boxes:
        for axis in ("x", "y", "width", "height"):
            assert getattr(box.border, axis) == pytest.approx(
                actual[node_id][axis], abs=0.05,
            ), f"nested {node_id}.{axis}: SFLE vs Chromium"


def test_nested_padding_border_content_origins_match_chromium(chromium_page):
    """F2.2.4.6 nested content-box placement with actual padding/borders."""
    from psx.sfle.box_geometry import UsedBoxEdges, UsedEdges
    from psx.sfle.edge_tree import EdgeTreeNode, compute_edge_tree
    def flex(n):
        return FlexBasis(n, n, grow=0, shrink=0, min_size=0)
    root_edges=UsedBoxEdges(padding=UsedEdges(top=3,left=5),
                            border=UsedEdges(top=2,left=1))
    parent_edges=UsedBoxEdges(padding=UsedEdges(top=4,left=6),
                              border=UsedEdges(top=1,left=2))
    nodes=(
        EdgeTreeNode("root",None,200,80,edges=root_edges),
        EdgeTreeNode("parent","root",50,30,flex=flex(50),edges=parent_edges),
        EdgeTreeNode("leaf","parent",10,10,flex=flex(10)),
    )
    chromium_page.set_content(
        '<!doctype html><html><body style="margin:0">'
        '<div id="root" style="display:flex;width:200px;height:80px;'
        'padding:3px 0 0 5px;border-style:solid;border-width:2px 0 0 1px;'
        'box-sizing:content-box;align-items:flex-start">'
        '<div id="parent" style="display:flex;flex:0 0 50px;width:50px;height:30px;'
        'padding:4px 0 0 6px;border-style:solid;border-width:1px 0 0 2px;'
        'box-sizing:content-box;align-items:flex-start;min-width:0">'
        '<div id="leaf" style="flex:0 0 10px;width:10px;height:10px;'
        'min-width:0"></div></div></div></body></html>'
    )
    actual=chromium_page.evaluate("""() => {
      const result={};
      for(const id of ['root','parent','leaf']){
        const r=document.getElementById(id).getBoundingClientRect();
        result[id]={x:r.x,y:r.y,width:r.width,height:r.height};
      }
      return result;
    }""")
    for id,box in compute_edge_tree(nodes,generation=8).boxes:
        for axis in ('x','y','width','height'):
            assert getattr(box.border,axis)==pytest.approx(actual[id][axis],abs=0.05), (
                f'nested edges {id}.{axis}: SFLE vs Chromium'
            )
