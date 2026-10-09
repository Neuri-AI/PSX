# Portable Slider

`Slider` displays a horizontal or vertical slider with the same public contract
in every renderer. It mounts a `QSlider`, `ttk.Scale`, or Kivy `Slider` and
preserves that widget during compatible updates. It dispatches value changes
using stable event slots.

| Property | Type | Default |
| --- | --- | --- |
| `value` | `float` | `0.0` |
| `min_value` | `float` | `0.0` |
| `max_value` | `float` | `100.0` |
| `step` | Non-negative `float` (`0.0` = continuous) | `0.0` |
| `orientation` | `"horizontal"` or `"vertical"` | `"horizontal"` |
| `enabled` | `bool` | `True` |
| `on_change` | `Callable[[float], None]` or `None` | `None` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`value` is always a `float` and must lie within `[min_value, max_value]`.
`step` controls the granularity of the slider: `0.0` means continuous motion,
any positive value snaps to multiples of `step`. `orientation` selects the
slider's axis. `enabled` disables user interaction.

Qt's native `QSlider` only works with integers, so the adapter maps the float
range to an integer range internally using a precision factor derived from
`step` (or from the decimal places of `min_value` and `max_value` when `step`
is `0.0`). The public contract stays float across all renderers.

The renderer updates value, range, step, orientation, and enabled state
natively without re-creating the underlying widget. Event callbacks are bound
via stable `EventSlot` connections. Programmatic updates from state
reconciliation bypass user-event signals to prevent feedback loops.

`Slider` is a self-closing element and does not accept children. Providing
children to `<Slider>` raises `InvalidChildError`.

```python
Slider(
    value=50.0,
    min_value=0.0,
    max_value=100.0,
    step=1.0,
    orientation="horizontal",
    on_change=set_volume,
)
```

```python
psx(
    '<Slider value={volume} min_value={0} max_value={100} step={1} '
    'on_change={set_volume} />',)
```
Unknown properties and invalid property values raise RendererCapabilityError.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate Native(...) API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.