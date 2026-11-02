"""Ordinary HTML/Flex card flows are eligible for sparse native worksets.

This test builds 500 cards x 6 nodes using immutable, already-solved
Cinnamon rectangles; no toolkit or alternative CSS solver is involved.
"""
from types import SimpleNamespace

from psx.core.vnode import NodeKind
from psx.layout.adapters.native_flow_viewport import plan_native_flow_viewport
from psx.layout.contracts.model import Rect


def _world(*, cards=500, viewport=300, changed_width=0,
           complex_card=None, nested_scroll=False):
    nodes = []
    identities = []
    handles = {}
    boxes = []
    def add(identifier, parent, x, y, width, height,
            *, tag="div", props=None, css=None):
        nodes.append(SimpleNamespace(node_id=identifier, parent_id=parent))
        source = SimpleNamespace(
            kind=NodeKind.HOST, type=tag, props=props or {},
            css_computed=(SimpleNamespace(properties=css)
                          if css is not None else None),
        )
        identities.append((identifier, source))
        handles[identifier] = object()
        boxes.append((identifier, SimpleNamespace(
            border=Rect(x, y, width, height)
        )))
    add("root", None, 0, 0, 600, viewport, tag="Flex")
    add("board", "root", 0, 0, 600, cards*40,
        tag="Scroll" if nested_scroll else "div")
    for i in range(cards):
        key = f"card-{i}"
        props = ({"style": {"transform": "translateY(-700px)"}}
                 if i == complex_card else {})
        add(key, "board", 0, i*40, 600+changed_width, 32, props=props,
            css={"position": "static", "overflow": "visible"})
        for j in range(5):
            add(f"{key}/child-{j}", key, j*10, i*40+j, 20, 5,
                tag="Text", css={"position": "static", "overflow": "visible"})
    snapshot = SimpleNamespace(nodes=tuple(nodes))
    result = SimpleNamespace(boxes=tuple(boxes))
    prepared = SimpleNamespace(identities=tuple(identities))
    renderer = SimpleNamespace(
        _sfle_constraints=SimpleNamespace(
            height=SimpleNamespace(value=viewport)
        )
    )
    return renderer, prepared, snapshot, result, handles


def test_500_card_html_flow_defers_more_than_2900_native_nodes():
    renderer, prepared, snapshot, result, handles = _world()
    first = plan_native_flow_viewport(renderer, prepared, snapshot, result,
                                      handles, "qt", epoch=1)
    assert not first.deferred_ids
    first.accept()
    second = plan_native_flow_viewport(renderer, prepared, snapshot, result,
                                       handles, "qt", epoch=1)
    assert len(second.deferred_ids) > 2900
    assert "card-0" not in second.deferred_ids
    assert "card-499/child-4" in second.deferred_ids
    second.accept()
    renderer._sfle_constraints.height.value = 21000
    tall = plan_native_flow_viewport(renderer, prepared, snapshot, result,
                                     handles, "qt", epoch=1)
    assert not tall.deferred_ids


def test_html_flow_respects_css_replacement_and_semantic_invalidation():
    renderer, prepared, snapshot, result, handles = _world(
        cards=24, viewport=100
    )
    plan = plan_native_flow_viewport(renderer, prepared, snapshot, result,
                                     handles, "tk", epoch=2)
    plan.accept()
    assert plan_native_flow_viewport(
        renderer, prepared, snapshot, result, handles, "tk", epoch=2
    ).deferred_ids
    # Even unchanged native identity cannot bypass a changed semantic epoch.
    assert not plan_native_flow_viewport(
        renderer, prepared, snapshot, result, handles, "tk", epoch=3
    ).deferred_ids
    # A card with newly changed CSS transform must remain fully active.
    replacement = list(prepared.identities)
    k = next(i for i, (key, _) in enumerate(replacement)
             if key == "card-23")
    changed = SimpleNamespace(
        kind=NodeKind.HOST, type="div",
        props={"style": {"position": "fixed"}}, css_computed=None,
    )
    replacement[k] = ("card-23", changed)
    updated = SimpleNamespace(identities=tuple(replacement))
    selected = plan_native_flow_viewport(
        renderer, updated, snapshot, result, handles, "tk", epoch=2
    ).deferred_ids
    assert "card-23" not in selected


def test_html_flow_inside_native_scroll_fails_closed():
    renderer, prepared, snapshot, result, handles = _world(
        cards=24, nested_scroll=True,
    )
    first = plan_native_flow_viewport(
        renderer, prepared, snapshot, result, handles, "kivy", epoch=1
    )
    assert first.workset is None and not first.deferred_ids
