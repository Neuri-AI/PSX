# Portable Input

`Input` displays a single-line text input field with the same public contract in
every renderer. It mounts a `QLineEdit`, `ttk.Entry`, or Kivy `TextInput` (configured
with `multiline=False`) and preserves that widget during compatible updates. It dispatches
text changes and submit events using stable event slots.

| Property | Type | Default |
| --- | --- | --- |
| `value` | `str` | `""` |
| `placeholder` | `str` | `""` |
| `font_size` | Positive finite `int` or `float` (excluding bool), in pixels | `14` |
| `enabled` | `bool` | `True` |
| `read_only` | `bool` | `False` |
| `password` | `bool` | `False` |
| `on_change` | `Callable[[str], None]` or `None` | `None` |
| `on_submit` | `Callable[[], None]` or `None` | `None` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

The renderer rounds pixel sizes for toolkits that require integer sizes.
Font families and exact glyph metrics depend on the platform's default font.

The renderer updates text content, placeholder text, font size, read-only mode,
password masking, and enabled state natively without re-creating the underlying
widget or losing user focus or cursor position. Event callbacks are bound via stable
`EventSlot` connections. Programmatic updates from state reconciliation bypass
user-event signals to prevent feedback loops.

`Input` is a self-closing element and does not accept children. Providing children
to `<Input>` raises `InvalidChildError`. Multi-line text input is handled separately by `<TextArea>`.

```python
Input(value=text, placeholder="Enter text...", font_size=16, on_change=set_text, on_submit=handle_submit)

```

```python
psx('<Input value={text} placeholder="Enter text..." password={is_secret} on_change={set_text} on_submit={handle_submit} />',
    scope={"text": text, "is_secret": True, "set_text": set_text, "handle_submit": handle_submit})

```

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate `Native(...)` API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.