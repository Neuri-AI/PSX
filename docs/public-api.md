# Public API

> **F3-G4 API:** `Flex` is the sole portable layout distributor. The
> public `Row` and `Column` builders, registry definitions, markup tags,
> native adapters and old geometry helpers were removed. There are no
> aliases or automatic conversions. `Scroll` remains a separate viewport.

```python
from psx import (
    App, Badge, Button, Checkbox, ComponentAdapter,
    ComponentDefinition, ComponentRegistry, Divider, Flex, Fragment,
    Image, Input, Link, Native, NativeOwnership, NativeWidget,
    PluginAPI, ProgressBar, Radio, RadioGroup, Ref,
    RendererAdapterRegistry, Scroll, Select, Slider, Spacer, SpinBox,
    Switch, Text, TextArea, VNode, builtin_component_registry,
    component, create_element, load_plugins, native_widget, psx,
    register_adapter, register_component, renderer_capabilities,
    use_effect, use_ref, use_state,
)
```

## Portable layout and markup

`Flex(direction="row")` distributes children horizontally, and
`Flex(direction="column")` distributes vertically. Use `gap` for
spacing, `padding` for the container inset, `align_items` for
cross-axis alignment, and child `flex_grow`/`flex_basis` to
participate in the available size.

`Text`, `Button`, `Input`, `Checkbox` and other admitted
widgets retain their portable semantics. `key` controls
reconciliation identity; `ref` is populated after mount.

`psx(source, scope=..., registry=...)` resolves registered built-ins
automatically, with static transforms available to bind lexical
variables directly. `<Row>` and `<Column>` are not registered
markup tags. See the [Flex reference](components/flex.md).

**Viewport ownership:** a renderer accepting `Flex` needs SFLE
constraints and its layout engine. The native toolkit contributes
intrinsic measurements and events, not a second geometry solver.

## Extensions

`ComponentRegistry` is instance-scoped. Create one with `builtin_component_registry()` and add a component with `register_component(registry, name, constructor, namespace=None, contract=None)`. A dot namespace produces markup-safe names such as `acme.Badge`; duplicate names raise `DuplicateComponentError`.

`ComponentAdapter` defines `create`, `update`, `bind_event`, `unbind_event`, and `destroy`. Register it through `register_adapter(renderer, component, adapter)` or `renderer.register_adapter()`. `renderer_capabilities(renderer)` reports adapters available on that renderer instance.

`Native(widget, props=..., signals=..., renderer=..., key=..., ref=...)` mounts a native class/factory (PSX-owned) or existing instance (borrowed). `NativeWidget` is the explicit advanced declaration.

`load_plugins(registry, renderers=..., plugins=..., namespace=...)` loads explicit plugin objects. `discover=True` loads the optional `psx.plugins` entry-point group. Normal imports never discover plugins or import GUI dependencies.

See [plugin details](refactoring/plugin-api.md) and [the example package](../examples/badge_plugin/pyproject.toml).
