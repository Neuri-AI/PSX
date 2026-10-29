"""Native structural projection caching preserves exact CSS, identity and geometry.

The cache is strictly a pure UI-thread preparation optimization. No solved
rectangles, native measurements or displayed pixels are stored.
"""
from dataclasses import replace
from types import SimpleNamespace

from psx import psx
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
from psx.sfle.native_structural_snapshot_reuse import (
    NativeStructuralSnapshotReuse, mounted_structural_token,
)


def constraints(width, height=650):
    return LayoutConstraints(
        AvailableSize(width, True), AvailableSize(height, True),
    )


def stamp_tree(vnode):
    def mounted(node):
        return SimpleNamespace(
            node=node, handle=object(),
            children=tuple(mounted(child) for child in node.children),
        )
    top = mounted(vnode)
    stamps = []
    def visit(instance):
        stamps.append(mounted_structural_token(instance))
        for child in instance.children:
            visit(child)
    visit(top)
    return stamps


def fresh(root, width, generation):
    normalized = normalize_flex_tree(root)
    return prepare_native_layout_snapshot(
        normalized, constraints(width), generation=generation,
    ).css_geometry_snapshot()


def test_resize_reuses_immutable_structure_but_rebinds_generation_and_width():
    root = psx(
        '<div style="padding:12px">'
        '<span style="margin-left: 5px">One</span>'
        '<button>Click</button>'
        '</div>'
    )
    stamp = stamp_tree(root)
    reuse = NativeStructuralSnapshotReuse()
    original_normalized, first = reuse.prepare(
        root, {}, stamp, constraints(480), 1, 0,
    )
    initial_snapshot = first.snapshot
    assert reuse.builds == 1 and reuse.hits == 0
    for revision, width in enumerate((560, 700, 640, 480), 2):
        normalized, prepared = reuse.prepare(
            root, {}, stamp, constraints(width), revision, 0,
        )
        assert normalized is original_normalized
        assert prepared.snapshot.nodes is initial_snapshot.nodes
        assert prepared.snapshot.constraints == constraints(width)
        assert prepared.snapshot.generation == revision
        assert prepared.css_geometry_snapshot() == fresh(root, width, revision)
    assert reuse.builds == 1 and reuse.hits == 4


def test_reactive_css_and_reconciled_subtree_invalidate_blueprint():
    root = psx('<div><span>One</span></div>')
    altered = psx('<div><span>Two</span></div>')
    reuse = NativeStructuralSnapshotReuse()
    before, _ = reuse.prepare(
        root, {}, stamp_tree(root), constraints(480), 1, 0,
    )
    changed, prepared = reuse.prepare(
        altered, {}, stamp_tree(altered), constraints(480), 2, 0,
    )
    assert changed is not before
    assert prepared.css_geometry_snapshot() == fresh(altered, 480, 2)
    same_tree_after_epoch, _ = reuse.prepare(
        altered, {}, stamp_tree(altered), constraints(480), 3, 1,
    )
    assert same_tree_after_epoch is not changed
    reuse.clear()
    another, _ = reuse.prepare(
        altered, {}, stamp_tree(altered), constraints(480), 4, 1,
    )
    assert another is not same_tree_after_epoch


def test_mount_identity_and_child_order_invalidate_even_with_same_vnodes():
    root = psx('<div><span>One</span><span>Two</span></div>')
    cache = NativeStructuralSnapshotReuse()
    ordered_stamp = stamp_tree(root)
    first, _ = cache.prepare(root, {}, ordered_stamp, constraints(480), 1, 0)
    replacement_stamp = list(ordered_stamp)
    original = replacement_stamp[1]
    replacement_stamp[1] = (original[0] + 1,) + original[1:]
    second, _ = cache.prepare(root, {}, replacement_stamp, constraints(480), 2, 0)
    assert second is not first


def test_viewport_css_resolved_fresh_on_every_resize():
    root = psx('<div style="padding-left:10vw"><span>Hello</span></div>')
    stamp = stamp_tree(root)
    cache = NativeStructuralSnapshotReuse()
    widths = (480, 720, 600)
    for i, width in enumerate(widths, 1):
        _, prepared = cache.prepare(root, {}, stamp, constraints(width), i, 0)
        assert prepared.css_geometry_snapshot() == fresh(root, width, i)
