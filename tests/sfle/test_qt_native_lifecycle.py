"""Real PySide6 offscreen SFLE UI-thread measurement and geometry commit."""
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")

from psx.sfle.constraint_propagation import ChildSizing
from psx.sfle.flex_math import FlexBasis
from psx.sfle.lengths import Length
from psx.sfle.margin_flex_pipeline import MarginFlexItem
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.native_lifecycle import NativeLayoutLifecycle, layout_and_commit
from psx.sfle.qt_measurement import QtMeasurementSource


def test_qt_offscreen_native_measure_and_commit():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = QtWidgets.QLabel("Root")
    child = QtWidgets.QLabel("Some text", root)
    try:
        generation = 14
        constraints = LayoutConstraints(
            AvailableSize(120, True), AvailableSize(80, True),
        )
        snapshot = LayoutInput(
            1, generation, WritingDirection.LTR, constraints, (
                LayoutNode("root", None, "Flex", ()),
                LayoutNode("child", "root", "Text", ()),
            ), (),
        )
        nodes = (
            MarginTreeNode("root", None, 120, 80),
            MarginTreeNode("child", "root", 40, 20, MarginFlexItem(
                "child", FlexBasis(40, 40, grow=0, shrink=0), 20,
            )),
        )
        source = QtMeasurementSource(
            {"root": root, "child": child}, qtcore=QtCore,
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.QT, nodes, {"child": child},
        )
        lifecycle = NativeLayoutLifecycle(
            lambda: generation, source.port(), committer,
        )
        result = layout_and_commit(
            snapshot, nodes, lifecycle,
            child_sizing=(("child", ChildSizing(
                Length.px(40), Length.px(20),
            )),),
        )
        assert result.deferred == ()
        assert child.geometry().width() == 40
        assert child.geometry().height() == 20
        assert result.measurements[0].intrinsic.preferred_width > 0
    finally:
        child.deleteLater()
        root.deleteLater()
        app.processEvents()
