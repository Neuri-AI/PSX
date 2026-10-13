"""Executed feature-level receipts for real Qt widgets, for all four bindings.

The parametrization shares the driver, not the proof: each Qt binding
runs its own native widget instances and emits its own JUnit assertions.
"""
from __future__ import annotations

import importlib
import os

import pytest

from psx import Button, Flex
from psx.core.reconcile import Reconciler
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints
from tests.certification.public_behavior_census import Feature, assert_feature
from tests.certification.qt_public_properties import NATIVE_PROPERTY_CASES

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



@pytest.fixture
def qt_image_path(qt_tree, tmp_path):
    renderer, _ = qt_tree
    gui = importlib.import_module(f"{renderer._binding_package}.QtGui")
    image = gui.QImage(80, 40, gui.QImage.Format.Format_ARGB32)
    image.fill(gui.QColor("#ff0000"))
    path = tmp_path / "native-source.png"
    assert image.save(str(path))
    return str(path)


def property_view(name, prop, value, extra, image_path):
    import psx
    options = {"key": "control", "layout_width": "160px",
               "layout_height": "40px", "flex_basis": "160px", "flex_shrink": 0}
    if name == "Text":
        options["value"] = "Native text"
    elif name == "Button":
        options["label"] = "Native button"
    elif name == "Radio":
        options["value"] = "radio"
    elif name == "Image":
        options["source"] = image_path
    options.update(extra)
    options[prop] = value
    child = (psx.Scroll(Flex(width="300px", height="200px"), **options)
             if name == "Scroll" else getattr(psx, name)(**options))
    return Flex(child, width="400px", height="120px", align_items="flex-start")


@pytest.mark.parametrize("case", NATIVE_PROPERTY_CASES, ids=lambda case: case.id)
def test_native_property_update_and_readback(qt_tree, qt_image_path, request, case):
    renderer, tree = qt_tree
    def view(value):
        return property_view(case.component, case.prop, value, case.extra, qt_image_path)
    original = tree.render(view(case.before))
    widget = original.children[0].handle.widget
    assert case.read(widget) == case.expected_before
    changed = tree.render(view(case.after))
    assert changed.children[0].handle.widget is widget
    for scenario in ("live_update", "native_readback"):
        assert_feature(request, Feature(case.component, BINDING, "property", case.prop,
                                        scenario, applicability="native"),
                       case.read(widget) == case.expected_after)
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


def property_receipts(request, component, prop, condition):
    for scenario in ("live_update", "native_readback"):
        assert_feature(request, Feature(component, BINDING, "property", prop,
                                        scenario, applicability="native"), condition)


def painted_pixel(widget, x, y):
    return widget.grab().toImage().pixelColor(x, y).name()


@pytest.mark.parametrize("prop,before,after,point,old,new", [
    ("variant", "neutral", "danger", (20, 20), "#374151", "#b91c1c"),
    ("appearance", "filled", "outline", (20, 20), "#374151", None),
    ("shape", "rounded", "pill", (5, 5), "#374151", None),
])
def test_native_badge_painted_property(qt_tree, qt_image_path, request,
                                     prop, before, after, point, old, new):
    _, tree = qt_tree
    def view(value):
        return property_view("Badge", prop, value, {}, qt_image_path)
    widget = tree.render(view(before)).children[0].handle.widget
    assert painted_pixel(widget, *point) == old
    assert tree.render(view(after)).children[0].handle.widget is widget
    observed = painted_pixel(widget, *point)
    property_receipts(request, "Badge", prop,
                      observed == new if new is not None else observed != old)


def test_native_switch_color_paints_updated_track(qt_tree, qt_image_path, request):
    _, tree = qt_tree
    def view(value):
        return property_view("Switch", "color", value, {"checked": True}, qt_image_path)
    widget = tree.render(view("#ff0000")).children[0].handle.widget
    assert painted_pixel(widget, 8, 20) == "#ff0000"
    assert tree.render(view("#0000ff")).children[0].handle.widget is widget
    property_receipts(request, "Switch", "color", painted_pixel(widget, 8, 20) == "#0000ff")


def test_native_switch_size_changes_intrinsic_native_measure(qt_tree, qt_image_path, request):
    _, tree = qt_tree
    def view(value):
        return property_view("Switch", "size", value, {}, qt_image_path)
    widget = tree.render(view("small")).children[0].handle.widget
    before = (widget.sizeHint().width(), widget.sizeHint().height())
    assert before == (34, max(20, widget.fontMetrics().height() + 4))
    assert tree.render(view("large")).children[0].handle.widget is widget
    property_receipts(request, "Switch", "size",
                      (widget.sizeHint().width(), widget.sizeHint().height()) == (56, max(32, widget.fontMetrics().height() + 4)))


def test_native_link_href_uses_updated_navigation_target(qt_tree, qt_image_path, monkeypatch, request):
    _, tree = qt_tree
    visited = []
    monkeypatch.setattr("psx.renderers.components.link.webbrowser.open", visited.append)
    def view(value):
        return property_view("Link", "href", value, {"label": "Visit"}, qt_image_path)
    widget = tree.render(view("https://example.com/before")).children[0].handle.widget
    widget.click()
    assert visited == ["https://example.com/before"]
    assert tree.render(view("https://example.com/after")).children[0].handle.widget is widget
    widget.click()
    property_receipts(request, "Link", "href", visited == ["https://example.com/before", "https://example.com/after"])


