# Portable Button

`Button` displays an interactive push button with the same public contract in
every renderer. It mounts a `QPushButton`, `ttk.Button`, or Kivy `Button` and
preserves that widget during compatible updates. It dispatches user clicks
using stable event slots.

| Property | Type | Default |
| --- | --- | --- |
| `label` | `str`, `int`, or `float` (excluding bool) | Required; first positional argument or markup child |
| `font_size` | Positive finite `int` or `float` (excluding bool), in pixels | `14` |
| `on_click` | `Callable[[], None]` or `None` | `None` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

The renderer rounds pixel sizes for toolkits that require integer sizes.
Font families and exact glyph metrics depend on the platform's default font.

The renderer updates button text, font size, and enabled state natively without
re-creating the underlying widget. Event callbacks are bound via stable `EventSlot`
connections: updating `on_click` replaces the target callback in place without
creating duplicate signal bindings or leaking memory on unmount.

Child text inside markup tags is normalized into the `label` property. Passing
both a `label` attribute and child text inside markup raises
`MarkupSyntaxError`.

```python
Button("Click me", font_size=18, enabled=True, on_click=handle_click)

```

```python
psx('<Button font_size={size} enabled={can_click} on_click={handle_click}>Click me</Button>',
    scope={"size": 18, "can_click": True, "handle_click": handle_click})

```

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate `Native(...)` API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.