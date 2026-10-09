### 📄 `textarea.md` (reescrito, alineado con el resto)

Ya que estamos, te dejo también el `TextArea` con la misma estructura en inglés, para que los cinco docs queden homogéneos:

```markdown
# Portable TextArea

`TextArea` displays a multi-line plain-text editor with the same public
contract in every renderer. It mounts a `QPlainTextEdit`, a `tk.Text`, or a
Kivy `TextInput` (configured with `multiline=True`) and preserves that widget
during compatible updates. It dispatches text changes using stable event slots.

| Property | Type | Default |
| --- | --- | --- |
| `value` | `str` | `""` (first positional argument or markup child) |
| `placeholder` | `str` | `""` |
| `font_size` | Positive finite `int` or `float` (excluding bool), in pixels | `14` |
| `enabled` | `bool` | `True` |
| `read_only` | `bool` | `False` |
| `on_change` | `Callable[[str], None]` or `None` | `None` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

The renderer rounds pixel sizes for toolkits that require integer sizes.
Font families and exact glyph metrics depend on the platform's default font.

The renderer updates text content, placeholder text, font size, read-only
mode, and enabled state natively without re-creating the underlying widget or
losing user focus or cursor position. Event callbacks are bound via stable
`EventSlot` connections. Programmatic updates from state reconciliation bypass
user-event signals to prevent feedback loops.

`TextArea` is self-closing when given a `value` attribute or first positional
argument, and may also accept a single textual child inside markup as its
initial content. Providing more than one child, or combining a `value`
attribute with child text, raises `MarkupSyntaxError`. Single-line text input
is handled separately by `<Input>`.

```python
TextArea(
    "Contenido inicial...",
    placeholder="Escribe tu nota aquí...",
    font_size=16,
    on_change=lambda text: print(f"Nuevo texto: {text}"),
)
```

```python
psx(
    '<TextArea value={note} placeholder="Escribe tu nota aquí..." '
    'font_size={size} on_change={set_note} />',
    scope={"note": "Contenido inicial...", "size": 16, "set_note": set_note},
)
```
Unknown properties and invalid property values raise RendererCapabilityError.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate Native(...) API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.