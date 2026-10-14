"""Small standalone application facade for the portable renderer contract."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from psx.core.component import ComponentType
from psx.core.errors import RendererConfigurationError
from psx.core.grid_contract import GRID_BREAKPOINTS, resolve_grid_item_props, validate_grid_breakpoints
from psx.core.reconcile import Reconciler
from psx.core.vnode import VNode
from psx.renderers.headless import HeadlessRenderer
from psx.renderers.protocol import Renderer


class App:
    def __init__(self, root: VNode | ComponentType, *, renderer: str | Renderer | None = None, providers: tuple[object, ...] = (), settings: Mapping[str, object] | None = None) -> None:
        self.settings = self._validate_settings(settings)
        self.grid_breakpoints = self.settings['grid']['breakpoints']
        self.root = root() if isinstance(root, ComponentType) else root
        self.providers = providers
        self.renderer = self._resolve_renderer(renderer)
        self.reconciler = Reconciler(self.renderer)

    @staticmethod
    def _validate_settings(settings: Mapping[str, object] | None) -> Mapping[str, object]:
        """Validate application-level Grid settings before creating native widgets."""
        if settings is None:
            settings = {}
        if not isinstance(settings, Mapping) or set(settings) - {'grid'}:
            raise RendererConfigurationError("App settings support only the 'grid' section.")
        grid = settings.get('grid', {})
        if not isinstance(grid, Mapping) or set(grid) - {'breakpoints'}:
            raise RendererConfigurationError("App.settings.grid supports only 'breakpoints'.")
        thresholds = validate_grid_breakpoints(grid.get('breakpoints', GRID_BREAKPOINTS))
        return MappingProxyType({'grid': MappingProxyType({'breakpoints': thresholds})})

    def resolve_grid_item_props(
        self, props: Mapping[str, object], content_width: int | float,
    ) -> Mapping[str, object]:
        """Resolve GridItem metadata using this application's configured breakpoints.

        This does not mount Grid or compute geometry; later runtime gates will
        connect content-box width invalidation to the native layout engine.
        """
        return resolve_grid_item_props(
            props, content_width, breakpoints=self.grid_breakpoints,
        )

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
