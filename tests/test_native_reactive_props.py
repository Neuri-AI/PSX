"""Regression suite for the public Native reactive property contract."""
from __future__ import annotations

import pytest

from psx.core.native import _apply_reactive_props, native_adapter, Native


class Widget:
    def __init__(self):
        self.calls = []

    def update_props(self, props, changed):
        self.calls.append((dict(props), changed))


def test_owned_widget_receives_initial_props_and_only_changes():
    w = Widget()
    _apply_reactive_props(w, {"url": "https://a", "enabled": True})
    _apply_reactive_props(w, {"url": "https://a", "enabled": True})
    _apply_reactive_props(w, {"url": "https://b", "enabled": True})
    assert len(w.calls) == 2
    assert w.calls[0][1] == frozenset({"url", "enabled"})
    assert w.calls[1][1] == frozenset({"url"})


def test_adapter_for_external_widget():
    class External: pass

    calls = []

    @native_adapter(External)
    def update(widget, props, changed):
        calls.append((widget, dict(props), changed))

    w = External()
    _apply_reactive_props(w, {"data": [1, 2]})
    assert calls == [(w, {"data": [1, 2]}, frozenset({"data"}))]


def test_instance_update_props_precedes_registered_adapter():
    class External:
        def update_props(self, props, changed):
            self.called = (props, changed)

    @native_adapter(External)
    def adapter(widget, props, changed):
        raise AssertionError("Should prefer instance implementation")

    w = External()
    _apply_reactive_props(w, {"data": 42})
    assert w.called[1] == frozenset({"data"})


def test_missing_adapter_fails_clearly():
    class External: pass
    with pytest.raises(TypeError, match="no update_props"):
        _apply_reactive_props(External(), {"data": 42})


def test_removed_props_fail_clearly():
    w = Widget()
    _apply_reactive_props(w, {"data": 42})
    with pytest.raises(ValueError, match="removed"):
        _apply_reactive_props(w, {})


def test_changed_handles_array_like_values_without_boolean_comparison():
    class Array:
        __module__ = "numpy.mock"

        def __eq__(self, other):
            raise ValueError("ambiguous truth")

    w = Widget()
    _apply_reactive_props(w, {"data": Array()})
    _apply_reactive_props(w, {"data": Array()})
    assert [changed for _, changed in w.calls] == [
        frozenset({"data"}), frozenset({"data"})
    ]


def test_native_constructor_factory_identity_is_stable():
    class QtWidget:
        __module__ = "PySide6.QtWidgets"
        def __init__(self, title, theme=None):
            self.title, self.theme = title, theme

    a = Native(QtWidget, kwargs={"title": "A", "theme": "dark"}, props={"data": 1}, key="same")
    b = Native(QtWidget, kwargs={"title": "A", "theme": "dark"}, props={"data": 2}, key="same")
    c = Native(QtWidget, kwargs={"title": "B", "theme": "dark"}, props={"data": 2}, key="same")
    assert a.type == b.type
    assert a.type != c.type
    assert a.type.factory().title == "A"


def test_native_reactive_qt_reconciles_without_remount(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    from psx.renderers.qt.pyside import PySide6Renderer
    from psx.core.reconcile import Reconciler
    from psx import Native as PublicNative
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    renderer = PySide6Renderer(argv=["native-reactive-test"])
    reconciler = Reconciler(renderer)

    class CustomLabel(QLabel):
        def __init__(self, prefix=""):
            super().__init__()
            self.prefix = prefix
            self.calls = []

        def update_props(self, props, changed):
            self.calls.append(changed)
            if "value" in changed:
                self.setText(self.prefix + props["value"])

    try:
        first = reconciler.render(
            PublicNative(CustomLabel, kwargs={"prefix": "v:"}, props={"value": "1"}, key="label")
        )
        widget = first.handle.widget
        assert widget.text() == "v:1"
        second = reconciler.render(
            PublicNative(CustomLabel, kwargs={"prefix": "v:"}, props={"value": "2"}, key="label")
        )
        assert second.handle.widget is widget
        assert widget.text() == "v:2"
        assert widget.calls == [frozenset({"value"}), frozenset({"value"})]
        third = reconciler.render(
            PublicNative(CustomLabel, kwargs={"prefix": "next:"}, props={"value": "3"}, key="label")
        )
        assert third.handle.widget is not widget
        assert third.handle.widget.text() == "next:3"
    finally:
        reconciler.unmount()
