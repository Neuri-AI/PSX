# Portable RadioGroup

`RadioGroup` displays a set of `Radio` children where exactly one can be
selected at a time. It mounts a container with a `QButtonGroup` on Qt, a
shared `StringVar` on Tkinter, and a shared group name on Kivy, and
dispatches the newly selected value through a stable event slot.

| Property | Type | Default |
| --- | --- | --- |
| `*children` | `Radio` VNode sequence | `()` |
| `value` | `str`, `int`, or `None` | `None` |
| `on_change` | `Callable[[str \| int], None]` or `None` | `None` |
| `orientation` | `"vertical"` or `"horizontal"` | `"vertical"` |
| `spacing` | Non-negative `int` | `0` |
| `padding` | `int`, `(horizontal, vertical)`, or `(left, top, right, bottom)` of non-negative ints | `0` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`value` is the value of the currently selected `Radio`, or `None` when no
radio is selected. Setting `value` to the value of a child `Radio` selects
that child and deselects the rest; setting it to a value that matches no
child deselects all of them without raising.

`on_change` receives the value of the radio the user just selected. It is
not fired for programmatic changes made through `value`, only for
user-driven selections.

`orientation` selects the axis along which the children are laid out.
`spacing` is the gap between consecutive children. `padding` is the inner
margin of the container: a single `int` applies to all four sides, a
two-tuple `(horizontal, vertical)` splits it, and a four-tuple
`(left, top, right, bottom)` sets each side explicitly.

`enabled=False` disables the whole group. The individual `Radio` children
keep their own `enabled` state; a disabled group prevents any radio from
being selected regardless of its own state.

`RadioGroup` is a specialized container. It arranges its children along a
single axis in the same way `Column` and `Row` do. Children must be `Radio`
nodes; any other node raises `RendererCapabilityError` at mount time, as
does a duplicate `value` among siblings.

```python
RadioGroup(
    Radio("dark", label="Dark theme"),
    Radio("light", label="Light theme"),
    Radio("system", label="Follow system"),
    value=selected_theme,
    on_change=set_selected_theme,
    spacing=8,
)
```

```python
psx(
    '<RadioGroup value={selected} on_change={set_selected} spacing={8}>'
    '  <Radio value="dark" label="Dark theme" />'
    '  <Radio value="light" label="Light theme" />'
    '  <Radio value="system" label="Follow system" />'
    '</RadioGroup>',
)
```

A horizontal group:

```python
RadioGroup(
    Radio("small", label="S"),
    Radio("medium", label="M"),
    Radio("large", label="L"),
    orientation="horizontal",
    value=size,
    on_change=set_size,
    spacing=12,
)
```

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Each
update applies the current portable properties directly; removing an
optional property returns it to the portable default above. No native
defaults are captured.

Use the separate `Native(...)` API for framework-specific widgets and
features. References and keys retain their existing PSX lifecycle behavior.
