"""CSS block children of column Flex retain inline native button flow."""

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.css.markup import compute_markup_styles
from psx.sfle.lengths import LengthKind
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot


MARKUP = """
<div class="sidebar">
    <div class="navigation">
        <button>Inicio</button>
        <button>Configuración</button>
    </div>
    <div class="sidebar-footer">
        <p>Mi perfil</p>
    </div>
</div>
"""


def snapshot(css: str):
    vnode = compute_markup_styles(psx(MARKUP), css)
    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(vnode),
        LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True)),
        generation=1,
    )
    return prepared.css_geometry_snapshot()


def parts(css: str):
    nodes = snapshot(css).nodes
    root = nodes[0]
    nav = next(node for node in nodes if node.parent_id == root.node_id)
    footer = next(
        node for node in nodes
        if node.parent_id == root.node_id and node.node_id != nav.node_id
    )
    buttons = [node for node in nodes if node.parent_id == nav.node_id]
    return root, nav, footer, buttons


def test_browser_like_inline_buttons_in_column_flex_sidebar():
    root, nav, footer, buttons = parts("""
        .sidebar {
            display: flex;
            flex-direction: column;
            height: 100vh;
            background: red;
        }
        .sidebar-footer { margin-top: auto; }
    """)
    assert root.component == "Flex"
    assert dict(root.style)["direction"] == "column"
    assert nav.component == "Flex"
    assert dict(nav.style)["direction"] == "row"
    assert dict(nav.style)["wrap"] == "wrap"
    assert dict(nav.style)["align_items"] == "flex-start"
    assert len(buttons) == 2
    assert all(button.component == "Button" for button in buttons)
    assert footer.component == "Flex"
    assert dict(footer.style)["direction"] == "column"
    assert dict(footer.style)["layout_margin_top"].kind is LengthKind.AUTO


def test_explicit_nested_flex_direction_is_not_overwritten():
    root, nav, footer, buttons = parts("""
        .sidebar { display:flex; flex-direction:column; height:100vh; }
        .navigation { display:flex; flex-direction:row; gap:10px; }
    """)
    assert nav.component == "Flex"
    assert dict(nav.style)["direction"] == "row"
    assert "wrap" not in dict(nav.style)
    assert len(buttons) == 2


def test_mixed_block_content_is_not_rewritten_as_an_inline_run():
    root, nav, _, buttons = parts("""
        .sidebar { display:flex; flex-direction:column; height:100vh; }
        button { display:block; }
    """)
    assert dict(nav.style)["direction"] == "column"
    assert len(buttons) == 2



def test_single_button_in_block_keeps_inline_sizing_mode():
    document = compute_markup_styles(psx("""
        <div class="sidebar">
            <div class="navigation"><button>Inicio</button></div>
            <div class="sidebar-footer"><p>Mi perfil</p></div>
        </div>
    """), """
        .sidebar { display:flex; flex-direction:column; height:100vh; }
        .sidebar-footer { margin-top:auto; }
    """)
    prepared = prepare_native_layout_snapshot(
        normalize_flex_tree(document),
        LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True)),
        generation=1,
    )
    nodes = prepared.css_geometry_snapshot().nodes
    root = nodes[0]
    nav = next(node for node in nodes if node.parent_id == root.node_id)
    assert nav.component == "Flex"
    assert dict(nav.style)["direction"] == "row"
