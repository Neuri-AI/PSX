from __future__ import annotations

import pytest

from psx import Column, Row, Spacer, Text, psx
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_spacer_has_no_portable_props() -> None:
    Spacer()
    Spacer(key="gap")
    with pytest.raises(RendererCapabilityError):
        Spacer(size=20)  # type: ignore[call-arg]


def test_spacer_is_a_builtin_markup_tag() -> None:
    node = psx("<Row><Text>A</Text><Spacer /><Text>B</Text></Row>")
    assert node.children[1].type == "Spacer"


def test_spacer_mounts_and_unmounts_cleanly() -> None:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Row(Text("A"), Spacer(), Text("B")))
    assert [h.type for h in root.handle.children] == ["Text", "Spacer", "Text"]
    reconciler.unmount()
    assert all(h.destroyed for h in root.handle.children)


def test_spacer_keeps_identity_across_keyed_reorder() -> None:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    reconciler.render(Row(Text("A", key="a"), Spacer(key="s"), Text("B", key="b")))
    spacer = reconciler.root.handle.children[1]
    reconciler.render(Row(Text("A", key="a"), Text("B", key="b"), Spacer(key="s")))
    assert reconciler.root.handle.children[2] is spacer