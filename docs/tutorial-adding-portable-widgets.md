# Tutorial: add a portable PSX markup component

This is the recipe for a component that has a different native widget in each
toolkit, but one PSX meaning. For example, `WidgetX` might be a `QWidgetX` in
Qt, `TkWidgetX` in Tkinter, and `KivyWidgetX` in Kivy, while PSX users write:

```xml
<WidgetX value={amount} enabled={can_edit} on_change={set_amount} />
```

This is **not** a `Native` wrapper. `Native` exposes a toolkit-specific widget
to one renderer. A portable component defines one contract, one VNode tag and
one lifecycle per supported renderer.

## What must be true when the work is complete

```text
Python builder / PSX markup
             │
             ▼
    ComponentContract (portable semantics)
             │
             ▼
         VNode: "WidgetX"
             │
  ┌──────────┼──────────┬──────────┬──────────┐
  ▼          ▼          ▼          ▼          ▼
 Qt       Kivy       Tkinter   Headless    future renderer
```

The public props, defaults, values passed to events and child policy must mean
the same thing on every supported backend. Only the native widget and its
mechanics vary.

`Checkbox` and `TextArea` are useful in-repository references. The current
renderer registration APIs are in `psx.renderers.qt.pyqt`,
`psx.renderers.kivy.kivy`, and `psx.renderers.tkinter.tkinter`.

## Step 0: design the portable API first

Write the API before choosing native classes. Keep it deliberately small:

```python
WidgetX(
    value=0,
    enabled=True,
    on_change=None,   # Callable[[int], None] | None
    key="quantity",
)
```

Decide these things explicitly:

| Question | Example answer |
| --- | --- |
| What are the portable props? | `value`, `enabled`, `on_change` |
| Defaults? | `0`, `True`, `None` |
| What does an event deliver? | an `int` |
| Does it contain PSX children? | no |
| Is a feature portable? | include it only if every advertised renderer can honour it |

Do not add `qt_style`, `tk_variable`, or `kivy_canvas` props. Use `Native` if
an application genuinely needs an escape hatch.

## Step 1: define the contract

Add the prop sets, defaults, validator and contract in
`psx/core/contracts.py`. Contracts contain no GUI imports.

```python
from collections.abc import Mapping
from types import MappingProxyType

from .errors import RendererCapabilityError

WIDGETX_PROPS = frozenset({"value", "enabled", "on_change"})
WIDGETX_DEFAULTS = MappingProxyType({
    "value": 0,
    "enabled": True,
    "on_change": None,
})


def validate_widgetx_props(props: Mapping[str, object]) -> None:
    unknown = set(props) - WIDGETX_PROPS - {"ref"}
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported WidgetX props: {', '.join(sorted(unknown))}"
        )
    value = props.get("value", WIDGETX_DEFAULTS["value"])
    if isinstance(value, bool) or not isinstance(value, int):
        raise RendererCapabilityError("WidgetX.value must be an int.")
    if not isinstance(props.get("enabled", WIDGETX_DEFAULTS["enabled"]), bool):
        raise RendererCapabilityError("WidgetX.enabled must be a bool.")
    callback = props.get("on_change", WIDGETX_DEFAULTS["on_change"])
    if callback is not None and not callable(callback):
        raise RendererCapabilityError("WidgetX.on_change must be callable or None.")


WIDGETX_CONTRACT = ComponentContract(
    "WidgetX",
    WIDGETX_PROPS,
    WIDGETX_DEFAULTS,
    frozenset({"on_change"}),
    "none",
    validate_widgetx_props,
)
```

Validation must reject unknown props and invalid values; never silently coerce
an invalid portable API.

## Step 2: provide the Python builder

In `psx/core/vnode.py`, import the contract and add a builder. Preserve `key`
and `ref` exactly as other built-ins do.

```python
def WidgetX(
    *,
    value: int = 0,
    enabled: bool = True,
    on_change: Callable[[int], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    options = dict(value=value, enabled=enabled, on_change=on_change, **props)
    WIDGETX_CONTRACT.validate_builder(options)
    return create_element("WidgetX", key=key, ref=ref, **options)
```

Also preserve the compatibility re-exports in `vnode.py`: existing renderers
import `*_PROPS`, `*_DEFAULTS`, and `validate_*_props` from there. Add the new
names; do not replace the old import list.

Export `WidgetX` from `psx/__init__.py` and add it to `__all__`.

## Step 3: register the tag for built-in PSX markup

Add the constructor and contract to `builtin_component_registry()` in
`psx/core/registry.py`:

```python
from .contracts import WIDGETX_CONTRACT

# Inside builtin_component_registry(), after importing WidgetX:
registry.register("WidgetX", WidgetX, contract=WIDGETX_CONTRACT)
```

This is what makes `WidgetX` a PSX built-in. No lexer, parser or compiler
change is required. It also matters for the static markup transform: built-in
tags resolve through the registry, so developers do **not** import `WidgetX`
inside a render function merely to use `<WidgetX />`.

```python
from psx import psx

def render():
    value = 3

    def set_value(next_value: int) -> None:
        print(next_value)

    return psx('<WidgetX value={value} on_change={set_value} />')
```

Inside braces, PSX markup accepts references such as `{value}` and
`{set_value}`—not arbitrary Python expressions or `lambda`s.

## Step 4: create the shared prop normalizer

