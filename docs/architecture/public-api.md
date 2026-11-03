# Public Python API

The distribution is `velto-core`; applications import `psx`. This inventory covers
the names exported by `psx.__all__`, including components, hooks, native extensions
and renderer integration. Layout and virtualization remain internal responsibilities.

The checked snapshot is `tests/fixtures/public-api-exports.json`. Validate it with
`python -m scripts.docs.api_census --check tests/fixtures/public-api-exports.json`
and `python -m scripts.docs.validate_api_reference`.

```python
from psx import Flex, Text

view = Flex(Text("Hello, Velto!"), direction="column")
```

## `App`

Import: `from psx import App`. Defined in `psx.app.App`.

## `Badge`

Import: `from psx import Badge`. Defined in `psx.core.vnode.Badge`.

## `Button`

Import: `from psx import Button`. Defined in `psx.core.vnode.Button`.

## `Checkbox`

Import: `from psx import Checkbox`. Defined in `psx.core.vnode.Checkbox`.

## `ComponentAdapter`

Import: `from psx import ComponentAdapter`. Defined in `psx.renderers.ComponentAdapter`.

## `ComponentDefinition`

Import: `from psx import ComponentDefinition`. Defined in `psx.core.registry.ComponentDefinition`.

## `ComponentRegistry`

Import: `from psx import ComponentRegistry`. Defined in `psx.core.registry.ComponentRegistry`.

## `Divider`

Import: `from psx import Divider`. Defined in `psx.core.vnode.Divider`.

## `DuplicateKeyError`

Import: `from psx import DuplicateKeyError`. Defined in `psx.core.errors.DuplicateKeyError`.

## `Flex`

Import: `from psx import Flex`. Defined in `psx.core.vnode.Flex`.

## `Fragment`

Import: `from psx import Fragment`. Defined in `psx.core.vnode.Fragment`.

## `Grid`

Import: `from psx import Grid`. Defined in `psx.core.vnode.Grid`.

## `GridItem`

Import: `from psx import GridItem`. Defined in `psx.core.vnode.GridItem`.

## `HookOrderError`

Import: `from psx import HookOrderError`. Defined in `psx.core.errors.HookOrderError`.

## `Image`

Import: `from psx import Image`. Defined in `psx.core.vnode.Image`.

## `Input`

Import: `from psx import Input`. Defined in `psx.core.vnode.Input`.

## `InvalidChildError`

Import: `from psx import InvalidChildError`. Defined in `psx.core.errors.InvalidChildError`.

## `Link`

Import: `from psx import Link`. Defined in `psx.core.vnode.Link`.

## `MarkupSyntaxError`

Import: `from psx import MarkupSyntaxError`. Defined in `psx.core.errors.MarkupSyntaxError`.

## `Native`

Import: `from psx import Native`. Defined in `psx.core.native.Native`.

## `NativeOwnership`

Import: `from psx import NativeOwnership`. Defined in `psx.core.native.NativeOwnership`.

## `NativeWidget`

Import: `from psx import NativeWidget`. Defined in `psx.core.native.NativeWidget`.

## `PLUGIN_ENTRY_POINT_GROUP`

Import: `from psx import PLUGIN_ENTRY_POINT_GROUP`. Defined in `psx.plugins.PLUGIN_ENTRY_POINT_GROUP`.

## `PSXError`

Import: `from psx import PSXError`. Defined in `psx.core.errors.PSXError`.

## `Plugin`

Import: `from psx import Plugin`. Defined in `psx.plugins.Plugin`.

## `PluginAPI`

Import: `from psx import PluginAPI`. Defined in `psx.plugins.PluginAPI`.

## `ProgressBar`

Import: `from psx import ProgressBar`. Defined in `psx.core.vnode.ProgressBar`.

## `Radio`

Import: `from psx import Radio`. Defined in `psx.core.vnode.Radio`.

## `RadioGroup`

Import: `from psx import RadioGroup`. Defined in `psx.core.vnode.RadioGroup`.

## `Ref`

Import: `from psx import Ref`. Defined in `psx.core.hooks.Ref`.

## `RendererAdapterRegistry`

Import: `from psx import RendererAdapterRegistry`. Defined in `psx.renderers.RendererAdapterRegistry`.

## `RendererCapabilities`

Import: `from psx import RendererCapabilities`. Defined in `psx.plugins.RendererCapabilities`.

## `RendererCapabilityError`

Import: `from psx import RendererCapabilityError`. Defined in `psx.core.errors.RendererCapabilityError`.

## `RendererConfigurationError`

Import: `from psx import RendererConfigurationError`. Defined in `psx.core.errors.RendererConfigurationError`.

## `Scroll`

Import: `from psx import Scroll`. Defined in `psx.core.vnode.Scroll`.

## `Select`

Import: `from psx import Select`. Defined in `psx.core.vnode.Select`.

## `Slider`

Import: `from psx import Slider`. Defined in `psx.core.vnode.Slider`.

## `Spacer`

Import: `from psx import Spacer`. Defined in `psx.core.vnode.Spacer`.

## `SpinBox`

Import: `from psx import SpinBox`. Defined in `psx.core.vnode.SpinBox`.

## `Switch`

Import: `from psx import Switch`. Defined in `psx.core.vnode.Switch`.

## `Text`

Import: `from psx import Text`. Defined in `psx.core.vnode.Text`.

## `TextArea`

Import: `from psx import TextArea`. Defined in `psx.core.vnode.TextArea`.

## `ThreadViolationError`

Import: `from psx import ThreadViolationError`. Defined in `psx.core.errors.ThreadViolationError`.

## `VNode`

Import: `from psx import VNode`. Defined in `psx.core.vnode.VNode`.

## `WebView`

Import: `from psx import WebView`. Defined in `psx.extensions.WebView`.

## `builtin_component_registry`

Import: `from psx import builtin_component_registry`. Defined in `psx.core.registry.builtin_component_registry`.

## `component`

Import: `from psx import component`. Defined in `psx.core.component.component`.

## `create_element`

Import: `from psx import create_element`. Defined in `psx.core.vnode.create_element`.

## `load_plugins`

Import: `from psx import load_plugins`. Defined in `psx.plugins.load_plugins`.

## `native_adapter`

Import: `from psx import native_adapter`. Defined in `psx.core.native.native_adapter`.

## `native_widget`

Import: `from psx import native_widget`. Defined in `psx.core.vnode.native_widget`.

## `psx`

Import: `from psx import psx`. Defined in `psx.markup.psx`.

## `register_adapter`

Import: `from psx import register_adapter`. Defined in `psx.plugins.register_adapter`.

## `register_component`

Import: `from psx import register_component`. Defined in `psx.plugins.register_component`.

## `renderer_capabilities`

Import: `from psx import renderer_capabilities`. Defined in `psx.plugins.renderer_capabilities`.

## `use_effect`

Import: `from psx import use_effect`. Defined in `psx.core.hooks.use_effect`.

## `use_ref`

Import: `from psx import use_ref`. Defined in `psx.core.hooks.use_ref`.

## `use_state`

Import: `from psx import use_state`. Defined in `psx.core.hooks.use_state`.

