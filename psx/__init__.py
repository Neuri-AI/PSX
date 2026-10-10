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
from .core.registry import ComponentDefinition, ComponentRegistry, builtin_component_registry
from .plugins import (
    PLUGIN_ENTRY_POINT_GROUP,
    Plugin,
    PluginAPI,
    RendererCapabilities,
    load_plugins,
    register_adapter,
    register_component,
    renderer_capabilities,
)
from .renderers import ComponentAdapter, RendererAdapterRegistry
from .core.vnode import (
    Button,
    Checkbox,
    Column,
    Fragment,
    Input,
    Row,
    Text,
    TextArea,
    VNode,
    create_element,
    native_widget,
    Slider,
    Spacer,
    Divider,
    Image,
    ProgressBar,
    Radio,
    RadioGroup,
    Select,
)
from .integrations.qyro import PSXComponent

__all__ = [
    # Components
    "Button",
    "Column",
    "Checkbox",
    "TextArea",
    "Slider",
    "Row",
    "Text",
    "Spacer",
    "Fragment",
    "Native",
    "Input",
    "Divider",
    "Image",
    "ProgressBar",
    "Radio",
    "RadioGroup",
    "Select",

    "App",
    "ComponentDefinition",
    "ComponentAdapter",
    "ComponentRegistry",
    "DuplicateKeyError",
    "HookOrderError",
    "InvalidChildError",
    "MarkupSyntaxError",
    "NativeOwnership",
    "NativeWidget",
    "PSXError",
    "PLUGIN_ENTRY_POINT_GROUP",
    "Plugin",
    "PluginAPI",
    "RendererCapabilities",
    "RendererAdapterRegistry",
    "RendererCapabilityError",
    "RendererConfigurationError",
    "Ref",
    "ThreadViolationError",
    "VNode",
    "component",
    "builtin_component_registry",
    "create_element",
    "native_widget",
    "psx",
    "load_plugins",
    "register_adapter",
    "register_component",
    "renderer_capabilities",
    "use_effect",
    "use_ref",
    "use_state",
    "PSXComponent",
]
