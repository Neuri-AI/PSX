"""PSX: declarative native UI for Python (Milestone 1 core)."""

from .app import App
from .core.component import component
from .core.errors import (
    DuplicateKeyError,
    HookOrderError,
    InvalidChildError,
    MarkupSyntaxError,
    PSXError,
    RendererCapabilityError,
    RendererConfigurationError,
    ThreadViolationError,
)
from .core.hooks import Ref, use_effect, use_ref, use_state
from .markup import psx
from .core.native import Native, NativeOwnership, NativeWidget
from .core.vnode import Button, Column, Fragment, Row, Text, VNode, create_element, native_widget

__all__ = [
    "App",
    "Button",
    "Column",
    "DuplicateKeyError",
    "Fragment",
    "HookOrderError",
    "InvalidChildError",
    "MarkupSyntaxError",
    "Native",
    "NativeOwnership",
    "NativeWidget",
    "PSXError",
    "RendererCapabilityError",
    "RendererConfigurationError",
    "Row",
    "Ref",
    "Text",
    "ThreadViolationError",
    "VNode",
    "component",
    "create_element",
    "native_widget",
    "psx",
    "use_effect",
    "use_ref",
    "use_state",
]
