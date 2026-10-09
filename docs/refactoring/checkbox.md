# REF-M7 Checkbox

`Checkbox` is the reference portable component added through the registry and adapter seams established in REF-M1–M6.

```python
from psx import Checkbox

Checkbox(checked=False, enabled=True, on_change=lambda checked: print(checked))
```

It has no children. `checked` and `enabled` default to `False` and `True`; `on_change` receives a `bool`. The default component registry registers `Checkbox` transparently, so existing markup can use `<Checkbox checked={selected} on_change={changed} />` with no manual registration.

The shared contract validates the three props. Renderer-local adapters map it to `QCheckBox` (PySide6, PyQt5, PyQt6), Kivy `CheckBox`, ttk `Checkbutton` and the headless handle. Programmatic `checked` updates suppress native notifications, while user changes route through the existing stable `EventSlot`. Compatible keyed reconciliation preserves widget identity; unmount removes the callback then destroys the PSX-owned widget.

## Scope accounting

REF-M7 created 3 files (`psx/renderers/checkbox.py`, `tests/test_checkbox.py`, this document) and modified 14 files: contracts, Python/public exports, built-in registry, five renderer backends, four backend test suites and `progress.md`. It did **not** modify the lexer, parser, markup compiler, reconciler or scheduler.

The only backend-specific limitation is visual labeling: Checkbox intentionally exposes the required boolean semantics only; labels remain application composition (`Row(Checkbox(...), Text(...))`) until a separately reviewed portable label contract is introduced.
