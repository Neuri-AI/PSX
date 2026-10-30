"""Scroll viewport content extents must share one Kivy Y-axis origin.

These tests use the native geometry transaction without loading a graphics
provider. Cinnamon stays authoritative; the expected ScrollView translation
matches the Kivy 2.3.1 viewport matrix at its two scroll endpoints.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from psx.sfle.grid_native_composition import ComposedGrid, compose_geometry_batch
from psx.sfle.grid_native_commit import GridCommitBackend, commit_grid_native_geometry
from psx.sfle.grid_native_plan import GridNativePlacement
from psx.sfle.model import Rect
from psx.sfle.native_layout_snapshot import path_identity


class NativeWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.pos = (0.0, 0.0)
        self.size = (1.0, 1.0)

    @property
    def x(self):
        return self.pos[0]

    @property
    def y(self):
        return self.pos[1]


def _scene(viewport_height: float, content_extent: float):
    """Grid > GridItem > Scroll > GridItem > div with overflow descendants."""
    root = NativeWidget()
    wrapper = NativeWidget(root)
    scroll = NativeWidget(wrapper)
    scroll_item = NativeWidget(scroll)
    content_root = NativeWidget(scroll_item)
    header = NativeWidget(content_root)
    footer = NativeWidget(content_root)
    sublabel = NativeWidget(header)

    item_source, scroll_source, flow_source = object(), object(), object()
    header_source, footer_source, sublabel_source = object(), object(), object()
    item_id = path_identity(("dashboard", "main"))
    content = SimpleNamespace(source=flow_source)
    scrolling = SimpleNamespace(source=scroll_source, effective_children=(content,))
    item = SimpleNamespace(
        path=("dashboard", "main"), source=item_source,
        effective_children=(scrolling,),
    )

    # The CSS root has an 800px border box, but descendant overflow extends
    # to content_extent. The visible Scroll viewport is independently sized.
    border_boxes = (
        ("flow",  None, Rect(0, 0, 400, 800)),
        ("header", "flow", Rect(0, 0, 400, 50)),
        ("sublabel", "header", Rect(8, 10, 100, 20)),
        ("footer", "flow", Rect(0, content_extent - 50, 400, 50)),
    )
    nodes = tuple(
        SimpleNamespace(node_id=key, parent_id=parent)
        for key, parent, box in border_boxes
    )
    boxes = tuple(
        (key, SimpleNamespace(border=box))
        for key, parent, box in border_boxes
    )
    flow = SimpleNamespace(
        prepared=SimpleNamespace(
            snapshot=SimpleNamespace(nodes=nodes),
            identities=(
                ("flow", flow_source),
                ("header", header_source),
                ("sublabel", sublabel_source),
                ("footer", footer_source),
            ),
        ),
        result=SimpleNamespace(boxes=boxes),
        nested_grids={},
    )
    composed = ComposedGrid(
        grid=SimpleNamespace(effective_children=(item,)),
        prepared=SimpleNamespace(placements=(
            GridNativePlacement(
                item_id, 0, 0, 400, viewport_height,
                400, viewport_height, False, False,
            ),
        )),
        nested={}, nested_flex={}, nested_flow={},
        nested_scroll={
            item_id: (flow, 400.0, viewport_height, content_extent),
        },
        content_height=viewport_height,
    )
    placements, widgets, heights = compose_geometry_batch(
        composed,
        handles={
            id(item_source): wrapper,
            id(scroll_source): scroll,
            id(flow_source): content_root,
            id(header_source): header,
            id(footer_source): footer,
            id(sublabel_source): sublabel,
        },
        root_height=viewport_height,
    )
    return item_id, placements, widgets, heights, content_root, header, footer, sublabel


@pytest.mark.parametrize("viewport_height", [280.0, 600.0, 750.0])
@pytest.mark.parametrize("content_extent", [900.0, 1100.0, 1700.0])
def test_grid_scroll_children_use_full_content_extent_on_vertical_resize(
    viewport_height, content_extent,
):
    item_id, placements, widgets, heights, root, header, footer, sublabel = (
        _scene(viewport_height, content_extent)
    )
    flow_id = item_id + "/scroll/content"
    header_id = flow_id + "/header"
    footer_id = flow_id + "/footer"
    sublabel_id = flow_id + "/sublabel"

    # The Kivy ScrollView viewport moves its canvas with a matrix; the CSS
    # children must be Y-flipped against the same extent as that matrix.
    assert heights[flow_id] == content_extent
    assert heights[header_id] == content_extent
    assert heights[footer_id] == content_extent
    assert heights[sublabel_id] == 50.0

    receipt = commit_grid_native_geometry(
        placements, backend=GridCommitBackend.KIVY,
        widgets=widgets, generation=1, current_generation=lambda: 1,
        is_ui_thread=lambda: True,
        parent_height=viewport_height, parent_heights=heights,
        kivy_window_coordinates=True,
    )
    assert receipt.max_readback_error <= 0.00001
    assert root.y == pytest.approx(0)
    assert header.y == pytest.approx(content_extent - 50)
    assert footer.y == pytest.approx(0)
    assert sublabel.y == pytest.approx(header.y + 20)

    # On Kivy, scroll_y=1 translates the viewport by -(extent - visible).
    # The first header starts exactly at the viewport's TOP, no blank band.
    top_translate_y = -(content_extent - viewport_height)
    assert header.y + header.size[1] + top_translate_y == pytest.approx(
        viewport_height,
    )
    # At scroll_y=0, translation is zero. The footer remains reachable at
    # the native bottom, rather than extending below the scroll boundary.
    bottom_translate_y = 0.0
    assert footer.y + bottom_translate_y == pytest.approx(0)
