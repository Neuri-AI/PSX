"""Real Headless renderer assertions for admitted portable surface."""
from __future__ import annotations

import pytest

from psx import Button, Flex, Text
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature
from tests.certification.headless_public_geometry import GEOMETRY_CASES


@pytest.fixture
def headless_tree():
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(400, True),
                                           AvailableSize(120, True)),
        engine=PythonLayoutEngine())
    tree = Reconciler(renderer)
    try:
        yield renderer, tree
    finally:
        tree.unmount()


@pytest.mark.parametrize(("name", "before", "after", "prop"),
                         [
                             ("Button", "Before", "After", "label"),
                             ("Text", "Before", "After", "value"),
                         ])
def test_admitted_headless_control_reconciliation(headless_tree, request,
                                                  name, before, after, prop):
    renderer, tree = headless_tree

    def view(value):
        options = {"key": "value", "layout_width": "160px",
                   "layout_height": "32px", "flex_basis": "160px", "flex_shrink": 0}
        child = Button(value, **options) if name == "Button" else Text(value, **options)
        return Flex(child, width="400px", height="120px",
                    align_items="flex-start")
    original = tree.render(view(before))
    handle = original.children[0].handle
    assert handle.props[prop] == before
    updated = tree.render(view(after))
    assert updated.children[0].handle is handle
    assert_feature(request, Feature(name, "headless", "property", prop,
                                    "live_update", applicability="native"),
                   handle.props[prop] == after)
    assert_feature(request, Feature(name, "headless", "property", prop,
                                    "native_readback", applicability="native"),
                   handle.props[prop] == after)
    assert renderer.sfle_result.geometry_commit_error == 0


def test_unported_headless_input_is_not_equivalent_to_native_certification(headless_tree):
    from psx import Input

    _, tree = headless_tree
    root = tree.render(Flex(
        Input(value="virtual", key="input", layout_width="100px",
              layout_height="24px", flex_basis="100px", flex_shrink=0),
        width="400px", height="120px"))
    assert root.children[0].handle.props["value"] == "virtual"
    # G2's unported classification does not imply creation rejection:
    # Headless can store a virtual handle without certifying native ports.


def receipt(request, component, kind, name, scenario, condition):
    assert_feature(request, Feature(component, "headless", kind, name,
                                    scenario, applicability="native"), condition)


def fixed_control(component, key, props):
    if component == "Flex":
        return Flex(key=key, **props)
    return (Text if component == "Text" else Button)(key, key=key, **props)


@pytest.mark.parametrize("component", ("Text", "Button", "Flex"))
@pytest.mark.parametrize("case", GEOMETRY_CASES, ids=lambda case: case.prop)
def test_headless_layout_property_has_mathematical_effect(headless_tree, request,
                                                          component, case):
    renderer, tree = headless_tree

    def view(value):
        options = {"layout_width": 40, "layout_height": 20, "flex_shrink": 0}
        options[case.prop] = value
        if case.prop == "flex_shrink":
            options["layout_min_width"] = 0
        return Flex(fixed_control(component, "subject", options),
                    Text("peer", key="peer", layout_width=40,
                         layout_height=20, flex_shrink=0),
                    width=case.viewport_width, height=120,
                    direction="column" if case.prop == "layout_margin_bottom" else "row",
                    align_items="flex-start")

    root = tree.render(view(case.before))
    handle = root.children[0].handle
    assert handle.geometry == case.before_rect
    root = tree.render(view(case.after))
    assert root.children[0].handle is handle
    # Margin-right changes the sibling's start; margin-bottom changes the
    # following sibling position in a column despite unchanged border geometry.
    condition = handle.geometry == case.after_rect
    if case.prop == "layout_margin_right":
        condition = condition and root.children[1].handle.geometry.x == 50
    if case.prop == "layout_margin_bottom":
        condition = condition and root.children[1].handle.geometry.y == 30
    receipt(request, component, "property", case.prop, "live_update", condition)
    receipt(request, component, "property", case.prop, "native_readback", condition)
    assert renderer.sfle_result.geometry_commit_error == 0


