```markdown
# Portable Divider

`Divider` renders a horizontal or vertical separator line with the same public
contract in every renderer. It mounts a `QFrame` with `Shape.HLine`/`Shape.VLine`,
a `ttk.Separator`, or a Kivy `Widget` with a `Line` on its canvas, and preserves
that widget during compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `orientation` | `"horizontal"` or `"vertical"` | `"horizontal"` |
| `thickness` | Non-negative `int` (≥ 1) | `1` |
| `color` | HEX string `#RRGGBB` or `None` | `None` (renderer/theme default) |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`Divider` is a leaf when it has no children, and a single-child layout when it
has exactly one. With no children it renders a plain line. With one child it
renders `─── child ───`: the child is laid out centered between two line
segments that together span the container's main axis. Providing more than one
child raises `InvalidChildError` in Python and `MarkupSyntaxError` in markup.

`orientation` selects the axis of the line. Horizontal separators consume
available width and have a fixed height of `thickness`; vertical separators
consume available height and have a fixed width of `thickness`.

`thickness` is the line width in pixels. The default `1` matches the native
separator of every renderer. Any other value triggers the renderer's custom
paint path, which overrides the toolkit's native theme separator.

`color=None` leaves the color to the renderer/theme. Qt uses the `QPalette`
mid color, Tkinter uses the current `ttk` theme's separator color, and Kivy
falls back to a neutral gray with transparency. An explicit `#RRGGBB` overrides
it. When `color` is provided, `thickness` defaults are not restored: each
update applies the current portable properties directly.

A single child that is a plain string is normalized to `Text` by the builder,
so `Divider("Sección")` and `<Divider>Sección</Divider>` produce the same tree.
The resulting `Text` uses its own portable contract for font size, color, and
alignment; `Divider` does not constrain it. Any `VNode` is accepted as the
child, though a text label is the common case.

```python
Column(
    Text("General"),
    Divider(),
    Text("Apariencia"),
    Divider(orientation="horizontal", thickness=2, color="#cccccc"),
    Text("Avanzado"),
    spacing=8,
)
```

```python
psx(
    '<Column spacing={8}>'
    '  <Text>General</Text>'
    '  <Divider />'
    '  <Text>Apariencia</Text>'
    '  <Divider thickness={2} color="#cccccc" />'
    '  <Text>Avanzado</Text>'
    '</Column>',
)
```

A labelled divider:

```python
Divider("Configuración avanzada")
```

```python
psx('<Divider>Configuración avanzada</Divider>')
```

```python
psx("""<Divider>
        <Text>Configuración avanzada</Text>
    </Divider>""")
```

A vertical divider between two columns:

```python
Row(
    Column(Text("Izquierda")),
    Divider(orientation="vertical"),
    Column(Text("Derecha")),
    spacing=12,
)
```

