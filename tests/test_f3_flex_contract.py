"""F3-G1 incremental: Flex declarations, properties and registry."""
import pytest

from psx import Flex, Text
from psx.core.contracts import FLEX_CONTRACT
from psx.core.errors import RendererCapabilityError
from psx.core.registry import builtin_component_registry
from psx.core.vnode import NodeKind


def test_flex_registry_and_host_identity() -> None:
    entry = builtin_component_registry().resolve("Flex")
    assert entry.constructor is Flex
    assert entry.contract is FLEX_CONTRACT
    tree = Flex(Text("A", key="a"), Text("B", key="b"),
                direction="column", gap="12px", key="root")
    assert tree.kind is NodeKind.HOST
    assert tree.type == "Flex"
    assert tree.key == "root"
    assert [node.key for node in tree.children] == ["a", "b"]
    assert tree.props["direction"] == "column"
    assert tree.props["gap"] == "12px"


def test_flex_default_props() -> None:
    tree = Flex(Text("Hello"))
    assert tree.props["direction"] == "row"
    assert tree.props["wrap"] == "nowrap"
    assert tree.props["gap"] == 0


@pytest.mark.parametrize("props", [
    {"direction": "invalid"}, {"wrap": "invalid"},
    {"justify_content": "invalid"}, {"align_items": "end"},
    {"align_self": "invalid"}, {"gap": -1},
    {"gap": "calc(2px+3px)"}, {"row_gap": -1},
    {"width": True}, {"width": "12vw"},
    {"flex_grow": -1}, {"flex_shrink": float("nan")},
    {"order": 2 ** 40}, {"order": True},
    {"padding": (1, 2, 3)}, {"padding": -4},
    {"unknown_flex_property": 1},
])
def test_invalid_flex_properties_fail_closed(props: dict) -> None:
    with pytest.raises(RendererCapabilityError):
        Flex(**props)


def test_valid_item_metadata_is_preserved_for_normalization() -> None:
    tree = Flex(direction="row-reverse", wrap="wrap", gap=8,
                flex_grow=2, order=-1, layout_width="50%",
                align_self="center")
    assert tree.props["layout_width"] == "50%"
    assert tree.props["flex_grow"] == 2
    assert tree.props["order"] == -1


def test_flex_contract_has_multiple_children_and_no_new_events() -> None:
    assert FLEX_CONTRACT.child_policy == "multiple"
    assert FLEX_CONTRACT.events == frozenset()


# F3-G1.2 RED: Markup parity, transparent boundaries and Scroll content authority.

def test_markup_and_builder_flex_are_semantically_identical() -> None:
    from psx import Button, psx

    markup = psx("""
        <Flex direction="column" gap={8} width="640px" key="root">
            <Text key="label">Hello</Text>
            <Flex direction="row" gap={12} key="actions">
                <Button label="Save" key="save" />
            </Flex>
        </Flex>
    """)
    builder = Flex(
        Text("Hello", key="label"),
        Flex(Button("Save", key="save"), direction="row", gap=12, key="actions"),
        direction="column", gap=8, width="640px", key="root",
    )
    assert markup == builder
    from psx.core.layout_tree import normalize_flex_tree
    a, b = normalize_flex_tree(markup), normalize_flex_tree(builder)
    assert a.path == b.path
    assert tuple(c.path for c in a.children) == tuple(c.path for c in b.children)


def test_layout_tree_flattens_fragments_without_creating_visible_boxes() -> None:
    from psx import Fragment
    from psx.core.layout_tree import normalize_flex_tree

    tree = Flex(Fragment(Text("A", key="a"), Text("B", key="b")),
                Flex(Text("C"), key="nested"))
    normalized = normalize_flex_tree(tree)
    assert normalized.source is tree
    assert normalized.children[0].kind is NodeKind.FRAGMENT
    assert [part.type for part in normalized.effective_children] == [
        "Text", "Text", "Flex",
    ]
    assert normalized.children[0].source is tree.children[0]
    assert normalized.effective_children[0].source.props["value"] == "A"


def test_layout_tree_keyed_paths_do_not_change_when_siblings_reorder() -> None:
    from psx.core.layout_tree import normalize_flex_tree

    before = normalize_flex_tree(Flex(Text("A", key="a"), Text("B", key="b")))
    after = normalize_flex_tree(Flex(Text("B", key="b"), Text("A", key="a")))
    assert {n.source.key: n.path for n in before.children} == {
        n.source.key: n.path for n in after.children
    }


def test_layout_tree_preserves_function_component_boundary_without_rendering_it() -> None:
    from psx import component
    from psx.core.layout_tree import normalize_flex_tree

    def should_not_render():
        raise AssertionError("Never evaluate hooks/components in the normalizer")

    Card = component(should_not_render)
    child = Card(key="card")
    rendered = Flex(Text("Card", key="label"), key="content")
    root = Flex(child, key="outer")
    normalized = normalize_flex_tree(root, component_roots={id(child): rendered})
    boundary = normalized.children[0]
    assert boundary.kind is NodeKind.COMPONENT
    assert boundary.source is child
    assert boundary.children[0].source is rendered
    assert normalized.effective_children[0].source is rendered


def test_layout_tree_rejects_unresolved_component_instead_of_guessing_geometry() -> None:
    from psx import component
    from psx.core.layout_tree import normalize_flex_tree

    @component
    def Card():
        return Text("card")

    with pytest.raises(RendererCapabilityError, match="resolved"):
        normalize_flex_tree(Flex(Card()))


def test_scroll_has_one_explicit_flex_content_root() -> None:
    from psx import Scroll, Fragment
    from psx.core.layout_tree import normalize_flex_tree

    inner = Scroll(Flex(Text("Inside"), key="inner-content"), key="inner-scroll")
    outer_content = Flex(inner, key="outer-content")
    outer = Scroll(Fragment(outer_content), key="outer-scroll")
    normalized = normalize_flex_tree(outer)
    assert normalized.scroll_content_root is not None
    assert normalized.scroll_content_root.source is outer_content
    inner_normalized = normalized.scroll_content_root.children[0]
    assert inner_normalized.scroll_content_root is not None
    assert inner_normalized.scroll_content_root.source is inner.children[0]
    assert normalized.scroll_content_root.path != inner_normalized.scroll_content_root.path


@pytest.mark.parametrize("children", [
    (),
    (Text("No Flex"),),
    (Flex(), Flex()),
    (Text("A"), Flex()),
])
def test_scroll_ambiguous_or_nonflex_content_is_rejected(children) -> None:
    from psx import Scroll
    from psx.core.layout_tree import normalize_flex_tree

    with pytest.raises(RendererCapabilityError, match="Scroll.*Flex"):
        normalize_flex_tree(Scroll(*children))


def test_scroll_rejects_multiple_flex_roots_even_behind_fragment() -> None:
    from psx import Scroll, Fragment
    from psx.core.layout_tree import normalize_flex_tree

    with pytest.raises(RendererCapabilityError, match="Scroll.*Flex"):
        normalize_flex_tree(Scroll(Fragment(Flex(), Flex())))


def test_layout_tree_rejects_duplicate_keyed_siblings() -> None:
    from psx.core.errors import DuplicateKeyError
    from psx.core.layout_tree import normalize_flex_tree

    with pytest.raises(DuplicateKeyError):
        normalize_flex_tree(Flex(Text("A", key="same"), Text("B", key="same")))