@pytest.mark.parametrize("prop,before,after,extra,expected", [
    ("min", 0, 3, {"value": -1}, ("0", "3")),
    ("max", 10, 4, {"value": 20}, ("10", "4")),
])
def test_native_spinbox_range_updates_clamped_editor(qt_tree, qt_image_path, request,
                                                   prop, before, after, extra, expected):
    _, tree = qt_tree
    def view(value):
        return property_view("SpinBox", prop, value, extra, qt_image_path)
    widget = tree.render(view(before)).children[0].handle.widget
    assert widget._psx_parts[1].text() == expected[0]
    assert tree.render(view(after)).children[0].handle.widget is widget
    property_receipts(request, "SpinBox", prop, widget._psx_parts[1].text() == expected[1])


def test_native_spinbox_step_updates_native_increment(qt_tree, qt_image_path, request):
    _, tree = qt_tree
    values = []
    def view(value):
        return property_view("SpinBox", "step", value, {"value": 10, "on_change": values.append}, qt_image_path)
    widget = tree.render(view(1)).children[0].handle.widget
    widget._psx_parts[2].click()
    assert values == [11]
    assert tree.render(view(3)).children[0].handle.widget is widget
    widget._psx_parts[2].click()
    property_receipts(request, "SpinBox", "step", values == [11, 13])


def test_native_image_source_updates_decoded_pixels(qt_tree, qt_image_path, tmp_path, request):
    renderer, tree = qt_tree
    gui = importlib.import_module(f"{renderer._binding_package}.QtGui")
    image = gui.QImage(80, 40, gui.QImage.Format.Format_ARGB32)
    image.fill(gui.QColor("#0000ff"))
    alternate = tmp_path / "alternate-source.png"
    assert image.save(str(alternate))
    def view(value):
        return property_view("Image", "source", value, {}, qt_image_path)
    widget = tree.render(view(qt_image_path)).children[0].handle.widget
    assert widget.pixmap().toImage().pixelColor(80, 20).name() == "#ff0000"
    assert tree.render(view(str(alternate))).children[0].handle.widget is widget
    property_receipts(request, "Image", "source",
                      widget.pixmap().toImage().pixelColor(80, 20).name() == "#0000ff")


def test_native_image_fit_updates_letterbox_to_stretched_pixels(qt_tree, qt_image_path, request):
    _, tree = qt_tree
    def view(value):
        return property_view("Image", "fit", value, {}, qt_image_path)
    widget = tree.render(view("contain")).children[0].handle.widget
    assert widget.pixmap().toImage().pixelColor(1, 20).alpha() == 0
    assert tree.render(view("fill")).children[0].handle.widget is widget
    pixel = widget.pixmap().toImage().pixelColor(1, 20)
    property_receipts(request, "Image", "fit", pixel.name() == "#ff0000" and pixel.alpha() == 255)


@pytest.mark.parametrize("prop", ("width", "height"))
def test_native_image_requested_dimension_updates_intrinsic_geometry(qt_tree, qt_image_path, request, prop):
    import psx
    _, tree = qt_tree
    def view(value):
        child = psx.Image(qt_image_path, key="control", **{prop: value})
        return Flex(child, width="400px", height="120px", align_items="flex-start")
    widget = tree.render(view(20)).children[0].handle.widget
    before = widget.width() if prop == "width" else widget.height()
    assert before == 20
    assert tree.render(view(60)).children[0].handle.widget is widget
    after = widget.width() if prop == "width" else widget.height()
    property_receipts(request, "Image", prop, after == 60)


def test_native_radiogroup_value_updates_exclusive_selection(qt_tree, request):
    import psx
    _, tree = qt_tree
    def view(value):
        return Flex(psx.RadioGroup(
            psx.Radio("a", label="Alpha", key="alpha"),
            psx.Radio("b", label="Beta", key="beta"),
            value=value, key="group", layout_width="300px", layout_height="80px"),
            width="400px", height="120px")
    root = tree.render(view("a"))
    group = root.children[0]
    alpha, beta = (item.handle.widget for item in group.children)
    assert alpha.isChecked() and not beta.isChecked()
    updated = tree.render(view("b"))
    assert updated.children[0].handle.widget is group.handle.widget
    property_receipts(request, "RadioGroup", "value", not alpha.isChecked() and beta.isChecked())


def test_native_radio_value_updates_group_event_payload(qt_tree, request):
    import psx
    _, tree = qt_tree
    values = []
    def view(value):
        return Flex(psx.RadioGroup(
            psx.Radio(value, label="Mutable value", key="radio"),
            psx.Radio("other", label="Other", key="other"),
            value="other", on_change=values.append, key="group",
            layout_width="300px", layout_height="80px"),
            width="400px", height="120px")
    root = tree.render(view("before"))
    widget = root.children[0].children[0].handle.widget
    widget.click()
    assert values == ["before"]
    updated = tree.render(view("after"))
    assert updated.children[0].children[0].handle.widget is widget
    # Native selection must actually change to cause a fresh group callback.
    updated.children[0].children[1].handle.widget.click()
    values.clear()
    widget.click()
    property_receipts(request, "Radio", "value", values == ["after"])


def test_native_radiogroup_selection_tracks_updated_radio_values(qt_tree):
    import psx
    _, tree = qt_tree
    def view(radio_value, selection):
        return Flex(psx.RadioGroup(
            psx.Radio(radio_value, label="Mutable", key="radio"),
            psx.Radio("other", label="Other", key="other"),
            value=selection, key="group", layout_width="300px", layout_height="80px"),
            width="400px", height="120px")
    root = tree.render(view("before", "other"))
    mutable, other = (child.handle.widget for child in root.children[0].children)
    assert other.isChecked() and not mutable.isChecked()
    tree.render(view("after", "other"))
    tree.render(view("after", "after"))
    assert mutable.isChecked() and not other.isChecked()
    tree.render(view("after", None))
    assert not mutable.isChecked() and not other.isChecked()
