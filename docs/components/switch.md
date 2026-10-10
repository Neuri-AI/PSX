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
| `color` | `#RRGGBB` | `"#16A34A"` |
| `on_change` | `Callable[[bool], None] \| None` | `None` |
| `key`, `ref` | runtime identity/reference | `None` |

Qt and Tkinter use track dimensions of `34×20`, `44×26` and `56×32` logical
pixels for small, medium and large. Kivy currently scales those track
dimensions by 2× (`68×40`, `88×52`, `112×64`) to suit its layout and touch
interaction. Labels appear on the **right** of the track and are part of
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
                size="small"
                color="#8B5CF6"
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
| Kivy | custom adapter | custom-painted `ButtonBehavior` track plus adjacent `Label`, Kivy `Animation` |
| Tkinter | custom adapter | `ttk.Frame` holding `Canvas` and `ttk.Label`, `after` animation |
| Headless | generic adapter | validated props and stable EventSlot |

Adapters are required because Qt needs custom-painted animation; Kivy needs a
labeled custom-painted compound widget without exposing children to PSX; and Tkinter requires
drawing, timer ownership and keyboard bindings.

Programmatic `checked` updates change the visual state but **never** emit
`on_change`. A click/keyboard activation emits the requested boolean and the
parent state must commit it. All animation resources are owned by the widget
and cancelled/stopped at destruction.

## Manual DX validation (pending)

- Mount checked/unchecked with and without label.
- Change `size` through small, medium and large.
- Toggle with mouse and keyboard; verify exactly one boolean callback.
- In Kivy, verify `size="small"` remains clickable and completely visible.
- Update `color` and confirm the active track changes in Qt, Kivy and Tkinter.
- Update controlled state in code; verify no callback and stable native identity.
- Replace the event callback during reconciliation.
- Disable and re-enable; confirm no user toggles while disabled.
- Unmount mid-animation; verify no active timer or animation callback.

Automated tests intentionally deferred to the component-phase test backlog.
