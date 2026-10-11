"""F3-G1 RED: portable SFLE item metadata and adversarial normalization.

Every registered portable widget is a possible Flex child. Metadata must be
validated independently of native widget property names and toolkit imports.
"""
from __future__ import annotations

import pytest

from psx import (
    Badge, Button, Checkbox, Divider, Flex, Image, Input, Link, ProgressBar,
    Radio, RadioGroup, Scroll, Select, Slider, Spacer, SpinBox, Switch, Text,
    TextArea, component, psx,
)
from psx.core.errors import RendererCapabilityError
from psx.core.layout_tree import normalize_flex_tree
from psx.core.registry import builtin_component_registry
from psx.core.vnode import NodeKind, create_element
from psx.sfle.lengths import Length, LengthKind

# The registry is the source of truth: no portable component can be missed.
PORTABLE = {
    "Text": lambda **kw: Text("hello", **kw),
    "Button": lambda **kw: Button("run", **kw),
    "Input": lambda **kw: Input(**kw),
    "TextArea": lambda **kw: TextArea(**kw),
    "Checkbox": lambda **kw: Checkbox(**kw),
    "Slider": lambda **kw: Slider(**kw),
    "Spacer": lambda **kw: Spacer(**kw),
    "Divider": lambda **kw: Divider(**kw),
    "Image": lambda **kw: Image("picture.png", **kw),
    "ProgressBar": lambda **kw: ProgressBar(**kw),
    "Radio": lambda **kw: Radio("r", **kw),
    "RadioGroup": lambda **kw: RadioGroup(**kw),
    "Select": lambda **kw: Select(**kw),
    "Switch": lambda **kw: Switch(**kw),
    "Link": lambda **kw: Link(**kw),
    "Badge": lambda **kw: Badge(**kw),
    "SpinBox": lambda **kw: SpinBox(**kw),
    "Scroll": lambda **kw: Scroll(Flex(), **kw),
}


def test_registry_metadata_census_is_complete() -> None:
    names = set(builtin_component_registry().snapshot())
    assert names - {"Flex", "Row", "Column", "Fragment", "Box", "Native"} == set(PORTABLE)


@pytest.mark.parametrize("name", sorted(PORTABLE))
def test_every_existing_component_accepts_portable_item_metadata(name: str) -> None:
    node = PORTABLE[name](
        flex_grow=2, flex_shrink=0, flex_basis="40%",
        align_self="flex-end", order=-4, layout_width="60%",
        layout_height=32, layout_min_width="min-content",
        layout_max_height="none", layout_margin_left="auto",
        layout_margin_top="-2px", layout_padding_right=2,
        layout_border_bottom=1,
    )
    assert node.props["flex_grow"] == 2
    assert node.props["layout_width"] == "60%"
    assert node.props["layout_margin_left"] == "auto"
    assert normalize_flex_tree(Flex(node)).children[0].source is node


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "3"])
def test_invalid_flex_factors_fail_closed_on_native_control(value: object) -> None:
    with pytest.raises(RendererCapabilityError, match=r"Text.flex_grow"):
        Text("hello", flex_grow=value)


@pytest.mark.parametrize("property_name,value", [
    ("flex_basis", "calc(1px + 2px)"),
    ("flex_basis", True),
    ("layout_width", "10vw"),
    ("layout_width", -1),
    ("layout_min_width", "none"),
    ("layout_max_width", "auto"),
    ("layout_margin_left", "calc(5px + 2px)"),
    ("layout_padding_right", "auto"),
    ("layout_padding_left", -2),
    ("layout_border_top", "-2px"),
    ("align_self", "end"),
    ("order", True),
    ("order", 2 ** 32),
])
def test_adversarial_item_values_fail_closed(property_name: str, value: object) -> None:
    with pytest.raises(RendererCapabilityError, match=property_name):
        Button("Save", **{property_name: value})


def test_existing_native_image_width_is_not_layout_width() -> None:
    img = Image("logo.png", width=32, height=16, layout_width="50%",
                layout_height=24, flex_grow=1)
    assert img.props["width"] == 32
    assert img.props["height"] == 16
    assert img.props["layout_width"] == "50%"
    normalize_flex_tree(Flex(img))


