from __future__ import annotations

import pytest

from psx import Text, create_element, psx
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.core.vnode import VNode, NodeKind
from psx.renderers.headless import HeadlessRenderer


@pytest.mark.parametrize("props", [
    {"value": True}, {"value": None}, {"value": []},
    {"font_size": 0}, {"font_size": -1}, {"font_size": True},
    {"font_size": float("inf")}, {"font_size": float("nan")}, {"font_size": "18sp"},
    {"bold": 1}, {"italic": "yes"}, {"enabled": None},
    {"color": "red"}, {"color": "#123"}, {"color": "#12345678"}, {"color": []},
    {"align": "justify"}, {"align": []}, {"wrap": True}, {"padding": 8},
    {"vertical_align": "top"}, {"underline": True}, {"strikethrough": True},
    {"qt": {}}, {"tkinter": {}}, {"kivy": {}},
    {"on_link_activated": lambda: None}, {"on_ref_press": lambda: None},
    {"on_native_signal:linkActivated": lambda: None}, {"on_click": lambda: None},
])
def test_closed_contract_rejects_invalid_values_and_unknown_props(props):
    options = {"value": "Hello", **props}
    with pytest.raises(RendererCapabilityError):
        Text(**options)
    with pytest.raises(RendererCapabilityError):
        create_element("Text", **options)
    # A hand-built VNode must not bypass renderer validation.
    with pytest.raises(RendererCapabilityError):
        HeadlessRenderer().create(VNode(NodeKind.HOST, "Text", None, options, ()), None)


@pytest.mark.parametrize("value", ["Hello", 42, 3.5])
def test_values_are_plain_text(value):
    assert Text(value).props["value"] == str(value)


def test_markup_uses_the_same_contract_and_defaults():
    node = psx('<Text font_size={size} bold color="#336699" align="right">Hello</Text>', scope={"size": 18.5})
    assert node.props == Text("Hello", font_size=18.5, bold=True, color="#336699", align="right").props
    with pytest.raises(RendererCapabilityError):
        psx('<Text wrap>Hello</Text>')


def test_reactive_updates_and_removal_keep_identity_and_destroy_once():
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    handle = reconciler.render(Text("old", font_size=24, bold=True)).handle
    reconciler.render(Text("new", font_size=12, color="#336699", align="right"))
    assert reconciler.root.handle is handle
    assert handle.props["value"] == "new"
    assert handle.props["bold"] is False
    reconciler.unmount()
    reconciler.unmount()
    assert handle.destroyed
    assert sum(op[0] == "destroy" for op in renderer.operations) == 1


def test_color_defaults_to_theme_in_python_and_markup():
    assert Text("theme").props["color"] is None
    assert Text("theme", color=None).props["color"] is None
    assert psx("<Text>theme</Text>").props["color"] is None
