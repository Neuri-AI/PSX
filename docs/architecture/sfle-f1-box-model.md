# SFLE F1.6/F1.7 — Ratified contracts, CSS box model and percentages

> **Decision status (2026-10-10):** D-F1.6 and D-F1.7 **closed at
> architectural-contract level**. The user approved direct item metadata,
> single-root functional components, inert metadata outside Flex, namespaced
> `layout_width`/`layout_height`, and immutable tagged lengths with deferred
> percentage resolution and `calc()` postponed.
>
> **Implementation status:** design only; no SFLE code, tests, or public API
> changes implemented. The CSS keyword/feature support matrix below is a
> **normative semantic contract for supported functionality**, not a claim
> that the first implementation supports every CSS feature.
>
> Related: [SFLE architecture](sfle.md),
> [F1 decision record](sfle-f1-contracts.md).
> Normative references:
> [CSS Flexbox Level 1](https://www.w3.org/TR/css-flexbox-1/),
> [CSS Sizing Level 3](https://www.w3.org/TR/css-sizing-3/),
> [CSS Box Model Level 3](https://www.w3.org/TR/css-box-3/),
> [CSS Box Sizing Level 3](https://www.w3.org/TR/css-sizing-3/#box-sizing).

## 1. Ratified decision matrix

| ID | Final decision | Invariant |
| --- | --- | --- |
| D-F1.6.A | Function components participate as a single logical flex item **only when their rendered root is single-root** | No anonymous multi-root box in initial release; unsupported multi-root use is rejected with a precise diagnostic |
| D-F1.6.B | Validate and preserve flex item metadata outside Flex; it is **inert** | Moving a component into or out of Flex does not silently mutate its public props |
| D-F1.6.C | Shared closed property partitioner plus existing strict component validators | No flex-only metadata reaches native widget constructors |
| D-F1.7.A | Namespaced `layout_width`, `layout_height` (and matching sizing constraints) | Existing `width`/`height` on Image/Scroll/etc. retain their established meanings |
| D-F1.7.B | Immutable discriminated length values; PX, PERCENT, AUTO, intrinsic tags; defer `calc()` | No evaluation of arbitrary length expressions |
| D-F1.7.C | CSS-compatible content/padding/border/margin model and box-sizing | No layout shortcuts that materially change browser geometry |
| D-F1.7.D | Per-property percentage references and definite-size tracking; defer cyclic resolution | Unknown and auto are not the number zero |

The exact **numeric tolerance** and **Rust implementation language** remain
D-F1.11 and F1-RUST, not decided by this contract.

## 2. Contextual shared layout properties (D-F1.6)

### 2.1 Closed property namespaces

A portable host element has three disjoint conceptual domains:

1. **Native/component-owned:** supplied exclusively to existing closed
   `ComponentContract` validation and to the renderer's widget adapter.
2. **Shared SFLE item metadata:** declared on existing portable components,
   normalized by `LayoutPropsResolver`, consumed only if the effective
   direct parent establishes a Flex formatting context.
3. **VNode identity/control:** existing `key` and `ref` handling, not CSS.

The initial shared item registry is closed:

| Prop | CSS counterpart | Default | Validation |
| --- | --- | --- | --- |
| `flex_grow` | flex-grow | 0 | finite float >= 0, bool prohibited |
| `flex_shrink` | flex-shrink | 1 | finite float >= 0, bool prohibited |
| `flex_basis` | flex-basis | auto | allowed length kinds by property |
| `align_self` | align-self | auto | closed alignment enum |
| `order` | order | 0 | signed integer, bool prohibited |
| `layout_width`, `layout_height` | width/height | auto | width/height typed length |
| `layout_min_width`, `layout_min_height` | min-width/min-height | auto | typed min constraint |
| `layout_max_width`, `layout_max_height` | max-width/max-height | none | typed max constraint |
| `layout_margin` and `layout_margin_{top,right,bottom,left}` | margin | 0 | length/percent/auto, negatives allowed |
| `layout_padding` and `layout_padding_{top,right,bottom,left}` | padding | 0 | nonnegative length/percent |
| `layout_border_{top,right,bottom,left}` | border widths | 0 | nonnegative physical widths |
| `layout_box_sizing` | box-sizing | content-box | content-box or border-box |

**Scope detail:** the `layout_*` namespace describes the logical flex-item
box and must not be mistaken for the component's existing `padding`, `width`
or `height` behavior. Border widths are reserved numeric layout edges;
border rendering/color/style is outside this design and may require native
rendering support before nonzero borders can be accepted in conformance mode.

A `Flex` container has its own dedicated contract, so its `width`,
`height`, `padding` and `gap` can be CSS-like without changing an
existing component's names. When `Flex` itself is a child of another Flex,
its own `layout_*` and flex-item fields govern its outer parent-facing box;
its container props govern its internal formatting context.

### 2.2 Conflict handling and validation phases

- The closed `LayoutPropsResolver` partitions recognized `flex_*`,
  `align_self`, `order`, and `layout_*` fields *before* native validation.
- The base component contract runs unchanged on its own properties; the
  shared validator runs independently on layout metadata.
- Unrecognized or misspelled names raise an error; they are not treated as
  optional native kwargs.
- A name collision with a component-owned property is a design error and
  must be rejected by registration. The namespace is not a back door for
  changing legacy `width`/`height` semantics.
- Builder errors and renderer errors retain their existing compatibility
  behavior; normalization must be common so Python builders, markup and
  reconciliation agree on accepted values.
- `component_props` and `item_style` are immutable logical snapshots.
  Original VNode props remain available for diffing, debug tooling and rerender.
- Outside Flex, shared metadata is validated and **stored but not used**;
  native widget geometry follows the existing parent (Row/Column/Scroll).
- Only direct effective Flex children are items. Nested Flex begins another
  formatting context, not inheritance of item constraints into all descendants.
- Source order, `key`, focus order, accessibility order and hook order are
  unaffected by `order` (which changes layout/paint ordering according to
  the supported capability scope only).

### 2.3 Function component boundary contract

A function component used as a flex item may expose **exactly one effective
rendered root** in the initial release. Logical component boundaries are
transparent for native widget ownership but preserve component identity,
hooks and layout metadata.

- One rendered root: its measured layout box satisfies the outer flex-item
  contract while preserving the component's own identity.
- Multiple roots, fragment with multiple effective roots, or a changing root
  cardinality unsupported by this phase: deterministic
  `UnsupportedFlexItemBoundary`-style diagnostic before geometry commit.
- A component whose root changes during rerender must revalidate this rule.
- No automatic copying to the first rendered child, no implicit native wrapper
  and no mutation of hook execution order.
- Empty roots need separate policy; until specified, treat them as unsupported
  flex-item boundaries rather than fabricating intrinsic dimensions.

~~~mermaid
flowchart TD
    A["VNode: component props + layout metadata"] --> B["Closed LayoutPropsResolver"]
    B --> C["Existing component validator"]
    B --> D["Shared FlexItemStyle validator"]
    B --> E["Unknown props => error"]
    C --> F["Native adapter: component props only"]
    D --> G{"Effective direct Flex child?"}
    G -- "No" --> H["Preserved and inert"]
    G -- "Yes" --> I{"Function component root count = 1?"}
    I -- "No" --> X["Boundary capability error"]
    I -- "Yes / native leaf" --> J["Layout item snapshot"]
    J --> K["Pure SFLE engine"]
~~~

### 2.4 Illustrative markup (not implemented)

~~~xml
<Flex direction="row" wrap="wrap" gap={16} width="100%">
    <Image source="logo.png" width={48} layout_width="25%"
           flex_shrink={0} />
    <UserCard layout_min_width={0} flex_grow={1} />
</Flex>
~~~

`Image.width` still denotes its existing widget/image dimension. The
`layout_width` value governs the surrounding Flex item box. They may
interact through the intrinsic measurement contract, but their meanings
must never be silently conflated.

## 3. Typed lengths and definite-size model (D-F1.7)

### 3.1 Immutable discriminated values

`Length` is a **closed tagged union**, *not* a loosely typed
`str | float | None` passed to the computation core:

| Tag | Payload | Meaning |
| --- | --- | --- |
| `PX` | finite f64 logical px | Numeric size or signed margin |
| `PERCENT` | finite fraction (e.g. 0.5) | Unresolved ratio with property-specific base |
| `AUTO` | none | Automatic CSS size |
| `MIN_CONTENT` | none | Intrinsic minimum |
| `MAX_CONTENT` | none | Intrinsic maximum |
| `FIT_CONTENT` | none | Intrinsic fit-content keyword where supported |
| `CONTENT` | none | CSS flex-basis: content; distinct from auto |
| `NONE` | none | Unbounded maximum constraint |
| `NORMAL` | none | Property-dependent 'normal' keyword if exposed |

A tag may carry a numeric payload **only** for `PX`/`PERCENT`.
Constructors reject bool, NaN and infinities. Canonical normalization uses
logical px and fractional percentages. Signed values are validated by
property, not by a global length type.

`Length` represents a *specified/computed style expression*. The engine
must separately represent:

- `AvailableSize(value, definite)`: available containing-block dimension
  and CSS definiteness; definite zero is meaningful.
- `ResolvedSize(value, definite, origin)`: a used numeric dimension,
  pending value or intrinsic resolution; never confuse absence with zero.
- `IntrinsicSizes(min_content, max_content, preferred, baseline)`: supplied
  by the renderer-specific measurement protocol.
- `BoxEdges(top,right,bottom,left)`: four individually typed lengths where
  permitted, resolved with correct containing-block reference rules.

`calc()`, `min()`, `max()`, `clamp()`, `em`, `rem`, `vw`, `vh`, and
CSS variables are **out of the initial value grammar**. Their admission
requires explicit parser and engine contracts; do not silently coerce them.

### 3.2 Property-specific grammar and defaults

| Property family | Admitted semantic kinds | Notes |
| --- | --- | --- |
| `layout_width`/`layout_height` | PX, PERCENT, AUTO, supported intrinsic | Nonnegative resolved size; no NONE |
| `layout_min_*` | PX, PERCENT, AUTO, supported intrinsic | Main-axis flex-item auto minimum is contextual |
| `layout_max_*` | PX, PERCENT, NONE, supported intrinsic | NONE means no upper bound |
| `flex_basis` | PX, PERCENT, AUTO, CONTENT, supported intrinsic | CONTENT != AUTO; 0% != 0px for definiteness |
| `gap`, `row_gap`, `column_gap` | nonnegative PX, supported PERCENT | Cyclic percentage handling is property-specific |
| `layout_padding` / container `padding` | nonnegative PX/PERCENT | Percentage base is containing block's inline size |
| `layout_margin` | signed PX/PERCENT, AUTO | Negative margin permitted; margin collapse prohibited for flex items |
| `layout_border_*` | nonnegative PX | Border style/painting integration gated |
| `layout_box_sizing` | content-box, border-box | Determines dimension box, not percentage base |

The source may use `24`, `"24px"`, `"50%"`, `"auto"`, or supported
intrinsic keywords; after parsing all variants are normalized to tagged
values. Quoted CSS-like lengths are **data**, never executable source.

## 4. CSS box model — committed semantics

### 4.1 Four boxes and their containment

~~~mermaid
flowchart TD
    M["Margin box"] --> B["Border box"]
    B --> P["Padding box"]
    P --> C["Content box"]
    C --> I["Intrinsic measured content"]
~~~

The nesting diagram expresses box ownership, **not** a layout processing
order. Rectangles use logical top-left coordinates and floating-point sizes.

For horizontal sizing, with left/right sums `PLR` (padding), `BLR`
(border), `MLR` (margin):

- `border_box_width = content_width + PLR + BLR`.
- `outer_width = border_box_width + MLR`.
- With `content-box`, a specified width determines content width; with
  `border-box`, it determines border-box width.
- If border-box sizing would leave a negative content dimension, clamp the
  used content width to zero under the relevant CSS sizing rules and
  re-evaluate the border-box result accordingly; **never** create negative
  physical boxes.
- The same relationships hold vertically, subject to the corresponding
  resolved top/bottom edges.
- `margin` may be negative. The outer margin rectangle may therefore
  have dimensions smaller than the border box or cross its edges;
  diagnostics must preserve the signed margins.
- Flex item margins **do not collapse**, including adjacent items.
- `auto` margins can consume available free space as prescribed by
  Flexbox. They are not globally equivalent to zero during alignment.
- Logical `gap` belongs to the container's **inter-item or inter-line**
  spacing, not to either item's border/padding/margin box; it does not
  collapse with margins.

### 4.2 Box-sizing and min/max clamps

- Resolve the declared `layout_width`/`layout_height`, min/max constraints
  and flex base according to the **appropriate sizing box**.
- Avoid applying border/padding subtraction twice when calculating the
  hypothetical main size, flex base size and post-flexing final size.
- Keep a separate intrinsic *content* measurement from the outer margin
  measurement used for flex line fitting.
- In the main axis, an auto minimum for a flex item with non-scrollable
  overflow is generally content-based (subject to replaced/non-replaced
  and transferred size suggestions). For a main-axis scroll container the
  automatic minimum is zero under the applicable Flexbox rule.
- A PSX `Scroll` widget's interaction/viewport behavior is not identical
  to a CSS overflow box by assumption. The renderer adapter must expose
  accurate overflow/scroll-container classification to apply this rule.
- Preferred sizes and min/max constraints use CSS order of operations,
  including minimum-size precedence in conflicts. Naively clamping a
  raw `flex_basis` in isolation is not sufficient.

## 5. Percentage resolution: precise reference rules

### 5.1 Per-property reference axis

Assume initial horizontal writing mode; writing modes/RTL remain D-F1.8.

| Property | Percentage reference | If reference indefinite |
| --- | --- | --- |
| `layout_width` | containing block's **inline size** (physical width in horizontal writing) | preserve unresolved; apply CSS auto/cyclic sizing rule for the context |
| `layout_height` | containing block's **block size** (physical height) | retain unresolved and apply CSS sizing rule; do not invent viewport height |
| `layout_min_width`/`max_width` | containing block's inline dimension | apply CSS sizing fallback where specified |
| `layout_min_height`/`max_height` | containing block's block dimension | apply CSS sizing fallback where specified |
| `flex_basis` | flex container's **main size** | CSS used flex basis becomes content-based when main size indefinite |
| `layout_margin_{top,right,bottom,left}` | containing block's **inline size**, for all four sides | apply cyclic/intrinsic contribution rules; retain source expression |
| `layout_padding_{top,right,bottom,left}` | containing block's **inline size**, for all four sides | apply cyclic/intrinsic contribution rules; retain source expression |
| `row_gap`/`column_gap` | corresponding content-box dimension of the **gap-owning** layout container | cyclic percentage gaps contribute as zero to intrinsic size where CSS specifies, then resolve for final layout where permitted |

In particular, a **10% top padding with 400px containing-block width is
40px**, not 10% of the block's height, in horizontal writing mode.
Likewise, a `flex_basis="50%"` uses the *main* axis, which is height for
column direction.

CSS percentage resolution may involve cycles, intrinsic contribution rules
and subsequent passes. It is **not** generally valid to say "if indefinite,
percentage = zero" or "all indefinite percentages = auto".

### 5.2 Definite size is semantic, not merely a numeric flag

~~~mermaid
flowchart TD
    A["Specified PERCENT length"] --> B["Select property-specific percentage base"]
    B --> C{"CSS reference is definite?"}
    C -- "Yes" --> D["Resolve percentage using reference"]
    C -- "No" --> E{"CSS special rule?"}
    E -- "flex-basis with indefinite main size" --> F["Use content-based flex basis"]
    E -- "cyclic percentage intrinsic phase" --> G["Apply prescribed intrinsic contribution"]
    E -- "other unresolved size" --> H["Preserve pending reference / sizing rule"]
    D --> I["Resolved used dimension"]
    F --> I
    G --> J["Intrinsic pass output"]
    H --> K["Constraint-dependent subsequent pass"]
~~~

**CSS Flexbox definiteness may arise during layout**: for example, a
flex item's post-flexing main size can be treated as definite under the
conditions in the Flexbox definiteness rules. The engine therefore must
support a staged measurement/layout protocol and cannot classify every
percentage once during parsing.

### 5.3 Calculated examples

| Scenario | CSS-compatible interpretation |
| --- | --- |
| Flex container content width 400, item `layout_width="50%"` | width 200 logical px, before box-sizing/min-max effects |
| Containing inline size 400, item `layout_padding_top="10%"` | top padding 40 logical px (even if containing block height differs) |
| Flex row definite main width 500, item `flex_basis="20%"` | main-axis base reference 100px before algorithmic flexing |
| Flex column main height indefinite, item `flex_basis="20%"` | percentage basis cannot use arbitrary viewport height; use CSS content-based rule |
| Percentage `row_gap` during intrinsic sizing | cyclic contribution rule, not unconditional conversion of final gap to zero |
| `layout_min_width="auto"` on non-scrollable flex item | CSS content-based automatic minimum in applicable circumstances |
| `layout_min_width=0` | explicitly allows main-axis shrink to zero subject to other applicable constraints |

### 5.4 Capability staging and errors

Because D-F1.3 approves **progressive** support, a phase may mark particular
percentage/intrinsic combinations `UNSUPPORTED_CSS_FEATURE`. It must not
quietly compute a non-CSS substitute. Every supported combination must
behave normatively; defer complex cycles if their correct rules are not
implemented.

## 6. Renderer/native boundary and Rust-readiness

~~~mermaid
sequenceDiagram
    participant V as PSX VNode/Markup
    participant R as Shared Props Resolver
    participant M as Native Measurer (UI thread)
    participant C as Python Coordinator
    participant P as Pure Layout Core (Python or Rust)
    participant A as Native Geometry Applicator
    V->>R: Raw specified component + layout props
    R-->>C: Frozen typed layout style
    R-->>A: Component props only
    C->>M: Intrinsic measurement constraints
    M-->>C: Immutable measured content + baseline
    C->>P: Batched typed layout input + definiteness
    P-->>C: Floating-point boxes + diagnostics
    C->>A: Commit geometry on UI thread
~~~

Contractual boundary:
- **One engine semantics**, regardless of Python or Rust implementation.
- Only tagged lengths, plain numeric constraints, stable IDs and intrinsic
  measurement snapshots cross into the pure computation core.
- Prefer `f64` for numerical layout internals, with validated finite
  values; do not quantize every intermediate step.
- Numeric rounding and origin translation occur in backend geometry
  application, not arbitrary points in the Flexbox algorithm.
- No user Python callables, GUI handles, native widgets or OS APIs inside
  the pure math algorithm.
- Percent unresolved values and explicit definiteness must survive the
  Python-to-Rust boundary.

## 7. Validation examples (semantic expectations, not tests added)

| Input | Expected behavior |
| --- | --- |
| `Text(flex_grow=2)` outside Flex | Validate, preserve, do not apply |
| `Text(flex_gorw=2)` | Unsupported-property diagnostic |
| `Text(flex_grow=-1)` | Validation error |
| `Text(flex_grow=True)` | Validation error |
| `Image(width=48, layout_width="50%")` in Flex | Native width remains 48; outer flex item width uses resolved layout style |
| `Scroll(height=200, layout_height="50%")` | Native viewport prop unchanged; flex item sizing follows CSS context |
| Functional component with one rendered root | Single logical flex item, hooks/refs unchanged |
| Functional component with two rendered roots | Explicit unsupported boundary error in initial release |
| Nested Flex inside Flex | Parent sizes nested Flex as item; inner Flex sizes its own direct children |
| `layout_margin_top="10%"` in 400px inline containing block | 40px, even if block height is 200px |
| `flex_basis="50%"` in indefinite column main axis | CSS content-based used flex-basis |
| `layout_padding_top=-2` | Reject |
| `layout_margin_left=-2` | Accept signed margin |
| `layout_width="calc(100% - 20px)"` | Unsupported grammar error |
| `layout_width=float("nan")` | Validation error |

**No test suite is added or run by this design-only decision record.**

## 8. Transition to the remaining F1 decisions

D-F1.6 and D-F1.7 are now **architecturally closed**, with the following
implementation-sensitive clarifications reserved for the corresponding F2
capability gates: functional root diagnostics, actual available native
border-box measurement, optional border painting, CSS intrinsic keyword
coverage and cyclic percentage support.

The next decisions are:
- **D-F1.8:** direction/writing mode/RTL scope.
- **D-F1.9:** explicit supported-feature matrix and diagnostics policy.
- **D-F1.10:** Row, Column, Scroll compatibility and mixed nesting.
- **D-F1.11:** geometry comparison fixtures and numeric tolerances.
- **D-F1.12:** immutable measurement snapshots, caching, scheduling.
- **F1-RUST:** computation backend priority, packaging and fallback.

Do not treat architecture approval as completion of the F2 implementation
or browser conformance certification.