Create `psx/renderers/components/widgetx.py`. It owns portable prop merging
and per-backend application helpers. Its generic functions have no GUI import.

```python
from collections.abc import Mapping

from psx.core.contracts import (
    WIDGETX_DEFAULTS,
    WIDGETX_PROPS,
    validate_widgetx_props,
)
from psx.core.errors import RendererCapabilityError


def widgetx_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_widgetx_props(props)
    return {**WIDGETX_DEFAULTS, **props}


def updated_widgetx_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - WIDGETX_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported WidgetX props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return widgetx_props(result)
```

Add `apply_qt_widgetx`, `apply_kivy_widgetx`, and `apply_tk_widgetx` as
needed. Every apply helper must avoid generating a user event during a
programmatic `value` update: block Qt signals or use an equivalent renderer
guard.

## Step 5: register the native implementations

The component must be registered in every renderer it promises to support.
All renderer registries are module-level: call their `register_primitive()` at
module import time, near the existing built-in registrations.

### Qt: one registration for PyQt5/6 and PySide2/6

There is one `QtRenderer`, shared by both binding families. Add the
registration once in `psx/renderers/qt/pyqt.py`; do not duplicate it in
`pyside.py`.

```python
from psx.core.contracts import validate_widgetx_props
from psx.renderers.components.widgetx import (
    apply_qt_widgetx,
    updated_widgetx_props,
)

register_primitive(
    "WidgetX",
    qt_class="QWidgetX",
    validate=validate_widgetx_props,
    apply=apply_qt_widgetx,  # apply(widget, props, binding)
    updated_props=updated_widgetx_props,
    events={"on_change": ("valueChanged", emit_value)},
)
```

`qt_class` is resolved dynamically from `PySide2.QtWidgets`,
`PySide6.QtWidgets`, `PyQt5.QtWidgets`, or `PyQt6.QtWidgets`. The native Qt
class and event name must therefore exist with the same semantics in every Qt
binding you advertise. Use a custom event factory instead of `emit_value` when
the signal's arguments need conversion.

### Kivy

In `psx/renderers/kivy/kivy.py`, import the Kivy native class and register it:

```python
register_primitive(
    "WidgetX",
    factory=KivyWidgetX,
    validate=validate_widgetx_props,
    apply=apply_kivy_widgetx,
    updated_props=updated_widgetx_props,
    events={"on_change": ("value", emit_value)},
)
```

Kivy callbacks receive `(widget, value)`. If a programmatic update changes the
same property, set and check `widget._psx_updating` in the apply helper and
event factory, as `Checkbox` does.

### Tkinter

In `psx/renderers/tkinter/tkinter.py`, factories receive the parent widget:

```python
register_primitive(
    "WidgetX",
    factory=TkWidgetX,  # called as TkWidgetX(master)
    validate=validate_widgetx_props,
    apply=apply_tk_widgetx,
    updated_props=updated_widgetx_props,
    events={"on_change": ("command", emit_value)},
)
```

The built-in `emit_value` is not a Tkinter helper. If the callback needs to
read a value from the widget, define a local factory:

```python
def emit_widgetx(widget, slot):
    return lambda: slot.invoke(int(widget.get()))

# ... events={"on_change": ("command", emit_widgetx)}
```

### Headless

Headless is part of the portability contract because it enables deterministic
tests. Add `WidgetX` to its known component list and validate it on creation.
It stores an `EventSlot`; tests can invoke it directly:

```python
handle.events["on_change"].invoke(42)
```

If Headless is refactored to a primitive registry like the GUI renderers, use
that registry instead; the requirements stay the same: props validate, update
without recreation, and events store/unbind correctly.

## Step 6: test the full lifecycle

Add contract and markup tests, then one lifecycle test per renderer:

1. mount `WidgetX`;
2. verify its initial native value;
3. trigger a native user event and assert `on_change` receives the portable
   value;
4. render again with the same key and changed props; assert the native widget
   object is identical;
5. replace only `on_change`; assert there is still one native connection and
   the new callback runs;
6. unmount; assert the callback is disconnected or removed.

Minimum markup test:

```python
node = psx(
    '<WidgetX value={amount} on_change={set_amount} />',
    scope={"amount": 7, "set_amount": lambda value: None},
)
assert node.type == "WidgetX"
assert node.props["value"] == 7
```

Also add a transform test proving a built-in `<WidgetX />` tag does not create
a lexical `WidgetX` identifier or require `from psx import WidgetX`.

## Built-in versus application/plugin component

Use the built-in path above when PSX itself guarantees support and documents
the component. For a package-specific component, create a registry from
`builtin_component_registry()`, register its `ComponentContract` and
constructor there, and pass that registry to `psx(..., registry=registry)`.

Use a namespace such as `<acme.WidgetX />` for plugin components to avoid tag
collisions. The renderer registrations are still required; registry resolution
only creates the VNode, it does not teach a renderer how to mount it.

## Definition of done

- Contract, builder, export, and built-in markup registration exist.
- `<WidgetX />` works without importing the builder in render code.
- Qt registration exists once and works through both PySide and PyQt.
- Kivy, Tkinter, and Headless implement the promised lifecycle.
- Programmatic updates do not emit user callbacks.
- Lifecycle, markup, and validation tests pass.
- The public component documentation states props, defaults, events and
  supported renderers.
