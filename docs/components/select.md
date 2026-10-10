# Portable Select

`Select` is a controlled, single-selection leaf component on Qt, Kivy,
Tkinter and Headless. It has `child_policy="none"`.

| Property | Type | Default |
| --- | --- | --- |
| `options` | Sequence of strings or `{"label": str, "value": str \| int}` mappings | `()` |
| `value` | `str \| int \| None` | `None` |
| `placeholder` | `str` | `""` |
| `enabled` | `bool` | `True` |
| `on_change` | `Callable[[str \| int], None] \| None` | `None` |
| `key`, `ref` | Runtime-managed | `None` |

Strings are shorthand for identical labels and values. Object options preserve
their typed values. Labels and values must be unique; boolean values are invalid.
The placeholder must not equal an option label. Invalid options or unknown
props raise `RendererCapabilityError`.

`value=None` shows the placeholder. If options change and the selected value
disappears, the placeholder is displayed until the state is updated. Selecting
an option emits its original value through `on_change`; reapplying a controlled
value does not emit an event. No `default_value`/uncontrolled mode is provided.

```python
from psx import psx, use_state

def render():
    language, set_language = use_state(None)
    languages = [
        {"label": "Python", "value": "python"},
        {"label": "JavaScript", "value": "js"},
        "Rust",
    ]
    return psx("""
        <Column spacing={8}>
            <Select options={languages} value={language}
                    placeholder="Choose a language"
                    on_change={set_language} />
            <Text>{language}</Text>
        </Column>
    """)
```

Qt uses `QComboBox` registered as a primitive; Kivy uses `Spinner`
registered as a primitive. Tkinter uses a small custom `ttk.Combobox`
adapter because its `<<ComboboxSelected>>` virtual event needs a proper
`bind`/`unbind` lifecycle. All updates preserve the native widget.
