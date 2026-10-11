"""PySide facades over PSX's shared Qt renderer."""

from __future__ import annotations

from .pyqt import QtRenderer
from psx.sfle.model import LayoutConstraints


class PySide6Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None, *, sfle_constraints: LayoutConstraints | None = None, engine: object | None = None) -> None:
        super().__init__("PySide6", argv, sfle_constraints=sfle_constraints, engine=engine)


class PySide2Renderer(QtRenderer):
    def __init__(self, argv: list[str] | None = None, *, sfle_constraints: LayoutConstraints | None = None, engine: object | None = None) -> None:
        super().__init__("PySide2", argv, sfle_constraints=sfle_constraints, engine=engine)


__all__ = ["PySide2Renderer", "PySide6Renderer"]
