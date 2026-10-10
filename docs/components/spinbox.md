# SpinBox

Portable, **controlled** numeric editor with a consistent horizontal layout
`[−] [value] [+]` across Qt, Kivy and Tkinter, plus Headless support.

## Public contract

- **Type:** interactive leaf, `child_policy="none"`; children are not allowed
- **Controlled value:** `value` is authoritative; typed text is only a temporary edit
- **Event:** `on_change(int | float)` after a confirmed user action; never during programmatic updates
- **Interaction:** buttons, typed values, Up/Down, and wheel while the editor is focused
- **Range:** values outside `min`/`max` are clamped; invalid typed input restores the controlled value
- **Precision:** `decimals=0` emits `int`; otherwise emits `float`

| Property | Type | Default |
| --- | --- | --- |
| `value` | `int \| float` | `0` |
| `min` | `int \| float` | `0` |
| `max` | `int \| float` | `100` |
| `step` | `int \| float` | `1` |
| `decimals` | `int` in `0..9` | `0` |
| `enabled` | `bool` | `True` |
| `on_change` | `Callable[[int \| float], None] \| None` | `None` |
| `key`, `ref` | runtime metadata | `None` |

All numeric settings must be finite and not `bool`. `min <= max`,
`step > 0`, and step/bounds must be representable at the chosen decimal
precision. For example, a fractional step requires `decimals > 0`.
Decimal arithmetic is used internally to minimize floating point drift;
results are rounded half-up to the selected precision and clamped.

Typing intermediate text such as `-` or `.` does not emit an event.
Entering `abc` followed by Enter or focus loss restores the controlled
value. Numeric input is normalized on Enter or focus loss.
An unchanged normalized value does not reemit an event.

## Usage

```python
from psx import psx, use_state

def render():
    quantity, set_quantity = use_state(5)
    price, set_price = use_state(19.99)

    return psx("""
        <Column padding={20} spacing={12}>
            <Text>Quantity</Text>
            <SpinBox value={quantity} min={0} max={100}
                     step={1} on_change={set_quantity} />

            <Text>Price</Text>
            <SpinBox value={price} min={0} max={999.99}
                     step={0.25} decimals={2}
                     on_change={set_price} />
        </Column>
    """)
```

Markup expressions resolve local state and callbacks automatically.
Do not pass an explicit `scope` to `psx()`.

## Renderer strategy

| Renderer | Adapter | Native elements |
| --- | --- | --- |
| Qt | `QtSpinBoxAdapter` | `QWidget`, `QHBoxLayout`, `QPushButton`, `QLineEdit` |
| Kivy | `KivySpinBoxAdapter` | `BoxLayout`, `Button`, `TextInput` |
| Tkinter | `TkSpinBoxAdapter` | `ttk.Frame`, `ttk.Button`, `ttk.Entry` |
| Headless | Generic | In-memory handle |

All four backends share `psx/renderers/components/spinbox.py` for merging
props, normalization, parsing, formatting and arithmetic.

Stable instances are preserved through compatible reconciliations. Renderer
event adapters keep the stable `EventSlot`; updates never emit callbacks,
and unmounts clear event slots and destroy or detach owned native controls.

## Manual DX validation checklist (pending)

- Exercise integer and fractional configurations and `int`/`float` payloads.
- Type valid, invalid, intermediate, below-min and above-max values; commit by Enter and focus loss.
- Confirm `−`/`+` buttons obey `step` and clamp at boundaries.
- Confirm Up/Down and **wheel only with focused editor**.
- Confirm disabled states cannot edit or increment/decrement.
- Rerender controlled values, limits, steps and precision without native widget replacement or duplicate callbacks.
- Change the `on_change` callback and verify only the new slot receives events.
- Mount/unmount repeatedly without leaking callbacks or focus handlers.
- Compare horizontal layout and sizing across Qt, Kivy and Tkinter.

**Automated tests are deferred** to the end of the component rollout; no
automated tests are created or executed as part of this change.
