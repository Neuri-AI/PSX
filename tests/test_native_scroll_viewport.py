"""Pure G2 native Scroll viewport contract: backend-independent geometry."""
import pytest

from psx import Flex, Scroll, Text
from psx.core.errors import RendererCapabilityError
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.native_scroll_viewport import (
    bind_scroll_viewport, require_scroll_content_root,
)
from psx.sfle.model import Rect


def test_scroll_explicit_flex_root_and_engine_rectangles_are_preserved():
    root = normalize_flex_tree(Flex(
        Scroll(Flex(Text("hello"), width="300px", height="500px"),
               direction="vertical", width=120, height=80),
        width="500px", height="600px",
    ))
    scroll = root.children[0]
    assert require_scroll_content_root(scroll).type == "Flex"
    viewport = Rect(12, 8, 120, 80)
    content = Rect(0, 0, 300, 500)
    binding = bind_scroll_viewport(scroll, viewport, content)
    assert binding.viewport is viewport
    assert binding.content is content
    assert binding.overflow_x == 180
    assert binding.overflow_y == 420
    assert binding.clip_y
    assert not binding.clip_x


@pytest.mark.parametrize("direction,clip", [
    ("horizontal", (True, False)),
    ("vertical", (False, True)),
    ("both", (True, True)),
])
def test_scroll_direction_never_changes_engine_geometry(direction, clip):
    root = normalize_flex_tree(Flex(
        Scroll(Flex(Text("x")), direction=direction),
        width="100px", height="100px",
    ))
    binding = bind_scroll_viewport(
        root.children[0], Rect(0, 0, 40, 50), Rect(0, 0, 90, 100),
    )
    assert (binding.clip_x, binding.clip_y) == clip


def test_scroll_disabled_does_not_claim_active_scroll_axis():
    root = normalize_flex_tree(Flex(
        Scroll(Flex(Text("x")), direction="both", enabled=False),
        width="100px", height="100px",
    ))
    binding = bind_scroll_viewport(
        root.children[0], Rect(0, 0, 40, 50), Rect(0, 0, 90, 100),
    )
    assert not binding.clip_x
    assert not binding.clip_y


@pytest.mark.parametrize("children", [(), (Text("not flex"),), (Flex(), Flex())])
def test_scroll_missing_or_invalid_content_fails_closed(children):
    with pytest.raises(RendererCapabilityError, match="exactly one Flex or HTML-like block root"):
        normalize_flex_tree(Flex(
            Scroll(*children), width="100px", height="100px",
        ))


def test_scroll_accepts_explicit_html_like_block_content():
    from psx.core.vnode import create_element
    content = create_element("div")
    tree = normalize_flex_tree(Flex(Scroll(content, height="100vh")))
    assert require_scroll_content_root(tree.children[0]).type == "div"
