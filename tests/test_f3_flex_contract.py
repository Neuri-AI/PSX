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
