# Row — retired portable container

The old `Row` builder and matching markup tag were
**removed in F3-G4**. They are not exported, registered or silently translated
into another component. Historical uses belong only in architecture and
migration records.

Replace them with `Flex(direction="row")`:

```python
from psx import Button, Flex, Text

view = Flex(
    Text("Account"),
    Button("Save"),
    direction="row",
    width="400px",
    height="240px",
    gap=12,
    padding=16,
)
```

Spacing migrates to `gap`; cross-axis alignment to `align_items`;
per-child expansion to `flex_grow` on the relevant child.
The old positional `expand` tuple is not preserved.

For complete geometry semantics and renderer setup, see [Flex](flex.md).
