"""Native SFLE RED/GREEN: canonical PSX tree -> immutable SFLE v1 snapshot."""
from __future__ import annotations

from dataclasses import replace

import pytest

from psx import Button, Flex, Fragment, Image, Scroll, Text, component, psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLECapabilityError
from psx.sfle.native_layout_snapshot import path_identity, prepare_native_layout_snapshot
from psx.sfle.lengths import Length
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox


def _constraints(width=160, height=90):
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))


def _prepare(tree, *, generation=17, measurements=(), **options):
    return prepare_native_layout_snapshot(
        normalize_flex_tree(tree), _constraints(), generation=generation,
        measurements=measurements, **options,
    )


def test_real_sfle_solver_consumes_markup_without_native_layout() -> None:
    markup = psx("""
        <Flex direction="row" width="120px" height="40px" gap="8">
            <Flex width="40px" height="10px" flex_basis="40px" flex_shrink="0" />
            <Flex width="30px" height="10px" flex_basis="30px" flex_shrink="0" />
        </Flex>
    """)
    prepared = _prepare(markup)
    snapshot = prepared.snapshot
    assert snapshot.schema_version == 1
    assert len(snapshot.nodes) == 3
    assert [node.component for node in snapshot.nodes] == ["Flex", "Flex", "Flex"]
    result = PythonLayoutEngine().compute(snapshot)
    boxes = dict(result.boxes)
    left, right = snapshot.nodes[1].node_id, snapshot.nodes[2].node_id
    assert boxes[left].border.width == 40
    assert boxes[right].border.x - boxes[left].border.x == 48
    assert result.generation == 17


def test_builder_markup_styles_and_identity_are_identical() -> None:
    markup = psx("""
        <Flex direction="column" gap="8px" padding="12" key="root">
            <Text key="header" flex_grow="1" layout_width="50%"
                  layout_margin_top="-2px">Welcome</Text>
            <Button key="save" label="Save" />
        </Flex>
    """)
    builder = Flex(
        Text("Welcome", key="header", flex_grow=1, layout_width="50%",
             layout_margin_top="-2px"),
        Button("Save", key="save"), direction="column", gap="8px", padding=12, key="root",
    )
    a = _prepare(markup).snapshot
    b = _prepare(builder).snapshot
    assert a.nodes == b.nodes
    assert dict(a.nodes[1].style)["layout_margin_top"] == "-2px"
    assert dict(a.nodes[0].style)["layout_padding_right"] == 12


def test_css_gap_shorthand_and_explicit_axis_override() -> None:
    snap = _prepare(Flex(Flex(), gap=16, row_gap=3)).snapshot
    style = dict(snap.nodes[0].style)
    assert style["row_gap"] == 3
    assert style["column_gap"] == 16
    assert "gap" not in style


@pytest.mark.parametrize("padding,expected", [
    (4, (4, 4, 4, 4)),
    ((2, 6), (2, 6, 2, 6)),
    ((1, 2, 3, 4), (1, 2, 3, 4)),
])
def test_padding_expansion_exact(padding, expected) -> None:
    node = _prepare(Flex(padding=padding)).snapshot.nodes[0]
    style = dict(node.style)
    assert tuple(style[f"layout_padding_{side}"] for side in (
        "top", "right", "bottom", "left",
    )) == expected


def test_native_image_dimensions_are_not_leaked_into_sfle_item_style() -> None:
    prepared = _prepare(Flex(Image("photo.png", width=80, height=30,
                                   layout_width=Length.px(20),
                                   layout_height="40px", flex_shrink=0)))
    node = prepared.snapshot.nodes[1]
    style = dict(node.style)
    assert node.component == "Image"
    assert "width" not in style and "height" not in style
    assert style["layout_width"] == Length.px(20)
    assert style["layout_height"] == "40px"
    assert prepared.identities[1][1].props["width"] == 80


