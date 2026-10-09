# Tutorial: adding a portable widget

`Checkbox` is the reference portable widget. Its implementation follows the same sequence for a new component while preserving the public programming model.

## 1. Define a contract

Keep portable semantics free of toolkit imports. A contract lists props, defaults, events, validation, and child policy. Checkbox has `checked: bool = False`, `enabled: bool = True`, and `on_change: Callable[[bool], None] | None`; it has no children.

```python
from psx.core.contracts import ComponentContract

TOGGLE = ComponentContract(
    "Toggle", {"checked", "enabled", "on_change"},
    {"checked": False, "enabled": True, "on_change": None},
    {"on_change"}, "none", validate_toggle_props,
)
```

Validation must reject unknown props and must not coerce invalid values silently. For a built-in component, add the contract to the built-in registry. For an external package, pass it to `api.component()`.

## 2. Build a VNode

The public builder validates then returns a host VNode. Preserve `key` and `ref`.

```python
def Toggle(*, checked=False, enabled=True, on_change=None, key=None, ref=None):
    props = {"checked": checked, "enabled": enabled, "on_change": on_change}
    TOGGLE.validate_builder(props)
    return create_element("Toggle", key=key, ref=ref, **props)
```

Checkbox follows this exact pattern:

```python
from psx import Checkbox, Column, Text

ui = Column(
    Checkbox(checked=True, on_change=lambda checked: print(checked), key="terms"),
    Text("Accept terms"),
)
```

## 3. Register the component

External packages should use an explicit registry and namespace:

```python
from psx import builtin_component_registry, register_component, psx

registry = builtin_component_registry()
register_component(registry, "Toggle", Toggle, namespace="acme", contract=TOGGLE)
node = psx('<acme.Toggle checked={enabled} />', scope={"enabled": True}, registry=registry)
```

No parser or compiler change is required. The namespace prevents collisions and each registry is isolated.

## 4. Implement renderer adapters

Register the tag in every supported renderer and implement create, update, bind, unbind, and destroy. Use a shared prop normalizer like `psx.renderers.checkbox`.

| Backend | Checkbox native type | Event | Update rule |
| --- | --- | --- | --- |
| PySide6 | `QCheckBox` | `toggled(bool)` | block signals before `setChecked` |
| PyQt5/PyQt6 | `QCheckBox` | `toggled(bool)` | block signals before `setChecked` |
| Kivy | `CheckBox` | `active` | mark programmatic update while setting `active` |
| Tkinter | `ttk.Checkbutton` | `command` | read a `BooleanVar` |
| Headless | `HeadlessHandle` | stored `EventSlot` | update props in memory |

Always route a native value through `slot.invoke(bool(value))`. Do not connect a new signal on a callback-only update: reconciliation updates the existing `EventSlot`.

## 5. Test the lifecycle

For every backend, test mount, a user event, a prop update with the same key, callback replacement, and unmount. Assert the widget object is unchanged after a compatible update and that no callback remains after teardown. `tests/test_checkbox.py`, `test_pyside6_renderer.py`, `test_pyqt_renderer.py`, `test_kivy_renderer.py`, and `test_tkinter_renderer.py` are executable references.

## Troubleshooting and practices

- Use `RendererCapabilityError` for unsupported props or backend behavior.
- Keep contracts and shared normalizers GUI-free.
- Do not mutate VNodes or call native widgets from a worker thread; state updates use the renderer scheduler.
- Use `key` when identity must survive reorder or replacement.
- Prefer composition (`Row(Checkbox(...), Text(...))`) instead of adding a backend-specific label prop without a portable contract.
