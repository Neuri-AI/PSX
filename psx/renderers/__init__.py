"""Optional rendering backends and the dependency-free headless backend."""

from .headless import HeadlessRenderer
from .adapters import ComponentAdapter, RendererAdapterRegistry

__all__ = ["ComponentAdapter", "HeadlessRenderer", "RendererAdapterRegistry"]