@pytest.mark.parametrize(("component", "prop", "before", "after"), [
    ("Text", "font_size", 16, 24), ("Text", "bold", False, True),
    ("Text", "italic", False, True), ("Text", "color", None, "#123456"),
    ("Text", "align", "left", "right"), ("Text", "enabled", True, False),
    ("Button", "font_size", 14, 24), ("Button", "enabled", True, False),
])
def test_headless_presentation_property_recording(headless_tree, request,
                                                   component, prop, before, after):
    _, tree = headless_tree

    def view(value):
        return Flex(fixed_control(component, "subject", {
            "layout_width": 40, "layout_height": 20, prop: value}),
            width=400, height=120)
    root = tree.render(view(before))
    handle = root.children[0].handle
    assert handle.props[prop] == before
    root = tree.render(view(after))
    assert root.children[0].handle is handle
    # Headless's presentation surface is a deterministic record, not pixels.
    receipt(request, component, "property", prop, "live_update", handle.props[prop] == after)
    receipt(request, component, "property", prop, "native_readback", handle.props[prop] == after)


@pytest.mark.parametrize("component", ("Text", "Button", "Flex"))
def test_headless_keyed_component_lifecycle(headless_tree, request, component):
    renderer, tree = headless_tree

    def view(keys):
        return Flex(*(fixed_control(component, key, {
            "layout_width": 40, "layout_height": 20, "flex_shrink": 0})
            for key in keys), width=400, height=120, align_items="flex-start")
    root = tree.render(view(("a", "b")))
    first, second = (child.handle for child in root.children)
    receipt(request, component, "lifecycle", "mount", "native_behavior",
            first.geometry.width == 40 and not first.destroyed and first in root.handle.children)
    root = tree.render(view(("a", "b")))
    receipt(request, component, "lifecycle", "update", "native_behavior",
            root.children[0].handle is first and root.children[1].handle is second)
    root = tree.render(view(("b", "a")))
    receipt(request, component, "lifecycle", "reorder", "native_behavior",
            root.children[0].handle is second and root.children[1].handle is first
            and root.handle.children == [second, first]
            and second.geometry.x == 0 and first.geometry.x == 40)
    tree.unmount()
    receipt(request, component, "lifecycle", "unmount", "native_behavior",
            first.destroyed and second.destroyed and renderer.sfle_result is None)


def test_headless_button_slot_dispatch_rebinding_and_teardown(headless_tree, request):
    _, tree = headless_tree
    called = []

    def view(callback):
        return Flex(Button("Go", key="button", on_click=callback,
                           layout_width=40, layout_height=20), width=400, height=120)
    root = tree.render(view(lambda payload: called.append(("old", payload))))
    handle = root.children[0].handle
    slot = handle.events["on_click"]
    slot.invoke("payload")
    receipt(request, "Button", "event", "on_click", "native_dispatch",
            called == [("old", "payload")])
    receipt(request, "Button", "event", "on_click", "payload",
            called[0][1] == "payload")
    root = tree.render(view(lambda payload: called.append(("new", payload))))
    assert root.children[0].handle is handle
    assert handle.events["on_click"] is slot
    slot.invoke("next")
    receipt(request, "Button", "event", "on_click", "rebind",
            called == [("old", "payload"), ("new", "next")])
    tree.unmount()
    slot.invoke("after")
    receipt(request, "Button", "event", "on_click", "teardown",
            handle.destroyed and not handle.events and len(called) == 2)


@pytest.mark.parametrize("case", [case for case in GEOMETRY_CASES
                                  if case.prop in {"layout_width", "layout_height",
                                                   "layout_min_width", "layout_min_height",
                                                   "layout_max_width", "layout_max_height"}],
                         ids=lambda case: case.prop.removeprefix("layout_"))
def test_headless_flex_dimension_alias_geometry(headless_tree, request, case):
    _, tree = headless_tree
    prop = case.prop.removeprefix("layout_")

    def view(value):
        options = {"width": 40, "height": 20, "flex_shrink": 0, prop: value}
        return Flex(Flex(key="subject", **options), width=400, height=120,
                    align_items="flex-start")
    root = tree.render(view(case.before))
    handle = root.children[0].handle
    assert handle.geometry == case.before_rect
    root = tree.render(view(case.after))
    assert root.children[0].handle is handle
    receipt(request, "Flex", "property", prop, "live_update", handle.geometry == case.after_rect)
    receipt(request, "Flex", "property", prop, "native_readback", handle.geometry == case.after_rect)


