# Portable ProgressBar

`ProgressBar` displays a determinate or indeterminate progress indicator with
the same public contract in every renderer. It mounts a `QProgressBar`, a
`ttk.Progressbar`, or a Kivy `ProgressBar`, and preserves that widget during
compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `value` | `float` | `0.0` |
| `min` | `float` | `0.0` |
| `max` | `float` | `100.0` |
| `indeterminate` | `bool` | `False` |
| `orientation` | `"horizontal"` or `"vertical"` | `"horizontal"` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

In determinate mode (`indeterminate=False`), the bar shows `value` as a
position between `min` and `max`. Values outside that range are clamped to
the nearest bound by the renderer, so a transient state such as a decrement
that briefly goes below `min` does not crash the app: the bar shows `min`
until the state comes back into range. The stored props keep the original
value, so a subsequent update to a different out-of-range value is still
detected as a change.

In indeterminate mode (`indeterminate=True`), the bar animates on its own to
signal that work is in progress without a specific completion figure.
`value` is ignored in this mode. Switching back to `indeterminate=False`
stops the animation and restores the bar to the last `value` (clamped to
`[min, max]` if it was out of range).

`orientation` selects the bar's axis. Horizontal bars consume available
width; vertical bars consume available height. Kivy's `ProgressBar` widget
does not support vertical orientation, so the Kivy adapter rejects
`orientation="vertical"` with `RendererCapabilityError`.

```python
ProgressBar(value=45.0, min=0.0, max=100.0)
ProgressBar(indeterminate=True)
```

```python
psx('<ProgressBar value={progress} min={0} max={100} />')
psx('<ProgressBar indeterminate />')
```

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Removing an
optional property returns it to the portable default above.

Use the separate `Native(...)` API for framework-specific widgets and features.
References and keys retain their existing PSX lifecycle behavior.
