# SFLE F1 — Portable Flexbox contracts and decision record

> **Status:** F1 design specification. No runtime implementation.
> **Approved:** D-F1.1–D-F1.5 (2026-10-10).
> **Open:** D-F1.6–D-F1.12 and F1-RUST. Proposed defaults below are not
> approved until the open decisions are resolved.
>
> Architecture: [SFLE](sfle.md). Reference semantics:
> [CSS Flexible Box Layout Level 1](https://www.w3.org/TR/css-flexbox-1/).

**Detailed proposals:** [D-F1.6 shared props + D-F1.7 typed lengths](sfle-f1-props-lengths.md).
The approved direction is recorded here; component-boundary behavior, width/height
collisions, length grammar, and percentage/box-model details remain subject to
explicit approval before these contracts are frozen.

## 1. Approved decision record

| ID | Accepted decision | Consequence |
| --- | --- | --- |
| D-F1.1 | A `Flex` container and flex item properties directly on existing PSX components | Do not require `FlexItem`; preserve actual child VNodes and identity |
| D-F1.2 | Public property names in `snake_case` | Python and PSX markup share one canonical spelling |
| D-F1.3 | Incremental implementation with progressive CSS conformance | Every unsupported normative feature is reported, not silently simulated |
| D-F1.4 | Native measurement on renderer UI thread; pure layout calculation | SFLE cannot call a GUI widget from the pure computation phase |
| D-F1.5 | Strict geometry comparison plus backend-specific tolerances | Browser reference rectangles and line formation are authoritative geometry targets |

**Primary invariant:** Given equivalent measured intrinsic sizes, definite
constraints and styles, SFLE must calculate the same flex geometry regardless
of the renderer. Pixel-identical native widget appearance is not a requirement.

## 2. Public component contract — `Flex` (proposed frozen surface)

- **Node:** portable layout host, `NodeKind.HOST`.
- **Children:** `multiple`; supports zero or more ordinary PSX VNodes,
  including nested Flex and user-defined function components.
- **Events:** none introduced by Flex.
- **Identity:** existing `key` and `ref` behavior unchanged.
- **State:** no independent state store; reconciler owns child identity.
- **Native realization:** backend adapter manages a suitable native container
  but must not delegate flex distribution to a conflicting native layout manager.
- **Style scope:** a Flex container establishes the flex formatting context
  for its *direct layout children*. Descendants within nested containers are
  governed by their own parent layout system.
- **Disabled:** no new `enabled` behavior specified; should follow established
  container conventions only if explicitly adopted in D-F1.10.

### 2.1 Container properties and proposed defaults

| Public prop | Proposed default | Values / restrictions |
| --- | --- | --- |
| `direction` | `"row"` | `row`, `row-reverse`, `column`, `column-reverse` |
| `wrap` | `"nowrap"` | `nowrap`, `wrap`, `wrap-reverse` |
| `justify_content` | `"flex-start"` | `flex-start`, `flex-end`, `center`, `space-between`, `space-around`, `space-evenly` |
| `align_items` | `"stretch"` | `stretch`, `flex-start`, `flex-end`, `center`, `baseline` |
| `align_content` | `"normal"` | `normal`, `stretch`, `flex-start`, `flex-end`, `center`, `space-between`, `space-around`, `space-evenly` |
| `gap` | `0` | Nonnegative layout length |
| `row_gap`, `column_gap` | unspecified | Override corresponding gap dimensions |
| `width`, `height` | `"auto"` | Definite logical length, `auto`, or resolvable percentage |
| `min_width`, `min_height` | `"auto"` | Min-size length, `auto`, or percentage |
| `max_width`, `max_height` | `"none"` | Max-size length, `none`, or percentage |
| `padding` | `0` | Nonnegative logical box spacing |
| `key`, `ref` | `None` | Standard PSX identity/ref contracts |

All lengths are backend-neutral *logical CSS-like pixels*, not raw device
pixels. Accepting CSS-like string percentages or `auto` is a **new contract**
requiring explicit parser/validator support and definite-size resolution. CSS
logical properties, `box_sizing`, borders, margins and aspect-ratio support
must be specified under D-F1.7 before becoming public promises.

### 2.2 Child item properties directly on components

The following *layout metadata* may appear on any layout-participating
child when its effective parent establishes a Flex formatting context:

| Public prop | Proposed CSS-equivalent default | Intended semantics |
| --- | --- | --- |
| `flex_grow` | `0` | Nonnegative finite number |
| `flex_shrink` | `1` | Nonnegative finite number, scaled by flex base |
| `flex_basis` | `"auto"` | `auto`, definite length, percentage, supported intrinsic size keyword |
| `align_self` | `"auto"` | Overrides container `align_items` |
| `order` | `0` | Integer; visual layout ordering only |
| `margin` | `0` | Box margins including `auto` where supported |
| `width`, `height`, `min_*`, `max_*` | CSS-like defaults | Item preferred and constrained dimensions |

There is **no required FlexItem widget**, no inserted wrapper VNode, and no
new event contract for these properties. Flex item metadata must be retained
when an item is a function-component boundary: the final mounted host/layout
root's measurement should represent that component without changing the
component's hook boundaries or generating new keys.

**Critical compatibility constraint:** existing validators use closed
`*_PROPS` sets (for example `Text`, `Button`, `Column`, `Scroll`).
The new layout style namespace must be validated in a common layer and separated
from widget-specific props before delegation. It must not be forwarded to
native factories, swallowed by `**props` without validation, or accidentally
interpreted as component behavior. Existing names with conflicting meanings
must be resolved explicitly (notably `align`, `expand`, `spacing`,
`padding`, `width`, `height`).

**Context-sensitive validation choice pending D-F1.6:** either allow metadata
on a portable component independent of its current parent and apply it only
within a Flex context (recommended), or reject metadata outside Flex. Both
options require consistent error behavior across builders, markup and renderer
validation. Do not silently accept misspelled properties.

### 2.3 Declarative syntax (illustrative only)

~~~xml
<Flex direction="row" wrap="wrap" gap={16}
      justify_content="space-between" align_items="center"
      width="100%">
    <Text flex_grow={1} flex_basis={200}>Left</Text>
    <Column flex_grow={2} flex_basis={300} min_width={0}>
        <Text>Right</Text>
        <Button>Continue</Button>
    </Column>
</Flex>
~~~

This sample is a **target API**, not executable under the current markup
compiler. In particular, `width="100%"` and the flex properties require new
contracts. It does not imply the compiler supports arbitrary Python
expressions, loops, or JSX conditionals.

## 3. Internal contracts — proposed schema

These are **design types, not Python implementations**. Define these
conceptually before choosing Python dataclasses or Rust-compatible structs.

| Contract | Required data | Guarantee |
| --- | --- | --- |
| `FlexStyle` | validated container style and box model | immutable, renderer-neutral semantics |
| `FlexItemStyle` | normalized child flex metadata | no mutation of the original VNode |
| `LayoutConstraints` | available width/height, definiteness flags, writing direction scope | distinguish undefined from numeric zero |
| `MeasureRequest` | node ID, measurement mode, per-axis limits, style/content identity | measurable on UI thread |
| `MeasureResult` | intrinsic min/max/preferred bounds, baseline, aspect-ratio where applicable | explicit unavailable/missing values |
| `LayoutInput` | stable IDs, child hierarchy, styles, constraints and cached measurements | no GUI handles |
| `LayoutResult` | logical rectangles, line metadata, overflow and diagnostics | immutable, deterministic per input |
| `GeometryCommit` | changed node IDs and geometry | no remount; UI-thread application only |
| `LayoutDiagnostic` | feature, node, reason, severity, backend | observable gaps in CSS support |

### 3.1 Coordinates and sizing

- Use logical top-left coordinates in SFLE; renderer adapters transform
  to native origins and device scaling.
- Defer rounding until native geometry application. Keep fractional values
  for diagnostics and conformance comparison.
- Keep `auto`, indefinite, min-content and max-content distinguishable;
  no implicit replacement of indefinite values with `0`.
- Resolve percentages only using CSS-compatible definite containing sizes.
- Use the CSS flexible-length freezing algorithm per line; do **not**
  distribute shrink using unscaled factors.
- Preserve CSS auto minimum-size behavior in the supported subset.
- A result is invalid if input data contain NaN, infinite dimensions,
  impossible constraint pairs, or unsupported CSS semantics that would change
  computed geometry without an explicit diagnostic.

### 3.2 Reconciliation / layout ordering

- `order` changes visual layout order **not** PSX reconciliation order.
- Preserve original keyed tree identity and the user's hook execution order.
- No widget creation, destruction or event rebinding solely for relayout.
- Cache intrinsic measurement by node, content, font/theme/DPI revision and
  effective constraints. Invalidation is required on corresponding changes.
- Layout computations are pure and may be executed off the UI thread **only
  after** all relevant native measurements have been captured safely.
- Avoid recursive measurement -> geometry -> resize feedback loops.

~~~mermaid
sequenceDiagram
    participant S as PSX Scheduler
    participant C as Python SFLE Coordinator
    participant M as UI-thread Native Measurer
    participant L as Pure SFLE Computation
    participant R as Renderer Applicator
    S->>C: Reconciled tree / resize invalidation
    C->>M: Measure dirty nodes with constraints
    M-->>C: Immutable measurement snapshot
    C->>L: LayoutInput snapshot
    L-->>C: Immutable LayoutResult
    C->>R: Apply changed geometry on UI thread
    R-->>S: Layout commit completed
~~~

## 4. Progressive conformance without false guarantees

Incremental development is approved (D-F1.3), **not** approximate Flexbox
semantics. Each phase must use browser-compatible rules for the features it
claims; unsupported combinations should be rejected or diagnosed.

| Proposed phase | Browser semantics targeted | Gate |
| --- | --- | --- |
| F2.A | row/column, definite sizes, gaps, simple grow/shrink | DOMRect equality within approved tolerance |
| F2.B | wrap/reverse, multi-line alignment, justify distribution | correct line membership + rectangles |
| F2.C | intrinsic sizes, min/max, auto minimum sizes, percentage resolution | constrained/nested geometry fixtures |
| F2.D | auto margins, baselines, alignment edges, aspect-ratio and overflow | reference behavior + explicit deviation list |
| F3 | Qt/Kivy/Tk/Headless native integration | geometry consistency and widget identity |
| F4 | 12-column Flexbox Grid atop established SFLE | responsive browser reference fixtures |

The phase order is **proposed**. Dependencies may require implementing
parts of intrinsic measurement earlier (for example to make basic grow/shrink
CSS-correct). Do not claim a feature supported until normative edge cases
are covered.

### 4.1 Conformance measurement and tolerances

Fixtures must capture container dimensions, normalized styles, content,
font details, measurements, browser-computed rectangles, flex-line membership,
overflow and DPI/environment metadata.

- **Headless:** aim for exact deterministic logical geometry with equivalent
  measured inputs; use a minimal numerical tolerance for floating-point output.
- **Native renderers:** report both (a) SFLE logical geometry deviation
  against Chromium and (b) applied native widget bounds deviation, separately.
- **Proposed starting thresholds for review, not approved:** numerical
  `<= 0.01` logical px for pure computation on matched intrinsic inputs,
  and `<= 1.0` logical px for native geometry after coordinate rounding.
- A difference in line membership, item order, identity or unsupported
  semantics is a failure even if screenshots look close.
- Any mismatch due to native font metrics must be attributed to measurement
  rather than dismissed as a layout-algorithm tolerance.

## 5. Native computation contract and Rust boundary

Rust acceleration remains **open F1-RUST**, not part of the five accepted
decisions. The interface must nevertheless be language-independent:

~~~mermaid
flowchart TD
    A["Python: VDOM + reconciliation"] --> B["Python: SFLE coordinator"]
    B --> M["Renderer measurement (UI thread)"]
    M --> D["Immutable layout input"]
    D --> C["Pure compute interface"]
    C --> P["Python reference candidate"]
    C --> R["Rust / PyO3 candidate"]
    P --> O["LayoutResult"]
    R --> O
    O --> B
    B --> E["Renderer geometry commit (UI thread)"]
~~~

- No Qt/Kivy/Tk objects or Python callbacks in the pure computation input.
- Batch data crossing Python/native boundaries; avoid per-item round-trips.
- Native computation may release the GIL only with immutable snapshots and
  no pending GUI access.
- Rust implementation must preserve the same contract and reference output;
  no separate, weaker layout semantics.
- Assess native wheels and frozen packaging across PSX/Qyro target platforms.
- Benchmark end-to-end resize, cold mount, warm relayout, nested wrapping,
  and intrinsic measurement costs before locking an implementation language.

## 6. Remaining decisions requiring sign-off

| ID | Topic | Recommended resolution | Why not yet frozen |
| --- | --- | --- | --- |
| D-F1.6 | Parent-independent child metadata validation | Accept recognized flex metadata on portable children; apply only under a Flex parent, preserve in other contexts | Requires exact contract integration strategy and handling function components |
| D-F1.7 | Lengths and box model | CSS-like `auto`, lengths in logical px, percentage only for definite containers; specify `box_sizing`, margins/borders and sizing keywords | Needed for browser-fidelity sizing and compatibility with existing `width`/`height` |
| D-F1.8 | Direction and writing modes | v1 horizontal writing mode, LTR; separate CSS writing-direction scope from row/column direction; document expansion plan | Flexbox start/end behavior depends on writing mode |
| D-F1.9 | Unsupported CSS features | Closed feature-gated validation: reject unsupported combinations or emit explicit diagnostics, never silently approximate | Progressive fidelity requirement |
| D-F1.10 | Existing `Row`/`Column`/`Scroll` interoperability | Keep current semantics unchanged; only a new Flex formatting context invokes SFLE; child layout metadata is independent | Prevent breaks to stable existing components |
| D-F1.11 | Numeric tolerances | Start with 0.01 logical px compute and 1.0 logical px native as **candidate**, then calibrate on fixtures | Reference font, DPI and rounding may shift the practical threshold |
| D-F1.12 | Measurement/cache and nested boundaries | Sync UI-thread measurement, immutable snapshots, invalidation by style/content/constraint/font/theme/DPI revisions | Need concrete request/response fields and lifecycle semantics |
| F1-RUST | Rust priority and packaging | Define pure ABI now; use Rust if profile justifies it, or adopt it as primary if packaging/fallback support is approved | Performance alone cannot guarantee deployment portability |

## 7. Completion criteria for F1 (no runtime coding)

- Approve D-F1.6–D-F1.12 and F1-RUST.
- Freeze container/item property names and defaults against CSS reference.
- Freeze parent-aware validation and `Row`/`Column`/`Scroll` interoperability.
- Freeze definite/indefinite measurement protocol, geometry and lifecycle.
- Agree a browser fixture matrix and geometry comparison thresholds.
- Document implementation boundaries, packaging consequences and deviations.
- Update [SFLE architecture](sfle.md) with finalized outcomes.
- Start F2 only after explicit architecture approval.

**This file is a contract proposal. It does not implement Flex, add
automated tests, change component behavior or certify CSS support.**
