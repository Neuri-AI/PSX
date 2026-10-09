# Portable Spacer

`Spacer` absorbs the free space of its parent along the parent's main axis
with the same public contract in every renderer. It mounts an invisible
`QWidget` with an expanding size policy, an empty `ttk.Frame` packed with
`expand=True`, or a Kivy `Widget` with `size_hint=1`, and preserves that
widget during compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`Spacer` has no portable properties beyond the runtime `key` and `ref`. Its
only behaviour is to consume the free space of its container.

Inside a `Column`, the spacer expands **vertically** and pushes its siblings
toward the top and bottom edges. Inside a `Row`, it expands
**horizontally** and pushes its siblings toward the left and right edges. The
parent container decides the axis; `Spacer` itself is axis-agnostic.

When several `Spacer` children coexist in the same container, they share the
free space equally, following the same rule used by `expand=True` on regular
children. Mixing `Spacer` with `expand=True` in the same parent is allowed but
rarely useful: both consume from the same pool.

`Spacer` is a leaf, not a container. It does not accept children and does not
accept textual content. `spacing` between a `Spacer` and its neighbours still
applies as usual, so the spacer and the gap compose predictably.

```python
Row(
    Text("Izquierda"),
    Spacer(),
    Text("Derecha"),
    padding=16,
)
```

```python
psx(
    '<Row padding={16}>'
    '  <Text>Izquierda</Text>'
    '  <Spacer />'
    '  <Text>Derecha</Text>'
    '</Row>',
)
```

Two spacers around a single child centre it along the container's main axis:

```python
Row(Spacer(), Text("Centrado"), Spacer())
```

A single trailing spacer anchors content to the start of a vertical column:

```python
Column(Text("Cabecera"), Text("Subcabecera"), Spacer())
```

Unknown properties and invalid property values raise RendererCapabilityError.
Builders, markup, and native renderers enforce this same contract. Removing an
optional property returns it to the portable default above. No native defaults
are captured.

Use the separate Native(...) API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.