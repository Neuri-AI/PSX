# Public API — alpha

The following imports are the supported PSX alpha surface:

```python
from psx import (
    App, Button, Column, Fragment, Native, NativeOwnership, NativeWidget,
    Ref, Row, Text, VNode, component, create_element, native_widget, psx,
    use_effect, use_ref, use_state,
)
```

`App` selects `headless`, `pyside6`, `pyqt6`, `pyqt5`, `tkinter`, or `kivy`.
Only the portable primitives (`Column`, `Row`, `Text`, and `Button`) share a
cross-renderer contract. Native widgets remain backend-specific by design.

`psx()` accepts explicit `scope` values; transformed M4B modules resolve
lexical names automatically. It never evaluates arbitrary Python expressions
inside markup. Use Python to compute conditional values before supplying them
to markup.

`Native(...)` is the ergonomic native-widget escape hatch. It accepts a native
widget class or borrowed instance, `props`, `signals`, `key`, and `ref`; see
[M10](m10-native-interoperability.md). `NativeWidget` is the lower-level API
for bespoke adapters.

Items under `psx.core.*`, `psx.renderers.*`, and `psx.devtools.*` are public
only where separately documented. Their internal handle classes and private
underscore-prefixed functions are not compatibility promises.
