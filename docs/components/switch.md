# Switch

Portable, controlled and animated toggle switch for Qt (PySide6/PyQt6/PyQt5/PySide2),
Kivy, Tkinter and Headless.

## Contract

- **Role:** interactive leaf
- **Child policy:** `none` (children are not accepted)
- **State:** controlled `checked`; no `default_checked` or second authoritative state
- **Event:** `on_change(bool)` is fired only by user interaction
- **Lifecycle:** a compatible update retains the same native widget; bindings are released at unmount

| Prop | Type | Default |
| --- | --- | --- |
| `checked` | `bool` | `False` |
| `enabled` | `bool` | `True` |
| `label` | `str` | `""` |
| `size` | `"small" \| "medium" \| "large"` | `"medium"` |
| `on_change` | `Callable[[bool], None] \| None` | `None` |
| `key`, `ref` | runtime identity/reference | `None` |

Physical track dimensions are `34×20`, `44×26` and `56×32` logical pixels for
small, medium and large. Labels sit adjacent to the track and are part of
the native widget, not PSX child VNodes.

## Developer experience

```python
from psx import psx, use_state

def render():
    notifications, set_notifications = use_state(False)

    return psx("""
        <Column spacing={12}>
            <Switch
                label="Enable notifications"
                size="medium"
                checked={notifications}
                on_change={set_notifications}
            />
            <Text>{notifications}</Text>
        </Column>
    """)
```

No explicit `scope` is necessary: the markup resolves local state and callbacks.

## Backend strategy

| Renderer | Mechanism | Implementation |
| --- | --- | --- |
| Qt | custom adapter | `QAbstractButton` subclass with `QPainter` and owned `QPropertyAnimation` |
| Kivy | custom adapter | native `kivy.uix.switch.Switch` plus adjacent `Label`, native animation |
| Tkinter | custom adapter | `ttk.Frame` holding `Canvas` and `ttk.Label`, `after` animation |
| Headless | generic adapter | validated props and stable EventSlot |

Adapters are required because Qt needs custom-painted animation; Kivy needs a
labeled compound widget without exposing children to PSX; and Tkinter requires
drawing, timer ownership and keyboard bindings.

Programmatic `checked` updates change the visual state but **never** emit
`on_change`. A click/keyboard activation emits the requested boolean and the
parent state must commit it. All animation resources are owned by the widget
and cancelled/stopped at destruction.

## Manual DX validation (pending)

- Mount checked/unchecked with and without label.
- Change `size` through small, medium and large.
- Toggle with mouse and keyboard; verify exactly one boolean callback.
- Update controlled state in code; verify no callback and stable native identity.
- Replace the event callback during reconciliation.
- Disable and re-enable; confirm no user toggles while disabled.
- Unmount mid-animation; verify no active timer or animation callback.

Automated tests intentionally deferred to the component-phase test backlog.
