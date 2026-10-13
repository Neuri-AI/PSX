"""Executed feature-level receipts for real Qt widgets, for all four bindings.

The parametrization shares the driver, not the proof: each Qt binding
runs its own native widget instances and emits its own JUnit assertions.
"""
from __future__ import annotations

import importlib
import os

import pytest

from psx import Button, Checkbox, Flex, Input
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature

BINDING = os.environ.get("PSX_QT_BINDING")
RENDERERS = {"pyside6": ("psx.renderers.qt.pyside", "PySide6Renderer"),
             "pyside2": ("psx.renderers.qt.pyside", "PySide2Renderer"),
             "pyqt5": ("psx.renderers.qt.pyqt", "PyQt5Renderer"),
             "pyqt6": ("psx.renderers.qt.pyqt", "PyQt6Renderer")}


@pytest.fixture
def qt_tree():
    if BINDING not in RENDERERS:
        pytest.fail("PSX_QT_BINDING must select a certified Qt runtime")
    module, name = RENDERERS[BINDING]
    cls = getattr(importlib.import_module(module), name)
    viewport = LayoutConstraints(AvailableSize(400, True), AvailableSize(120, True))
    renderer = cls(argv=["psx-public-native"], sfle_constraints=viewport,
                   engine=PythonLayoutEngine())
    tree = Reconciler(renderer)
    try:
        yield renderer, tree
    finally:
        tree.unmount()
        renderer.application.processEvents()


@pytest.mark.parametrize(("name", "before", "after", "read"),
                         [
                             ("Button", "Before", "After", lambda w: w.text()),
                             ("Checkbox", False, True, lambda w: w.isChecked()),
                             ("Input", "Before", "After", lambda w: w.text()),
                         ])
def test_native_property_update_and_readback(qt_tree, request, name, before, after, read):
    renderer, tree = qt_tree
    def view(value):
        options = {"key": "control", "layout_width": "160px",
                   "layout_height": "32px", "flex_basis": "160px", "flex_shrink": 0}
        if name == "Button":
            child = Button(value, **options)
        elif name == "Checkbox":
            child = Checkbox(checked=value, **options)
        else:
            child = Input(value=value, **options)
        return Flex(child, width="400px", height="120px", align_items="flex-start")

    original = tree.render(view(before))
    widget = original.children[0].handle.widget
    assert read(widget) == before
    changed = tree.render(view(after))
    assert changed.children[0].handle.widget is widget
    assert_feature(request, Feature(name, BINDING, "property",
                                    {"Button": "label", "Checkbox": "checked",
                                     "Input": "value"}[name],
                                    "live_update", applicability="native"),
                   read(widget) == after)
    assert_feature(request, Feature(name, BINDING, "property",
                                    {"Button": "label", "Checkbox": "checked",
                                     "Input": "value"}[name],
                                    "native_readback", applicability="native"),
                   read(widget) == after)
    assert renderer.sfle_result.geometry_commit_error <= 1


def test_native_button_event_rebind_and_disabled(qt_tree, request):
    _, tree = qt_tree
    calls = []
    def view(tag, enabled=True):
        return Flex(
            Button("Activate", key="action", enabled=enabled,
                   on_click=lambda: calls.append(tag),
                   layout_width="130px", layout_height="32px",
                   flex_basis="130px", flex_shrink=0),
            width="400px", height="120px", align_items="flex-start",
        )
    root = tree.render(view("first"))
    widget = root.children[0].handle.widget
    widget.click()
    assert_feature(request, Feature("Button", BINDING, "event", "on_click",
                                    "native_dispatch", applicability="native"),
                   calls == ["first"])
    assert_feature(request, Feature("Button", BINDING, "event", "on_click",
                                    "payload", applicability="native"),
                   len(calls) == 1 and calls[0] == "first")
    updated = tree.render(view("second"))
    assert updated.children[0].handle.widget is widget
    widget.click()
    assert_feature(request, Feature("Button", BINDING, "event", "on_click",
                                    "rebind", applicability="native"),
                   calls == ["first", "second"])
    tree.render(view("disabled", enabled=False))
    widget.click()
    assert_feature(request, Feature("Button", BINDING, "event", "on_click",
                                    "disabled", applicability="native"),
                   calls == ["first", "second"])
