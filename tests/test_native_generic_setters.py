"""Regression tests for generic Native Qt property synchronization.

No GUI event loop is needed: these exercises verify the generic property
dispatcher independently of the Qt bindings.
"""

import pytest

from psx.core.native import _qt_update


class CustomWidget:
    def __init__(self):
        self.current_url = None
        self.calls = []

    def set_url(self, url):
        self.current_url = url
        self.calls.append(("url", url))


class QtStyleWidget:
    def __init__(self):
        self.calls = []

    def setWindowTitle(self, title):
        self.calls.append(("title", title))


class PythonStyleWidget:
    def __init__(self):
        self.calls = []

    def set_background_color(self, value):
        self.calls.append(("background", value))


def test_custom_set_url_receives_original_string_and_updates_in_place():
    widget = CustomWidget()
    _qt_update(widget, {"url": "https://example.com"}, frozenset())
    _qt_update(widget, {"url": "https://example.org"}, frozenset())
    assert widget.current_url == "https://example.org"
    assert widget.calls == [
        ("url", "https://example.com"),
        ("url", "https://example.org"),
    ]


def test_qt_camel_case_property_setter():
    widget = QtStyleWidget()
    _qt_update(widget, {"window_title": "Hello"}, frozenset())
    assert widget.calls == [("title", "Hello")]


def test_python_snake_case_property_setter():
    widget = PythonStyleWidget()
    _qt_update(widget, {"background_color": "#123456"}, frozenset())
    assert widget.calls == [("background", "#123456")]


def test_does_not_call_arbitrary_methods():
    class Widget:
        def deleteLater(self):
            raise AssertionError("Must never invoke")

    with pytest.raises(AttributeError, match="no writable native property"):
        _qt_update(Widget(), {"deleteLater": True}, frozenset())


def test_removed_props_remain_explicitly_unsupported():
    with pytest.raises(ValueError, match="cannot be removed"):
        _qt_update(CustomWidget(), {}, frozenset({"url"}))
