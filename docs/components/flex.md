# Flex — portable layout

`Flex` is the only public layout-distribution component in PSX. SFLE owns the
layout geometry for Qt, Tkinter, Kivy and Headless. Toolkits provide intrinsic
measurement and native event handling, but cannot independently arrange the
portable Flex children.

## Directional layouts

```python
from psx import Button, Flex, Text, psx

horizontal = Flex(
    Button("Cancel", layout_width="120px", layout_height="36px"),
    Button("Save", layout_width="120px", layout_height="36px"),
    direction="row", width="320px", height="56px",
    gap=12, align_items="center",
)

vertical = Flex(
    Text("Settings"),
    horizontal,
    direction="column", width="400px", height="240px",
    padding=24, gap=16,
)
```

Markup uses the same single component:

```python
view = psx("""
    <Flex direction="column" width="400px" height="240px" padding={24} gap={16}>
        <Text>Settings</Text>
        <Flex direction="row" width="100%" gap={12}>
            <Button layout_width="120px" layout_height="36px">Cancel</Button>
            <Button layout_width="120px" layout_height="36px">Save</Button>
        </Flex>
    </Flex>
""")
```

The application/integration layer provides the viewport and SFLE engine to
the renderer. For explicit standalone PySide6 applications:

```python
from psx import App
from psx.renderers.qt.pyside import PySide6Renderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints

renderer = PySide6Renderer(
    sfle_constraints=LayoutConstraints(
        AvailableSize(400, True), AvailableSize(240, True)),
    engine=PythonLayoutEngine(),
)
app = App(vertical, renderer=renderer)
app.run()
```

For responsive roots, the application host should update
`renderer.set_sfle_constraints(...)` when the native viewport changes; the
native layout bridge then recommits the existing tree. A root must not delegate
its child distribution to `QBoxLayout`, Tkinter `pack`/`grid` or Kivy
`BoxLayout`.

### Properties

`direction` accepts `row`, `row-reverse`, `column` and
`column-reverse`. `wrap`, `justify_content`, `align_items`,
`align_content`, `gap`, `row_gap`, `column_gap`, `width`,
`height`, min/max dimensions and `padding` use the SFLE
contract. Items can express `flex_grow`, `flex_shrink`,
`flex_basis`, `align_self`, `order` and `layout_*` metadata.

The retired `Row` and `Column` builders and markup tags have **no
compatibility aliases**. See the migration reference in
[Row](row.md) and [Column](column.md).