@pytest.mark.parametrize(("prop", "before", "after", "base", "expected"), [
    ("direction", "row", "column", {}, ((0, 0), (0, 20))),
    ("wrap", "nowrap", "wrap", {"width": 60}, ((0, 0), (0, 20))),
    ("justify_content", "flex-start", "center", {}, ((20, 0), (60, 0))),
    ("align_items", "flex-start", "center", {}, ((0, 50), (40, 50))),
    ("align_content", "flex-start", "space-between", {"width": 60, "wrap": "wrap"},
     ((0, 0), (0, 100))),
    ("gap", 0, 10, {}, ((0, 0), (50, 0))),
    ("column_gap", 0, 10, {}, ((0, 0), (50, 0))),
    ("row_gap", 0, 10, {"direction": "column"}, ((0, 0), (0, 30))),
    ("padding", 0, 10, {}, ((10, 10), (50, 10))),
])
def test_headless_flex_distribution_property_effect(headless_tree, request,
                                                      prop, before, after, base, expected):
    _, tree = headless_tree

    def view(value):
        options = {"width": 120, "height": 120, "align_items": "flex-start",
                   "align_content": "flex-start", **base, prop: value}
        return Flex(Text("a", key="a", layout_width=40, layout_height=20, flex_shrink=0),
                    Button("b", key="b", layout_width=40, layout_height=20, flex_shrink=0),
                    **options)
    root = tree.render(view(before))
    handle = root.handle
    children = tuple(child.handle for child in root.children)
    initial = tuple((child.geometry.x, child.geometry.y) for child in children)
    root = tree.render(view(after))
    observed = tuple((child.handle.geometry.x, child.handle.geometry.y)
                     for child in root.children)
    assert observed != initial
    assert root.handle is handle
    assert tuple(child.handle for child in root.children) == children
    receipt(request, "Flex", "property", prop, "live_update", observed == expected)
    receipt(request, "Flex", "property", prop, "native_readback", observed == expected)


def test_headless_flex_justify_gap_interaction(headless_tree, request):
    _, tree = headless_tree
    root = tree.render(Flex(Text("a", layout_width=40, layout_height=20, flex_shrink=0),
                            Button("b", layout_width=40, layout_height=20, flex_shrink=0),
                            width=120, height=120, gap=10, justify_content="center",
                            align_items="flex-start"))
    positions = tuple(child.handle.geometry.x for child in root.children)
    receipt(request, "Flex", "interaction", "justify_content__gap", "paired_native",
            positions == (15, 65))


def test_headless_flex_column_wrap_interaction(headless_tree, request):
    _, tree = headless_tree
    root = tree.render(Flex(Text("a", layout_width=40, layout_height=20, flex_shrink=0),
                            Button("b", layout_width=40, layout_height=20, flex_shrink=0),
                            width=120, height=30, direction="column", wrap="wrap",
                            align_items="flex-start", align_content="flex-start"))
    positions = tuple((child.handle.geometry.x, child.handle.geometry.y)
                      for child in root.children)
    receipt(request, "Flex", "interaction", "direction__wrap", "paired_native",
            positions == ((0, 0), (40, 0)))


def test_headless_fragment_transparent_lifecycle(headless_tree, request):
    from psx import Fragment, create_element

    renderer, tree = headless_tree

    def view(keys, label="a"):
        return Flex(create_element(Fragment, *(
            Text(label if key == "a" else key, key=key, layout_width=40,
                 layout_height=20, flex_shrink=0) for key in keys), key="boundary"),
            width=400, height=120, align_items="flex-start")

    root = tree.render(view(("a", "b")))
    boundary = root.children[0]
    first, second = (child.handle for child in boundary.children)
    receipt(request, "Fragment", "lifecycle", "mount", "transparent_boundary",
            boundary.handle.geometry is None and boundary.handle.children == [first, second]
            and len(renderer.sfle_result.boxes) == 3)
    root = tree.render(view(("a", "b"), "changed"))
    boundary = root.children[0]
    receipt(request, "Fragment", "lifecycle", "update", "transparent_boundary",
            boundary.handle.geometry is None and boundary.children[0].handle is first
            and first.props["value"] == "changed")
    root = tree.render(view(("b", "a")))
    receipt(request, "Fragment", "lifecycle", "reorder", "transparent_boundary",
            root.children[0].handle.geometry is None
            and root.children[0].handle.children == [second, first]
            and second.geometry.x == 0 and first.geometry.x == 40)
    tree.unmount()
    receipt(request, "Fragment", "lifecycle", "unmount", "transparent_boundary",
            boundary.disposed and first.destroyed and second.destroyed)