def test_nested_fragments_are_transparent_and_keyed_nodes_stable_on_reorder() -> None:
    first = Flex(Fragment(Text("A", key="a"), Text("B", key="b")),
                 Flex(key="sub"), key="root")
    second = Flex(Fragment(Text("B", key="b"), Text("A", key="a")),
                  Flex(key="sub"), key="root")
    old = _prepare(first).snapshot
    new = _prepare(second).snapshot
    assert len(old.nodes) == len(new.nodes) == 4
    assert [node.component for node in old.nodes] == ["Flex", "Text", "Text", "Flex"]
    assert set(node.node_id for node in old.nodes) == set(node.node_id for node in new.nodes)
    assert all(node.parent_id == old.nodes[0].node_id for node in old.nodes[1:])


def test_resolved_function_components_do_not_insert_phantom_layout_boxes() -> None:
    @component
    def Card():
        return Flex(Text("hi"), key="inner")

    vnode = Card(key="card")
    tree = Flex(vnode)
    normalized = normalize_flex_tree(tree, component_roots={id(vnode): Flex(Text("hi"), key="inner")})
    prepared = prepare_native_layout_snapshot(normalized, _constraints(), generation=3)
    assert [node.component for node in prepared.snapshot.nodes] == ["Flex", "Flex", "Text"]
    assert all(node.component != "Fragment" for node in prepared.snapshot.nodes)


def test_scroll_is_structural_only_with_explicit_flex_root() -> None:
    prepared = _prepare(Flex(Scroll(Flex())))
    assert [n.component for n in prepared.snapshot.nodes] == ["Flex", "Flex", "Flex"]
    # The Scroll host is retained as its own stable native identity.
    assert [vnode.type for _, vnode in prepared.identities] == [
        "Flex", "Scroll", "Flex",
    ]


def test_no_implicit_flex_root_is_created_for_nonflex_tree() -> None:
    with pytest.raises(SFLECapabilityError, match="explicit Flex"):
        _prepare(Text("plain"))
    with pytest.raises(SFLECapabilityError, match="explicit Flex"):
        _prepare(Fragment(Flex(), Flex()))


def test_missing_intrinsic_measurement_is_not_conjured_from_available_size() -> None:
    prepared = _prepare(Flex(Text("A very long text")))
    assert prepared.snapshot.measurements == ()
    # F2 owns any unsupported intrinsic sizing diagnostic, G2 doesn't guess.


def test_supplied_measurement_retains_identity_revision_and_constraints() -> None:
    prepared = _prepare(Flex(Text("hello")))
    node_id = prepared.snapshot.nodes[1].node_id
    metrics = IntrinsicSizes(10, 20, 10, 10, 20, 10)
    measure = MeasuredBox(node_id, metrics, _constraints(), 5)
    updated = _prepare(Flex(Text("hello")), measurements=(measure,))
    assert updated.snapshot.measurements == (measure,)
    assert updated.snapshot.nodes[1].node_id == node_id


def test_foreign_measurement_is_rejected_not_silently_dropped() -> None:
    metrics = IntrinsicSizes(2, 2, 2, 2, 2, 2)
    measure = MeasuredBox("foreign", metrics, _constraints(), 0)
    with pytest.raises(ValueError, match="Measurements must refer"):
        _prepare(Flex(), measurements=(measure,))


def test_stable_id_is_key_aware_and_does_not_depend_on_python_object_id() -> None:
    assert path_identity((("root", 0), ("key", "a"))) == path_identity((("root", 0), ("key", "a")))
    assert path_identity((("root", 0), ("key", "b"))) != path_identity((("root", 0), ("key", "a")))
    with pytest.raises(ValueError, match="layout path"):
        path_identity(())


def test_generator_measurements_consumed_once() -> None:
    initial = _prepare(Flex(Text("hello")))
    child = initial.snapshot.nodes[1].node_id
    metrics = IntrinsicSizes(1, 1, 1, 1, 1, 1)
    measurements = (m for m in (MeasuredBox(child, metrics, _constraints(), 0),))
    prepared = _prepare(Flex(Text("hello")), measurements=measurements)
    assert len(prepared.snapshot.measurements) == 1


