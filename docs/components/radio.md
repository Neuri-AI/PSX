# Portable Radio

`Radio` displays a single option in a mutually exclusive group with the same
public contract in every renderer. It mounts a `QRadioButton`, a
`ttk.Radiobutton`, or a Kivy `CheckBox` with a label, and preserves that
widget during compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `value` | `str` or `int` | Required; first positional argument |
| `label` | `str` | `""` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`Radio` is always expected to be placed inside a `RadioGroup`, which owns
the currently selected value and dispatches `on_change`. A `Radio` on its
own has no portable selection semantics; the renderer may still mount it,
but its behaviour is backend-specific. See the `RadioGroup` documentation
for the group contract.

`label` is the visible text next to the radio indicator. An empty `label`
renders just the indicator. `enabled=False` disables user interaction with
this specific radio without affecting its siblings.

`Radio` is a self-closing element and does not accept children. Providing
children to `<Radio>` raises `InvalidChildError`.

```python
Radio("dark", label="Dark theme")
Radio("light", label="Light theme")
```

```python
psx('<Radio value="dark" label="Dark theme" />')
psx('<Radio value="light" label="Light theme" />')
```

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Each
update applies the current portable properties directly; removing an
optional property returns it to the portable default above. No native
defaults are captured.

Use the separate `Native(...)` API for framework-specific widgets and
features. References and keys retain their existing PSX lifecycle behavior.

