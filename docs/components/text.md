# Portable Text

`Text` displays plain text with the same public contract in every renderer.
It mounts a `QLabel`, `ttk.Label`, or Kivy `Label` and preserves that widget
during compatible updates. It has no events or framework-specific options.

| Property    | Type                                                         | Default                             |
| ----------- | ------------------------------------------------------------ | ----------------------------------- |
| `value`     | `str`, `int`, or `float` (excluding bool)                    | Required; first positional argument |
| `font_size` | Positive finite `int` or `float` (excluding bool), in pixels | `16`                                |
| `bold`      | `bool`                                                       | `False`                             |
| `italic`    | `bool`                                                       | `False`                             |
| `color`     | HEX string `#RRGGBB` or `None`                               | `None` (renderer/theme default)     |
| `align`     | `"left"`, `"center"`, or `"right"`                           | `"left"`                            |
| `enabled`   | `bool`                                                       | `True`                              |
| `key`       | `str`, `int`, or `None`                                      | `None`                              |
| `ref`       | PSX ref or `None`                                            | `None`                              |

The renderer rounds pixel sizes for toolkits that require integer sizes.
Alignment positions text horizontally within the label; layout owns its bounds.
`color=None` leaves color selection to the renderer/theme. An explicit HEX
color overrides it; omitting the color again removes that override. Qt uses
the inherited palette/stylesheet, Tkinter uses the ttk style, and Kivy uses
its standard Label colors.

Font families and exact glyph metrics depend on the platform's default font.

```python
Text("Hello", font_size=20, bold=True, color="#336699", align="center")
```

```python
psx(
    '<Text value="Hello" font_size={size} bold color="#336699" align="center" />',
    scope={"size": 20})
```

Unknown properties and invalid property values raise RendererCapabilityError.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate Native(...) API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.
