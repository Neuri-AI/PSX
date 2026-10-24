"""A semantic Qt border must paint only its owning host widget."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from psx.css.cascade import StyleTarget, resolve_style
from psx.css.parser import parse_stylesheet


def test_semantic_header_border_is_scoped_to_host_widget():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QWidget
    from psx.renderers.qt.pyqt import QtHandle
    from psx.renderers.qt.pyside import PySide6Renderer

    renderer = PySide6Renderer(argv=["psx-semantic-border-test"])
    header = QWidget()
    greeting = QWidget(header)
    computed = resolve_style(
        parse_stylesheet("div { border-bottom: 1px solid #ccc; }"),
        StyleTarget("div"),
    )
    renderer.apply_css(QtHandle("div", header), computed)
    stylesheet = header.styleSheet()
    assert stylesheet.startswith(f"#{header.objectName()} {{")
    assert "border-bottom: 1px solid #cccccc;" in stylesheet
    assert greeting.styleSheet() == ""
    # Changing the host style must not introduce a generic QWidget selector
    # that also targets its children.
    renderer.apply_css(
        QtHandle("div", header),
        resolve_style(parse_stylesheet(""), StyleTarget("div")),
    )
    assert header.styleSheet() == ""
    header.deleteLater()


def test_semantic_card_full_border_is_scoped_to_host_widget():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QWidget
    from psx.renderers.qt.pyqt import QtHandle
    from psx.renderers.qt.pyside import PySide6Renderer

    renderer = PySide6Renderer(argv=["psx-card-border-test"])
    card = QWidget()
    paragraph = QWidget(card)
    computed = resolve_style(
        parse_stylesheet("div { border: 1px solid #e0e0e0; }"),
        StyleTarget("div"),
    )
    renderer.apply_css(QtHandle("div", card), computed)
    assert card.styleSheet().startswith(f"#{card.objectName()} {{")
    assert "border: 1px solid #e0e0e0;" in card.styleSheet()
    assert paragraph.styleSheet() == ""
    card.deleteLater()
