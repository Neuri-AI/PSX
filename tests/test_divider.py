from __future__ import annotations

import pytest

from psx import Column, Divider, Text, psx
from psx.core.errors import InvalidChildError, RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_divider_accepts_no_children_or_one_child_only() -> None:
    Divider()
    Divider("Sección")
    Divider(Text("Sección"))
    with pytest.raises(InvalidChildError):
        Divider(Text("A"), Text("B"))


def test_divider_defaults_and_validation() -> None:
    node = Divider()
    assert node.props["orientation"] == "horizontal"
    assert node.props["thickness"] == 1
    assert node.props["color"] is None
    with pytest.raises(RendererCapabilityError):
        Divider(orientation="diagonal")
    with pytest.raises(RendererCapabilityError):
        Divider(thickness=0)
    with pytest.raises(RendererCapabilityError):
        Divider(color="red")


def test_divider_is_a_builtin_markup_tag_with_optional_child() -> None:
    assert psx("<Divider />").type == "Divider"
    with_child = psx("<Divider>Sección</Divider>")
    assert with_child.type == "Divider"
    assert len(with_child.children) == 1
    assert with_child.children[0].type == "Text"


def test_divider_markup_rejects_multiple_children() -> None:
    from psx.core.errors import MarkupSyntaxError
    with pytest.raises(MarkupSyntaxError, match="at most one child"):
        psx("<Divider><Text>A</Text><Text>B</Text></Divider>")


def test_divider_mounts_updates_and_unmounts() -> None:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(
        Column(Divider(key="d"), Divider("Etiqueta", key="d2"))
    )
    column_handle = root.handle
    assert [h.type for h in column_handle.children] == ["Divider", "Divider"]
    second_divider = column_handle.children[1]
    assert len(second_divider.children) == 1
    assert second_divider.children[0].type == "Text"

    first_handle = column_handle.children[0]
    reconciler.render(
        Column(
            Divider(thickness=2, color="#336699", key="d"),
            Divider("Otra", key="d2"),
        )
    )
    assert column_handle.children[0] is first_handle
    assert first_handle.props["thickness"] == 2
    assert first_handle.props["color"] == "#336699"

    reconciler.unmount()
    assert all(h.destroyed for h in column_handle.children)