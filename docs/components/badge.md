# Badge

Portable, stateless and noninteractive status label with consistent semantic
colors and shapes across Qt, Kivy and Tkinter.

## Portable contract

- **Component:** `Badge`
- **Role:** visual leaf; `child_policy="text-only"`
- **Content property:** `label`
- **Events:** none; input/click callbacks are not accepted
- **State:** presentation only, no internal state or hooks
- **Supported:** Qt (PySide/PyQt), Kivy, Tkinter and Headless
- **Dependencies:** no mandatory Qyro or Pydux dependency

| Prop | Type | Default | Values |
| --- | --- | --- | --- |
| `label` | `str` | `""` | Any text |
| `variant` | `str` | `"neutral"` | `neutral`, `success`, `warning`, `danger`, `info` |
| `appearance` | `str` | `"filled"` | `filled`, `outline` |
| `size` | `str` | `"medium"` | `small`, `medium`, `large` |
| `shape` | `str` | `"rounded"` | `rounded`, `pill` |
| `enabled` | `bool` | `True` | Visual dimming only |
| `key`, `ref` | runtime metadata | `None` | PSX-managed |

Unknown properties, invalid values, callbacks, nested VNodes and non-string
labels are invalid. `label` can be passed as a builder argument, a
`label="..."` attribute, or a single text/interpolation child in markup.
Icons are reserved for a **future version** and are not supported by v1.

## Shared semantic palette

| Variant | Filled background | Filled text | Outline text/stroke |
| --- | --- | --- | --- |
| neutral | `#374151` | `#FFFFFF` | `#6B7280` |
| success | `#15803D` | `#FFFFFF` | `#15803D` |
| warning | `#A16207` | `#FFFFFF` | `#A16207` |
| danger | `#B91C1C` | `#FFFFFF` | `#B91C1C` |
| info | `#1D4ED8` | `#FFFFFF` | `#1D4ED8` |

Outline badges use a transparent or parent-matched surface; filled badges use a
solid background. A disabled badge uses a neutral dimmed palette.

| Size | Font | Horizontal padding | Vertical padding |
| --- | --- | --- | --- |
| small | 11 | 6 | 2 |
| medium | 12 | 8 | 4 |
| large | 14 | 10 | 6 |

Rounded shapes use a small corner radius; pill shapes use half the measured
badge height. Width depends on actual label measurement, not a fixed size.
These dimensions are logical tokens; underlying renderers apply their
toolkit-specific font and DPI conventions.

## Usage

```python
from psx import Badge, psx

python_badge = Badge("Active", variant="success", shape="pill")

def render():
    return psx("""
        <Column padding={16} spacing={12}>
            <Row spacing={8}>
                <Badge variant="success">Active</Badge>
                <Badge variant="warning">Pending</Badge>
                <Badge variant="danger">Failed</Badge>
                <Badge variant="info">Processing</Badge>
                <Badge variant="neutral">Draft</Badge>
            </Row>
            <Badge variant="info" appearance="outline"
                   size="small" shape="rounded">
                v1.0.0
            </Badge>
        </Column>
    """)
```

Note: conditional rendering with JSX-style ternary/boolean expressions is
**planned but not implemented**. For reactive updates, compute ordinary
supported expressions or build the desired Badge VNode in Python; do not
expect `{condition ? ... : ...}` to work in current PSX markup.

## Architecture and lifecycle

- **Shared tokens/validation:** `psx/renderers/components/badge.py`
  together with the core component contract and validator.
- **Qt:** self-sizing `QLabel` with QSS background, border and radius.
- **Kivy:** intrinsically sized `Label` with a rounded canvas background
  and outline stroke, rebuilt on resize or prop changes.
- **Tkinter:** `Canvas` with smooth rounded polygon and measured text. Tk
  has no native transparent Canvas background; outline uses its parent
  surface color when available.
- **Headless:** validates props and records updates without rendering.

On mount, the adapter validates/defaults props and creates one native widget.
On update, the same widget receives the latest label, colors, size and shape.
On unmount, owned widgets and graphical resources are released. No
subscriptions, `EventSlot`, timers or animations are required.

## Manual DX checklist — pending

- Compare every semantic variant in both `filled` and `outline` appearances.
- Compare `small`, `medium`, `large` with `rounded` and `pill`.
- Check intrinsic sizing for empty, short and long labels.
- Confirm labels render legibly inside `Row` and `Column` with explicit
  alignment; avoid assuming a child controls the parent layout.
- Verify updates preserve native widget identity and refresh text/appearance.
- Verify disabled palettes and no interactions/event subscriptions.
- Verify markup child-text and Python builder forms.
- Confirm unmount cleanup without leaked Kivy canvas instructions or Tk widgets.
- Check outline surface appearance on Qt, Kivy and Tkinter separately.

No automated tests are added or executed during this component phase.
