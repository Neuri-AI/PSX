# CSS box geometry in Cinnamon

**Implementation branch:** `feature/universal-box-model-and-styling`. This
contract describes the bounded normal-flow box algorithm. Cinnamon remains the
only source of geometry for the native renderers.

## Layout box semantics

Each node receives four separate immutable rectangles: `content`, `padding`,
`border`, and `margin`, in that order moving outward. Positive padding and
borders enlarge the border box, while margins reserve space outside it.
Block children begin inside their parent's content box and subsequent block
siblings advance by the predecessor's complete outer margin box. **There is
no margin collapsing** in this currently certified subset.

`width` and `height` are content-box dimensions. `min-width`,
`max-width`, `min-height` and `max-height` constrain the resolved content
dimension, with minimum winning if minimum is greater than maximum. A
side-specific edge overrides the corresponding shorthand. An explicitly
specified `0px` is not the same thing as an omitted declaration.

Horizontal percentages and percentage margins/padding use the nearest
containing block's content width. Vertical percentages of height and height
constraints resolve against a definite containing height, and otherwise
defer to intrinsic/auto sizing. All resulting rectangles use Cinnamon's
1/64-pixel coordinate grid.

The native viewport is authoritative for the outermost root rectangle. Root
padding and borders reduce auto content size, rather than silently changing
the host window dimensions. Existing explicit validated `layout_*`
declarations override the corresponding CSS source slot. Native component
`width` and `height` properties retain their component-specific meanings.

## Unsupported cases

The semantic Block/Inline subset is not a browser layout algorithm. It does
not implement margin collapsing, floats, positioning, arbitrary text
fragmentation, or inline formatting owners with their own box edges. The
latter fail with explicit unsupported-feature diagnostics, rather than
producing misleading geometry. There is no implicit CSS Grid implementation.
CSS visual paint belongs to a separate native renderer increment.

## Regression evidence

The `tests/css/test_box_flow_geometry.py` suite asserts all four boxes,
nested flow spacing, constraints, percentages and definitive-height
semantics. The differential suite in
`tests/interop/test_sfle_differential.py` checks Rust/Python agreement over
full content/padding/border/margin rectangles. The native Qt, Tkinter, Kivy
and headless suites verify applied widget dimensions and offsets. Completion
requires exact-SHA successful CI and public behavior receipts where the
public CSS markup source exposes new capabilities.
