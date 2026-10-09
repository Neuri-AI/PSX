"""PySide facades over PSX's shared Qt renderer."""

from __future__ import annotations

from .pyqt import QtRenderer


class PySide6Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PySide6", argv)


class PySide2Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None) -> None:
        super().__init__("PySide2", argv)


__all__ = ["PySide2Renderer", "PySide6Renderer"]
