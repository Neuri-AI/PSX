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

## Block hosts inside column Flex

PSX formatting hosts such as `<p>`, `<h1>`, `<section>` and `<div>`
retain block-style full available inline width when placed in a column
Flex container, including under `align-items: center`. This is a bounded
HTML-like block-host contract: it does not override native controls, images,
inline boxes or row-direction Flex children.

The shared CSS-to-Cinnamon projection marks an otherwise auto-sized block
item for *cross-axis stretch*, rather than injecting `width: 100%`.
This avoids a cyclic percentage dependency during recursive intrinsic
measurement and uses exactly the same immutable input in Qt, Tkinter,
Kivy and both Rust/Python Cinnamon engines.

Explicit `width`, `layout_width` and `align-self` are preserved. The
parent's `align-items` still aligns native controls that do not participate
in the block-host rule. Text reflows at the width assigned by Cinnamon, and
the native measurement port supplies its resulting auto height.

A full-width block does not imply centered text: `text-align: center`
must be authored separately when centered glyphs are desired.

## Inline text nested in block hosts

A block host can contain a mixed text run such as
`<p>Edit <span>src/App.tsx</span> and save to test HMR</p>`.
The `span` stays a distinct source VNode, retaining CSS inheritance, keys,
and native identity; the preceding and following Text nodes participate in
the same inline run. Word-sized measured fragments wrap at the container
inline width instead of inserting forced line breaks around the span.

For CSS Flex parents, the block host remains an auto-height, cross-axis
stretched flex item; the shared projection represents a mixed text run as
a wrapping row of native-measured fragments. For semantic block roots, the
measured Block/Inline compositor gathers the inline nodes into one line
sequence. Both paths use Cinnamon's immutable geometry and are toolkit
independent (Qt, Tkinter, Kivy). CSS `text-align` controls line alignment;
`align-items:center` does not imply centered glyphs.

This increment certifies the bounded mixed text/inline-span subset. It does
not claim browser-grade bidirectional shaping, letter-level fragmentation,
inline decoration fragmentation or inline layout of arbitrary controls.

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
