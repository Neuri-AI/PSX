"""HTML block width semantics use one CSS/Cinnamon projection for every backend.

Qt, Tk and Kivy all call PreparedNativeLayoutSnapshot.css_geometry_snapshot,
which determines block host geometry before any native widget placement.
"""
import pytest

from psx.markup.compile import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutInput,
    MeasuredBox,
)


def _prepared(markup, viewport=800, scope=None):
    constraints = LayoutConstraints(
        AvailableSize(viewport, True), AvailableSize(600, True),
    )
    node = psx(markup, scope=scope)
    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(node), constraints, generation=1,
    )
    snapshot = prepared.css_geometry_snapshot()
    records = {
        source.type: (node, dict(node.style))
        for node in snapshot.nodes
        for identifier, source in prepared.identities
        if identifier == node.node_id
    }
    return snapshot, records


def test_linked_stylesheet_starter_template_uses_full_block_width():
    css = (
        ".root { display: flex; flex-direction: column; gap: 16px; "
        "justify-content: center; align-items: center; height: 100vh; } "
        "p { background-color: red; }"
    )
    _, records = _prepared(
        '<><link rel="stylesheet" href="css/styles.css" />'
        '<div class="root">'
        '<h1>Get started</h1>'
        '<p>Edit src/App.tsx and save to test HMR</p>'
        '<button>Count is 0</button>'
        '</div></>',
        scope={"__velto_css_resource_resolver__": lambda _: css},
    )
    assert records["h1"][1]["align_self"] == "stretch"
    assert records["p"][1]["align_self"] == "stretch"
    assert "align_self" not in records["Button"][1]


def test_default_html_blocks_fill_column_parent_without_stretching_controls():
    _, records = _prepared(
        '<div style="display: flex; flex-direction: column; '
        'align-items: center; height: 100vh">'
        '<h1>Get started</h1>'
        '<p style="background-color: red">Edit src/App.tsx and save to test HMR</p>'
        '<button>Count is 0</button></div>'
    )
    for name in ("h1", "p"):
        component, style = records[name]
        assert component.component == "Flex"
        assert style["align_self"] == "stretch"
    assert "layout_width" not in records["Button"][1]


@pytest.mark.parametrize("width", [800, 320, 140])
def test_full_width_block_tracks_parent_viewport(width):
    snapshot, records = _prepared(
        '<div style="display: flex; flex-direction: column; '
        'align-items: center; height: 100vh">'
        '<p>Text wrapping at the actual block width</p>'
        '<button>Small control</button></div>',
        viewport=width,
    )
    measurements = []
    for node in snapshot.nodes:
        if node.component in ("Text", "Button"):
            intrinsic = IntrinsicSizes(60, 260, 18, 18, 260, 18) if node.component == "Text" else IntrinsicSizes(80, 80, 24, 24, 80, 24)
            measurements.append(MeasuredBox(
                node.node_id, intrinsic,
                LayoutConstraints(AvailableSize(None, False), AvailableSize(None, False)),
                snapshot.generation,
            ))
    from dataclasses import replace
    solved = dict(PythonLayoutEngine().compute(
        replace(snapshot, measurements=tuple(measurements))
    ).boxes)
    paragraph = records["p"][0]
    button = records["Button"][0]
    assert abs(solved[paragraph.node_id].content.width - width) <= 1 / 64
    if width > 80:
        assert solved[button.node_id].content.width < width


def test_authored_css_width_and_native_layout_width_are_not_overridden():
    _, records = _prepared(
        '<div style="display: flex; flex-direction: column; align-items: center">'
        '<p style="width: 120px">Fixed</p>'
        '<h1 layout_width="50%">Half width</h1></div>'
    )
    from psx.sfle.lengths import Length
    assert records["p"][1]["layout_width"] == Length.px(120)
    assert records["h1"][1]["layout_width"] == Length.percent(0.5)


def test_authored_align_self_preserves_user_choice():
    _, records = _prepared(
        '<div style="display: flex; flex-direction: column; align-items: center">'
        '<p style="align-self: center">Author controls alignment</p></div>'
    )
    assert records["p"][1]["align_self"] == "center"


def test_inline_display_and_row_flex_do_not_synthesize_block_width():
    _, records = _prepared(
        '<div style="display: flex; flex-direction: column">'
        '<p style="display: inline">Inline</p></div>'
    )
    assert "align_self" not in records["p"][1]
    _, records = _prepared(
        '<div style="display: flex; flex-direction: row">'
        '<p>Row participant</p></div>'
    )
    assert "layout_width" not in records["p"][1]
