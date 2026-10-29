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
    assert reuse.project_css(first) == fresh(root, 480, 1)
    assert reuse.builds == 1 and reuse.hits == 0
    for revision, width in enumerate((560, 700, 640, 480), 2):
        normalized, prepared = reuse.prepare(
            root, {}, stamp, constraints(width), revision, 0,
        )
        assert normalized is original_normalized
        assert prepared.snapshot.nodes is initial_snapshot.nodes
        assert prepared.snapshot.constraints == constraints(width)
        assert prepared.snapshot.generation == revision
        assert reuse.project_css(prepared) == fresh(root, width, revision)
    assert reuse.builds == 1 and reuse.hits == 4
    assert reuse.projections == 1 and reuse.projection_hits == 4


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
        assert cache.project_css(prepared) == fresh(root, width, i)
    assert cache.projections == 3 and cache.projection_hits == 0


def test_css_auto_height_and_viewport_height_are_not_conflated():
    root = psx(
        '<div style="display:flex; flex-direction:column; padding:10px">'
        '<span>Responsive child</span>'
        '</div>'
    )
    cache = NativeStructuralSnapshotReuse()
    stamp = stamp_tree(root)
    for generation, (width, height) in enumerate(
        ((360, 600), (480, 850), (320, 450)), 1
    ):
        dims = constraints(width, height)
        _, prepared = cache.prepare(root, {}, stamp, dims, generation, 0)
        projected = cache.project_css(prepared)
        expected = prepare_native_layout_snapshot(
            normalize_flex_tree(root), dims, generation=generation,
        ).css_geometry_snapshot()
        assert projected == expected
    assert cache.projections == 1 and cache.projection_hits == 2


def test_css_snapshot_cache_drops_on_semantic_epoch_change():
    root = psx('<div><span>Hello</span></div>')
    cache = NativeStructuralSnapshotReuse()
    stamp = stamp_tree(root)
    for epoch in (0, 0, 1, 1):
        _, prepared = cache.prepare(root, {}, stamp, constraints(450), epoch + 1, epoch)
        assert cache.project_css(prepared) == fresh(root, 450, epoch + 1)
    assert cache.builds == 2
    assert cache.projections == 2
    assert cache.projection_hits == 2


def test_direct_grid_root_normalization_reused_without_fabricating_css_layout():
    root = psx(
        '<Grid gap="8px">'
        '<GridItem span="6" key="a"><button>A</button></GridItem>'
        '<GridItem span="6" key="b"><button>B</button></GridItem>'
        '</Grid>'
    )
    cache = NativeStructuralSnapshotReuse()
    stamp = stamp_tree(root)
    first = cache.normalize(root, {}, stamp, 0)
    assert first._participating_roots()[0].type == "Grid"
    for _ in range(5):
        assert cache.normalize(root, {}, stamp, 0) is first
    assert cache.builds == 1 and cache.hits == 5
    assert cache.projections == 0 and cache.projection_hits == 0
    changed = cache.normalize(root, {}, stamp, 1)
    assert changed is not first
    assert cache.builds == 2
