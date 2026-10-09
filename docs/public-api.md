# Public API

```python
from psx import (
    App, Button, Checkbox, Column, ComponentAdapter, ComponentDefinition,
    ComponentRegistry, Fragment, Input, Native, NativeOwnership, NativeWidget,
    PluginAPI, Ref, RendererAdapterRegistry, Row, Text, VNode,
    builtin_component_registry, component, create_element, load_plugins,
    native_widget, psx, register_adapter, register_component,
    renderer_capabilities, use_effect, use_ref, use_state,
)
```

## UI and markup

`Column`, `Row`, `Text`, `Button`, `Input`, and `Checkbox` are portable builders. `Column` and `Row` accept `spacing`, `padding`, `align`, positional `expand`, and `enabled`. `Checkbox` accepts `checked=False`, `enabled=True`, and `on_change: Callable[[bool], None] | None`. `key` controls reconciliation identity and `ref` is populated after commit.

`psx(source, scope=..., registry=...)` resolves familiar built-ins automatically. Markup keeps attributes, expressions, children, keys, refs, event handlers, static transform support, and legacy `primitives=` support.

## Extensions

`ComponentRegistry` is instance-scoped. Create one with `builtin_component_registry()` and add a component with `register_component(registry, name, constructor, namespace=None, contract=None)`. A dot namespace produces markup-safe names such as `acme.Badge`; duplicate names raise `DuplicateComponentError`.

`ComponentAdapter` defines `create`, `update`, `bind_event`, `unbind_event`, and `destroy`. Register it through `register_adapter(renderer, component, adapter)` or `renderer.register_adapter()`. `renderer_capabilities(renderer)` reports adapters available on that renderer instance.

`Native(widget, props=..., signals=..., renderer=..., key=..., ref=...)` mounts a native class/factory (PSX-owned) or existing instance (borrowed). `NativeWidget` is the explicit advanced declaration.

`load_plugins(registry, renderers=..., plugins=..., namespace=...)` loads explicit plugin objects. `discover=True` loads the optional `psx.plugins` entry-point group. Normal imports never discover plugins or import GUI dependencies.

See [plugin details](refactoring/plugin-api.md) and [the example package](../examples/badge_plugin/pyproject.toml).