def test_layout_direction_and_generation_are_not_overwritten() -> None:
    from psx.sfle.model import WritingDirection
    prepared = _prepare(Flex(), generation=91, direction=WritingDirection.RTL)
    assert prepared.snapshot.generation == 91
    assert prepared.snapshot.direction is WritingDirection.RTL



def test_prepared_boxes_preserve_identity_and_unresolved_lengths() -> None:
    prepared = _prepare(Flex(
        Image("photo.png", width=80, height=30, layout_width="25%",
              layout_margin_top="-4px", layout_padding_left="10px",
              layout_border_right="2px"),
    ))
    assert tuple(identifier for identifier, _ in prepared.box_styles) == tuple(
        node.node_id for node in prepared.snapshot.nodes
    )
    image_id, image_box = prepared.box_styles[1]
    assert image_id == prepared.snapshot.nodes[1].node_id
    assert image_box.dimension("layout_width") == Length.percent(0.25)
    assert image_box.margin.top == Length.px(-4)
    assert image_box.padding.left == Length.px(10)
    assert image_box.border.right == Length.px(2)
    assert dict(prepared.snapshot.nodes[1].style)["layout_width"] == "25%"
    assert prepared.identities[1][1].props["width"] == 80


def test_builder_and_markup_have_equal_typed_box_styles() -> None:
    markup = psx("""
        <Flex direction="column">
            <Text layout_width="50%" layout_padding_top="8px">hello</Text>
        </Flex>
    """)
    builder = Flex(Text("hello", layout_width="50%", layout_padding_top="8px"),
                   direction="column")
    assert _prepare(markup).box_styles == _prepare(builder).box_styles


def test_native_snapshot_rejects_invalid_box_metadata_before_engine_dispatch() -> None:
    from psx.core.errors import RendererCapabilityError
    from psx.core.vnode import VNode

    # A hand-built host node can bypass the builder validator; the snapshot
    # boundary must still reject an invalid length before engine dispatch.
    valid = Flex(Text("hello"))
    child = valid.children[0]
    from dataclasses import replace as immutable_replace
    malformed = immutable_replace(child, props={**child.props, "layout_padding_left": "-2px"})
    malformed_root = immutable_replace(valid, children=(malformed,))
    with pytest.raises(RendererCapabilityError, match="layout_padding_left"):
        _prepare(malformed_root)


def test_canonical_snapshot_uses_typed_lengths_without_mutating_original() -> None:
    prepared = _prepare(Flex(
        Flex(layout_width="40px", layout_padding_left="6px",
             layout_border_right="2px", layout_margin_top="-3px",
             height="10px", flex_basis="40px", flex_shrink=0),
        width="120px", height="40px",
    ))
    original = prepared.snapshot
    typed = prepared.canonical_snapshot()
    assert typed is not original
    assert typed.generation == original.generation
    assert typed.measurements == original.measurements
    assert typed.nodes[0] == original.nodes[0]
    legacy_style = dict(original.nodes[1].style)
    typed_style = dict(typed.nodes[1].style)
    assert legacy_style["layout_width"] == "40px"
    assert typed_style["layout_width"] == Length.px(40)
    assert typed_style["layout_padding_left"] == Length.px(6)
    assert typed_style["layout_border_right"] == Length.px(2)
    assert typed_style["layout_margin_top"] == Length.px(-3)
    assert typed_style["flex_basis"] == "40px"
    assert PythonLayoutEngine().compute(typed).boxes == PythonLayoutEngine().compute(original).boxes


def test_canonical_snapshot_preserves_flex_container_padding_shorthand() -> None:
    prepared = _prepare(Flex(Flex(), padding=(4, 8)))
    original = prepared.snapshot
    canonical = prepared.canonical_snapshot()
    assert canonical.nodes[0].style == original.nodes[0].style
    assert dict(canonical.nodes[0].style)["layout_padding_left"] == 8
