markdown
# Portable Row

`Row` arranges its children horizontally with the same public contract in
every renderer. It mounts a `QWidget` with a `QHBoxLayout`, a `ttk.Frame`
whose children are packed with `side=LEFT`, or a Kivy
`BoxLayout(orientation="horizontal")`, and preserves that container during
compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `*children` | `VNode` sequence | `()` |
| `spacing` | Non-negative `int` | `0` |
| `padding` | `int`, `(horizontal, vertical)`, or `(left, top, right, bottom)` of non-negative ints | `0` |
| `align` | `"start"`, `"center"`, `"end"`, or `"stretch"` | `"stretch"` |
| `expand` | `bool`, or a tuple of `bool` aligned with children | `False` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`align` positions each child **vertically** within the row. `start` maps to
the top edge, `end` to the bottom edge, `center` to the vertical midpoint,
and `stretch` lets the child fill the full height (the default).

`expand` controls whether each child grows **horizontally** to consume free
space. A single `bool` applies to every child; a tuple assigns a value per
position, and missing entries fall back to `False`.

`spacing` is the gap between consecutive children. `padding` is the inner
margin of the container: a single `int` applies to all four sides, a
two-tuple `(horizontal, vertical)` splits it, and a four-tuple
`(left, top, right, bottom)` sets each side explicitly.

`Row` is a container, not a leaf. Children are passed positionally in the
Python builder or written between the tags in markup. `align`, `expand` and
`spacing` apply per child, not to the row as a whole; when children are
reordered or replaced, those per-position values are reapplied without
re-creating the native widgets. `Row` does not accept textual content of its
own.

```python
Row(
    Button("Cancelar"),
    Button("Guardar"),
    spacing=8,
    align="center",
    expand=(False, True),
)
```

```python
psx(
    '<Row spacing={8} align="center" expand={expand_actions}>'
    '  <Button>Cancelar</Button>'
    '  <Button>Guardar</Button>'
    '</Row>',
    scope={"expand_actions": (False, True)},
)
```

Unknown properties and invalid property values raise RendererCapabilityError.
Builders, markup, and native renderers enforce this same contract. Each update
applies the current portable properties directly; removing an optional property
returns it to the portable default above. No native defaults are captured.

Use the separate Native(...) API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.