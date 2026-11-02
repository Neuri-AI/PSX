"""Root Grid viewport native-workset regression tests (headless planner)."""
from types import SimpleNamespace

from psx.layout.adapters.grid_viewport_workset import (
    GridViewportWorkset, subtree_is_safe_for_root_culling,
)
from psx.layout.grid.grid_native_plan import GridNativePlacement
from psx.core.vnode import NodeKind

def place(node, y, h=32):
    return GridNativePlacement(node, 0, y, 200, h,
                               200, h, False, False)

def case(count):
    roots = tuple(f"item-{i}" for i in range(count))
    widgets, batch = {}, []
    for i, key in enumerate(roots):
        widgets[key] = object()
        widgets[key + "/leaf"] = object()
        batch += [place(key, i * 40), place(key + "/leaf", 0)]
    return roots, tuple(batch), widgets

def test_sparse_root_grid_over_500_cards():
    roots, batch, widgets = case(500)
    cache = GridViewportWorkset()
    args = dict(root_ids=roots, batch=batch, widgets=widgets, viewport_height=300,
                epoch=1, backend="qt", safe_ids=set(roots))
    assert not cache.plan(**args)  # First mount is always complete.
    cache.accept(**args, skipped=frozenset())
    selected = cache.plan(**args)
    assert len(selected) > 900
    assert "item-0" not in selected and "item-499/leaf" in selected
    cache.accept(**args, skipped=selected)
    assert cache.plan(**args) == selected

def test_resize_activates_newly_visible_groups():
    roots, batch, widgets = case(30)
    cache = GridViewportWorkset()
    args = dict(root_ids=roots, batch=batch, widgets=widgets, viewport_height=100,
                epoch=1, backend="kivy", safe_ids=set(roots))
    cache.accept(**args, skipped=frozenset())
    assert "item-29" in cache.plan(**args)
    taller = dict(args, viewport_height=1200)
    assert not cache.plan(**taller)
    cache.accept(**taller, skipped=frozenset())
    assert not cache.plan(**args)

def test_reconciliation_epoch_style_and_negative_y_fail_closed():
    roots, batch, widgets = case(30)
    cache = GridViewportWorkset()
    args = dict(root_ids=roots, batch=batch, widgets=widgets, viewport_height=100,
                epoch=4, backend="tk", safe_ids=set(roots))
    cache.accept(**args, skipped=frozenset())
    assert cache.plan(**args)
    assert not cache.plan(**dict(args, epoch=5))
    assert not cache.plan(**dict(args, safe_ids=set()))
    assert "item-29" not in cache.plan(**dict(
        args, widgets={**widgets, "item-29/leaf": object()}))
    negative = tuple(place("item-29/leaf", -100)
                     if p.node_id == "item-29/leaf" else p for p in batch)
    assert "item-29" not in cache.plan(**dict(args, batch=negative))

def test_overlap_is_not_occlusion_proof():
    roots, batch, widgets = case(30)
    cache = GridViewportWorkset()
    args = dict(root_ids=roots, batch=batch, widgets=widgets, viewport_height=100,
                epoch=1, backend="qt", safe_ids=set(roots))
    cache.accept(**args, skipped=frozenset())
    assert "item-0" not in cache.plan(**args)

def test_scroll_offset_reentry_rehydrates_oncoming_cards():
    roots, batch, widgets = case(30)
    cache = GridViewportWorkset()
    kwargs = dict(root_ids=roots, batch=batch, widgets=widgets,
                  viewport_height=100, epoch=3, backend="qt",
                  safe_ids=set(roots))
    cache.accept(**kwargs, skipped=frozenset())
    assert "item-29" in cache.plan(**kwargs)
    assert "item-29" not in cache.plan(**dict(kwargs, viewport_top=1050))
    assert "item-29/leaf" not in cache.plan(**dict(kwargs, viewport_top=1050))

def test_complex_css_and_native_controls_fail_closed():
    def node(props=None, kind=NodeKind.HOST, children=(), tag="Box"):
        return SimpleNamespace(kind=kind, type=tag,
            source=SimpleNamespace(props=props or {}),
            effective_children=children)
    assert subtree_is_safe_for_root_culling(node({"style": {"background": "#fff"}}))
    assert not subtree_is_safe_for_root_culling(node(children=(
        node({"style": {"transform": "translateY(-900px)"}}),)))
    assert not subtree_is_safe_for_root_culling(node(tag="Scroll"))
    assert not subtree_is_safe_for_root_culling(node(kind=NodeKind.NATIVE))
    assert not subtree_is_safe_for_root_culling(
        node({"style": {"position": "absolute"}}))
    assert not subtree_is_safe_for_root_culling(
        node({"style": {"overflow": "visible"}}))
    computed = node()
    computed.source.css_computed = SimpleNamespace(
        properties={"position": "fixed"}, specified=frozenset({"position"}),
    )
    assert not subtree_is_safe_for_root_culling(computed)
