"""Small standalone application facade for the portable renderer contract."""

from __future__ import annotations

from psx.core.component import ComponentType
from psx.core.errors import RendererConfigurationError
from psx.core.reconcile import Reconciler
from psx.core.vnode import VNode
from psx.renderers.headless import HeadlessRenderer
from psx.renderers.protocol import Renderer


class App:
    def __init__(self, root: VNode | ComponentType, *, renderer: str | Renderer | None = None, providers: tuple[object, ...] = ()) -> None:
        self.root = root() if isinstance(root, ComponentType) else root
        self.providers = providers
        self.renderer = self._resolve_renderer(renderer)
        self.reconciler = Reconciler(self.renderer)

    @staticmethod
    def _resolve_renderer(renderer: str | Renderer | None) -> Renderer:
        if renderer == "headless":
            return HeadlessRenderer()
        if renderer is None:
            return App._renderer_from_qyro_settings()
        if isinstance(renderer, str) and renderer.lower() in {"pyside6", "pyside2"}:
            try:
                from psx.renderers.qt.pyside import PySide2Renderer, PySide6Renderer
            except ImportError as exc:
                raise RendererConfigurationError("PySide renderer requires its matching optional binding.") from exc
            return PySide6Renderer() if renderer.lower() == "pyside6" else PySide2Renderer()
        if isinstance(renderer, str) and renderer.lower() in {"pyqt6", "pyqt5"}:
            try:
                from psx.renderers.qt.pyqt import PyQt5Renderer, PyQt6Renderer
            except ImportError as exc:
                raise RendererConfigurationError("PyQt renderer requires its matching optional binding.") from exc
            return PyQt6Renderer() if renderer.lower() == "pyqt6" else PyQt5Renderer()
        if isinstance(renderer, str) and renderer.lower() == "tkinter":
            try:
                from psx.renderers.tkinter import TkinterRenderer
            except ImportError as exc:
                raise RendererConfigurationError(
                    "Tkinter renderer requires a Python distribution built with tkinter support."
                ) from exc
            return TkinterRenderer()
        if isinstance(renderer, str) and renderer.lower() == "kivy":
            try:
                from psx.renderers.kivy.kivy import KivyRenderer
            except ImportError as exc:
                raise RendererConfigurationError("Kivy renderer requires the optional Kivy dependency.") from exc
            return KivyRenderer()
        if isinstance(renderer, str):
            raise RendererConfigurationError(
                f"Renderer {renderer!r} is not available; use 'headless', 'pyside2', 'pyside6', 'pyqt5', 'pyqt6', 'tkinter', or 'kivy'."
            )
        return renderer

    @staticmethod
    def _renderer_from_qyro_settings() -> Renderer:
        try:
            from qyro import load_build_settings
        except ImportError as exc:
            raise RendererConfigurationError(
                "No renderer was provided. Install/configure Qyro or pass an explicit renderer."
            ) from exc
        settings = load_build_settings()
        configured = settings.get("binding") or settings.get("framework")
        if not isinstance(configured, str) or not configured.strip():
            raise RendererConfigurationError(
                "Qyro settings contain no usable 'binding' or 'framework'; pass an explicit renderer."
            )
        return App._resolve_renderer(configured.strip().lower())

    def mount(self) -> object:
        return self.reconciler.render(self.root).native_handle()

    def unmount(self) -> None:
        self.reconciler.unmount()

    def run(self) -> int:
        self.mount()
        return self.renderer.run()