def test_markup_matches_builder_with_item_metadata_and_preserves_ref() -> None:
    ref = object()
    built = Flex(Text("Header", ref=ref, flex_grow=1, layout_width="50%",
                      layout_margin_top="-2px", key="title"), key="root")
    # Plain PSX Markup should not require a separate user-supplied scope.
    marked = psx("""
        <Flex key="root">
            <Text key="title" flex_grow={1} layout_width="50%"
                  layout_margin_top="-2px">Header</Text>
        </Flex>
    """)
    assert marked.children[0].props["flex_grow"] == built.children[0].props["flex_grow"]
    assert marked.children[0].props["layout_width"] == built.children[0].props["layout_width"]
    assert normalize_flex_tree(marked).effective_children[0].source.key == "title"
    assert normalize_flex_tree(built).effective_children[0].source.props["ref"] is ref


def test_direct_host_declarations_cannot_bypass_item_validation() -> None:
    raw = create_element("Text", value="A", layout_width=True)
    with pytest.raises(RendererCapabilityError, match="layout_width"):
        normalize_flex_tree(Flex(raw))


def test_native_node_layout_metadata_is_validated_without_widget_import() -> None:
    from psx.core.native import NativeWidget
    from psx.core.vnode import native_widget

    decl = NativeWidget(renderer="tkinter", factory=lambda: object())
    ok = native_widget(decl, flex_grow=1, layout_width="80%")
    assert normalize_flex_tree(Flex(ok)).children[0].source is ok
    bad = native_widget(decl, flex_grow=float("nan"))
    with pytest.raises(RendererCapabilityError, match="flex_grow"):
        normalize_flex_tree(Flex(bad))


@pytest.mark.parametrize("raw_key", [True, False])
def test_boolean_keys_are_never_valid_node_identity(raw_key: bool) -> None:
    with pytest.raises((TypeError, RendererCapabilityError)):
        create_element("Flex", key=raw_key)


def test_unresolved_markup_tags_report_source_location() -> None:
    from psx.core.errors import MarkupSyntaxError

    with pytest.raises(MarkupSyntaxError, match=r"sample.psx:2:"):
        psx("<Flex>\n  <Unknown />\n</Flex>", filename="sample.psx")


def test_scroll_component_root_must_resolve_to_one_flex() -> None:
    @component
    def Content():
        return Flex()

    child = Content(key="content")
    root = Scroll(child)
    assert normalize_flex_tree(root, component_roots={id(child): Flex()}).scroll_content_root is not None
    with pytest.raises(RendererCapabilityError, match="Scroll.*Flex"):
        normalize_flex_tree(root, component_roots={id(child): Text("bad")})


def test_cyclic_component_resolution_is_rejected() -> None:
    @component
    def Cyclic():
        return Text("bad")

    child = Cyclic()
    outer = Flex(child)
    with pytest.raises(RendererCapabilityError, match="Cyclic"):
        normalize_flex_tree(outer, component_roots={id(child): outer})


def test_native_layout_properties_cannot_replace_natively_owned_dimensions() -> None:
    img = Image("logo.png", width=50, layout_width="80px")
    assert img.props["width"] == 50
    assert img.props["layout_width"] == "80px"


@pytest.mark.parametrize("props", [
    {"width": 20, "layout_width": 30},
    {"height": 20, "layout_height": 30},
    {"min_width": "5px", "layout_min_width": "7px"},
    {"max_height": "8px", "layout_max_height": "12px"},
])
def test_flex_rejects_conflicting_layout_dimensions(props: dict[str, object]) -> None:
    with pytest.raises(RendererCapabilityError, match="Conflicting Flex"):
        Flex(**props)


def test_fragments_and_keys_remain_unmodified_for_reorder_and_disposal() -> None:
    from psx import Fragment

    root = Flex(Fragment(Text("a", key="a"), key="fragment"),
                Button("click", key="action"), key="root")
    original = root.children[0]
    normalized = normalize_flex_tree(root)
    assert normalized.children[0].source is original
    assert normalized.effective_children[0].source.key == "a"
    assert normalized.effective_children[1].source.key == "action"


def test_item_lengths_accept_typed_sfle_values() -> None:
    node = Text("A", layout_width=Length(LengthKind.PERCENT, 0.5))
    assert node.props["layout_width"].kind is LengthKind.PERCENT
