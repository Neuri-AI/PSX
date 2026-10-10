# SFLE — Shared Flex Layout Engine

> **Status:** architecture specification / proposed design. **Not implemented.**
> This document is a design and documentation baseline, not an assertion that
> the current PSX runtime already supports these behaviors.

## 1. Purpose and scope

**SFLE (Shared Flex Layout Engine)** is the proposed platform-independent layout
calculator for PSX. Its primary goal is to **match the geometry produced by a web
browser implementing CSS Flexible Box Layout**, given equivalent layout inputs,
across Qt, Kivy, Tkinter, and Headless.

SFLE is **not** a wrapper around each toolkit's horizontal/vertical layout manager.
Native layout managers may produce different intrinsic sizes, wrapping, or
free-space allocation; therefore, PSX must own the flex calculations and use
native renderers mainly to measure content and apply the resulting geometry.

A high-fidelity layout means matching element bounds, line breaks, spacing,
alignment, overflow, and resize behavior—not guaranteeing pixel-identical
glyphs, native button styles, antialiasing, or system-specific font metrics.

The authoritative semantic reference is the CSS Flexible Box Layout Module
(Level 1), supported by the CSS Box Sizing, CSS Sizing, CSS Align, and CSS Box
Model specifications. An actual browser (initially Chromium) is the practical
reference implementation for comparison fixtures.

Reference: https://www.w3.org/TR/css-flexbox-1/

### 1.1 Goals

- Resolve flex direction, axis mapping, item order, wrapping, flexible lengths,
  minimum/maximum sizing, alignment, margins, padding, gaps, and overflow.
- Compute geometry deterministically from explicit constraints and measured
  intrinsic sizes without coupling the algorithm to any UI toolkit.
- Give Qt, Kivy, Tkinter, and Headless the **same geometry decisions**.
- Avoid recreating widgets while recalculating layout after resize or rerender.
- Provide inspectable box data to PSX Playground's Visual Layout Inspector
  and the future visual UI builder.
- Explicitly document deviations instead of silently claiming CSS compliance.

### 1.2 Non-goals for the initial implementation

- A full HTML DOM or CSS cascade.
- CSS Grid's independent track-sizing algorithm (a future, separate phase).
- Arbitrary CSS positioning, float layout, fragmentation, writing modes,
  text line layout, or browser-native painting.
- Guaranteed pixel-identical fonts and native widget appearance.
- Automatic support for browser features not explicitly admitted to the PSX
  portable API.

## 2. Proposed system architecture

~~~mermaid
flowchart TD
    A["PSX markup / Python Flex component"] --> B["Validated layout style"]
    V["PSX reconciliation tree"] --> C["Layout tree / node identity"]
    B --> C
    C --> D["SFLE layout coordinator"]
    D --> E["Intrinsic measurement protocol"]
    E --> Q["Qt measurer"]
    E --> K["Kivy measurer"]
    E --> T["Tkinter measurer"]
    E --> H["Headless fixture measurer"]
    Q --> F["SFLE Flexbox algorithm"]
    K --> F
    T --> F
    H --> F
    D --> F
    F --> G["Geometry tree + diagnostics"]
    G --> R["Renderer geometry applicators"]
    R --> Q2["Qt native widgets"]
    R --> K2["Kivy native widgets"]
    R --> T2["Tkinter native widgets"]
    G --> I["Playground Inspector / UI Builder"]
    G --> J["Headless geometry snapshots"]
~~~

**Ownership contract:**

| Responsibility | Owner |
| --- | --- |
| Parse and validate portable layout properties | PSX component contracts |
| Preserve keyed node/widget identity | PSX reconciler |
| Measure text/native controls under available constraints | Renderer measurer |
| Calculate flex basis, lines, sizing, gaps and alignment | SFLE |
| Write geometry to actual widgets | Renderer geometry applicator |
| Schedule relayout and prevent recursive loops | Layout coordinator |
| Visualize dimensions, gaps and box boundaries | Layout Inspector |
| Compare measured geometry with browser | Conformance harness |

The native widgets remain the source of truth for actual intrinsic metrics,
but **SFLE** decides their final positions and allocation of available space.

## 3. Layout data model (proposal, not a final public API)

Each layout node supplies:

- **identity:** stable PSX instance key / node identifier
- **style:** display semantics, direction, wrap, sizing, min/max constraints,
  flex grow/shrink/basis, gaps, padding, margins, alignment and order
- **children:** ordered layout-node references (not native widget ownership)
- **measurer:** callback for intrinsic dimensions and baseline as needed
- **constraints:** available inline/block dimensions and whether they are definite
- **metadata:** diagnostic labels and renderer-neutral capabilities

A measurement request should carry the relevant size constraints and produce
measured min-content/max-content/preferred dimensions, baseline and any relevant
aspect-ratio information. The protocol must distinguish **unknown** from **zero**.
Percentage resolution depends on a *definite* containing size.

A computed layout result should be immutable for a single layout pass:

~~~text
LayoutResult
  node_id
  border_box: { x, y, width, height }
  padding_box: { x, y, width, height }
  content_box: { x, y, width, height }
  margin_box: { x, y, width, height }
  baseline: optional number
  children: [LayoutResult...]
  overflow: { x, y }
  diagnostics: [...]
~~~

**Coordinates:** logical top-left layout coordinates, independent of device
pixel ratio. Adapt to toolkit-specific origins (notably Kivy's vertical axis)
when applying geometry. Round at the renderer boundary, not during each
intermediate flex calculation; document fractional-pixel behavior.

## 4. CSS-compatible concepts and defaults

A PSX Flex node should distinguish **container properties** from **item
properties**. The following is a proposed semantic coverage matrix, not a
final naming decision for the Python/markup surface.

| CSS concept | Semantic behavior to preserve |
| --- | --- |
| flex-direction | row, row-reverse, column, column-reverse; defines main axis |
| flex-wrap | nowrap, wrap, wrap-reverse; forms flex lines |
| flex-grow | proportional allocation of positive remaining free space |
| flex-shrink | scaled shrink factors based on flex base sizes |
| flex-basis | base size for flex calculations; auto differs from zero |
| justify-content | alignment/distribution in the main axis |
| align-items / align-self | cross-axis item alignment, including stretch |
| align-content | distribution of flex lines when applicable |
| gap / row-gap / column-gap | fixed gutters; direction-sensitive line/item gaps |
| order | layout order without mutating PSX reconciliation identity |
| margins | outer spacing, including auto margin behavior |
| padding/border | content vs border box and available free space |
| min/max width/height | sizing bounds and flexible-size freezing |
| width/height | definite/auto/percentage sizing semantics |
| overflow | layout overflow reporting versus viewport clipping/scrolling |

Important CSS compatibility details:

1. The initial main size of a flex item is **not necessarily its final size**.
2. Negative free space is distributed using **scaled flex-shrink factors**, not
   unscaled shrink weights.
3. Flex items have an **automatic minimum size** in relevant circumstances;
   blindly treating auto minimum size as zero breaks common browser layouts.
4. Percentage lengths may remain unresolved when the containing size is
   indefinite; do not substitute the viewport dimension without a rule.
5. Flex lines are independent: free-space distribution happens per line.
6. Main/cross axes differ from physical horizontal/vertical directions;
   reverse directions affect placement, not tree identity.
7. **align-content** concerns multiple lines, not individual item alignment.
8. Auto margins can absorb free space ahead of ordinary alignment.
9. Item intrinsic dimensions depend on text wrapping and available cross/main
   constraints. Fixed estimates are insufficient for fidelity.
10. Box sizing, aspect ratio, and min/max constraints affect base-size and
    hypothetical-size calculations.

## 5. Algorithm — from constraints to final geometry

The implementation should follow the ordering and definitions from the Flexbox
specification, including its iterative resolve-flexible-lengths procedure. The
sequence below is a conceptual map; details must be specified against the
normative algorithm before coding.

~~~mermaid
flowchart TD
    A["Container receives available size"] --> B["Resolve axis, box model, definite sizes"]
    B --> C["Measure children / resolve flex bases"]
    C --> D["Calculate hypothetical main sizes"]
    D --> E{"Wrapping enabled?"}
    E -- "Yes" --> F["Collect items into flex lines"]
    E -- "No" --> G["Place items in one line"]
    F --> H["Resolve flexible lengths per line"]
    G --> H
    H --> I["Determine hypothetical cross sizes"]
    I --> J["Calculate line cross sizes and baselines"]
    J --> K["Align lines and stretch eligible items"]
    K --> L["Resolve main-axis alignment and auto margins"]
    L --> M["Resolve item cross-axis alignment"]
    M --> N["Produce geometry + overflow"]
    N --> O["Apply positions; report inspector data"]
~~~

### 5.1 Resolve axes and containing geometry

Given container dimensions, padding, borders, and layout style:

- Map logical main and cross axes (direction and reverse flags).
- Determine whether the main/cross container sizes are definite.
- Subtract non-content spacing only when the relevant sizing rule requires it.
- Preserve logical coordinates until geometry application.
- Apply min/max size clamps according to CSS sizing order, not arbitrarily
  before every operation.

### 5.2 Establish flex bases and hypothetical sizes

For each item, determine:

- Its **flex base size**, using flex-basis, item preferred size, and the CSS
  rules for content-based automatic sizing.
- Its **hypothetical main size**, derived by clamping the flex base size with
  resolved min/max constraints.
- Whether an intrinsic remeasurement or baseline query is needed.

A CSS-like *flex-basis: 0* is not the same as *flex-basis: auto*; this distinction
must remain observable in the public PSX model.

### 5.3 Form flex lines

For wrapping containers, place items in source/order-modified order, collecting
as many as can fit subject to hypothetical outer main sizes and item gaps.
Single items too large for a line still form a line of their own. For nowrap,
all items remain on the same line even when they overflow.

~~~mermaid
flowchart LR
    A["Container width: 400"] --> B["Item A: 120"]
    B --> C["Item B: 150"]
    C --> D["Item C: 160"]
    D --> E["A+B fit; C starts next line with wrap"]
~~~

Note: dimensions above are illustrative and exclude margins and gaps; concrete
fixtures must account for the *outer* hypothetical sizes and gutters.

### 5.4 Resolve flexible lengths per line

Determine original free space after flex bases, gutters and margins. For
positive space, use grow factors. For negative space, use shrink factors
**scaled by each item's base size**. Clamp by min/max constraints, freeze
violating items, and repeat distribution until the line is resolved.

~~~mermaid
flowchart TD
    A["Compute line free space"] --> B{"Positive or negative?"}
    B -- "Positive" --> C["Select grow factors"]
    B -- "Negative" --> D["Select scaled shrink factors"]
    C --> E["Distribute space to unfrozen items"]
    D --> E
    E --> F["Apply min/max clamps"]
    F --> G{"Unfrozen items and violations?"}
    G -- "Yes" --> H["Freeze constrained items"]
    H --> E
    G -- "No" --> I["Final main sizes"]
~~~

**Example — grow:** 400 units available; items have bases 100 and 100, gap 20,
grow factors 1 and 2. Remaining space is 180; ideal target widths are 160 and
220 respectively, absent min/max clamps and other adjustments.

**Example — shrink:** item bases 200 and 100, container 250, no gap, shrink
factors 1 and 1. There is 50 units of negative space; scaled weights are 200
and 100, yielding approximate sizes 166.67 and 83.33, subject to constraints.

### 5.5 Determine line cross sizes and align items

After main sizes are resolved:

- Determine each item's hypothetical cross size, potentially measuring it
  again given its final main-axis constraint.
- Calculate each flex line's cross size, including baseline requirements.
- Distribute extra cross space between lines via align-content, if applicable.
- Stretch eligible auto-sized items to line cross size, respecting min/max.
- Position individual items via align-items / align-self and auto margins.
- Translate final placements for reverse directions and writing-mode scope.

### 5.6 Finalize bounds and overflow

Output final border/content/margin rectangles, available clipping/overflow
extents, line metadata, baselines and diagnostics. No geometry result may
silently discard a constraint or mutate reconciler keys.

## 6. Responsive relayout and lifecycle

~~~mermaid
sequenceDiagram
    participant P as Parent/window
    participant R as PSX reconciler
    participant C as SFLE coordinator
    participant M as Renderer measurer
    participant E as SFLE engine
    participant W as Native widgets
    P->>C: Resize / available-size changed
    R->>C: Style or child-tree changed
    C->>C: Dirty nodes and ancestor invalidation
    C->>M: Measure intrinsic sizes under constraints
    M-->>C: Size and baseline data
    C->>E: Layout tree, measurements, constraints
    E-->>C: LayoutResult with stable node IDs
    C->>W: Apply changed geometry only
    C-->>R: Commit layout (no remount)
~~~

The coordinator must:

- Batch invalidations with the renderer's UI event loop.
- Avoid reentrant measurement/layout/write cycles.
- Cache measurements by node identity, style, available constraints,
  content/font/theme versions and DPI-sensitive inputs.
- Invalidate on text changes, style changes, font or DPI changes, parent resize,
  children insertion/removal/reordering and relevant intrinsic-size updates.
- Retain keyed widget identities, state, hooks, focus and scroll offsets where
  the existing reconciler contracts allow.
- Detect oscillation or repeated dirty measurements; emit diagnostics rather
  than entering an infinite layout loop.

Nested Flex containers should be measured under constraints from their parents,
then relaid out when final space differs from hypothetical space.

## 7. Renderer integration

### 7.1 Qt / PySide / PyQt

- Query native size hints, min/max constraints, font metrics and baselines.
- Prevent native QBoxLayout logic from overriding SFLE's calculated geometry.
- Apply logical results via native geometry APIs on the UI thread.
- Respect widget style changes, size policies, high-DPI scaling and focus.
- Do not assume QSS styling behaves exactly like CSS layout.

### 7.2 Kivy

- Convert top-left logical geometry into Kivy's coordinate orientation.
- Account for Kivy size_hint and native layout controls; disable conflicting
  automatic sizing where SFLE is authoritative.
- Use intrinsic/native size hooks and schedule writes appropriately.
- Preserve touch, event binding and scroll behavior while relaying out.

### 7.3 Tkinter

- Derive requested/native sizes without relying on pack/grid/place's distinct
  space-distribution algorithms for CSS Flex semantics.
- Apply explicit geometry via a contained placement strategy; document geometry
  manager interactions and constraints.
- Bind configuration invalidation carefully to avoid feedback loops.
- Respect Tk scaling, theme-driven native widget sizes and window lifecycle.

### 7.4 Headless

- Accept deterministic intrinsic-size fixture providers.
- Emit exact logical rectangles, lines, overflow and calculation diagnostics.
- Provide a testable baseline before introducing toolkit-specific rendering.
- Reuse the same result model in the Playground geometry inspector.

## 8. Flex and Grid relationship

The proposed responsive **12-column Flexbox Grid** should reuse SFLE's row
wrapping, sizing and alignment semantics. It is **not CSS Grid**. The grid's
spans, offsets, gutters and breakpoints are a separate public API layer whose
layout constraints are translated into SFLE inputs.

A future **CSS Grid-like track layout** may use the same measurement and output
protocol but requires a separate track-sizing algorithm. It should not be
implemented as an inaccurate Flexbox emulation.

~~~mermaid
flowchart TD
    A["Portable measurement + geometry protocol"] --> B["SFLE Flexbox"]
    A --> C["Future CSS Grid track engine"]
    B --> D["Responsive 12-column Flexbox Grid"]
    B --> E["PSX Flex"]
    D --> F["Playground Inspector"]
    E --> F
    C --> F
~~~

## 9. Conformance strategy

Use browser geometry as the reference, rather than subjective screenshots
alone. A fixture should include HTML/CSS, viewport size, intrinsic content,
font selection, expected DOMRects and reference screenshots. Native fixtures
should declare any unavoidable content/font measurement differences.

**Coverage:**

1. Grow/shrink/flex-basis interactions, including zero and auto.
2. Min/max constraints and automatic minimum sizes.
3. Single line, multiple lines, wrap-reverse and reverse direction.
4. Space-between/around/evenly and start/end/center alignments.
5. Cross-axis stretch, baseline, align-self and align-content.
6. Auto margins, padding, borders and gaps.
7. Percentage dimensions with definite and indefinite ancestors.
8. Intrinsic sizes, text wrapping, aspect ratio and oversized content.
9. High-DPI coordinates and fractional rounding.
10. Resize/reflow, nested layouts, identity preservation and overflow.

~~~mermaid
flowchart LR
    A["Fixture: HTML/CSS + constraints"] --> B["Chromium DOMRect / screenshots"]
    A --> C["Equivalent PSX Flex fixture"]
    C --> D["Headless SFLE geometry"]
    C --> E["Qt / Kivy / Tk geometry"]
    B --> F["Compare rects + layout lines"]
    D --> F
    E --> F
    F --> G{"Within approved tolerances?"}
    G -- "Yes" --> H["Pass"]
    G -- "No" --> I["Diagnostic diff + deviation record"]
~~~

**Pass criteria (to approve in F1):** use geometry tolerances defined per
measurement class and high-DPI scale. Prefer exact logical geometry in Headless
when intrinsic inputs match, and explicit tolerances for native widget
measurements. A screenshot match alone is not evidence of algorithm fidelity.

## 10. Documentation and implementation deliverables

Before coding, approve and maintain these documents (they may initially be
sections of this file and later split):

| Document | Required content |
| --- | --- |
| SFLE architecture | ownership, boundaries, modules, lifecycle, diagrams |
| Public Flex API | syntax, defaults, supported values, errors, examples |
| Intrinsic measurement contract | constraints, sizing, baseline, caching |
| Flex algorithm | spec mapping, phases, rounding, edge cases |
| Renderer integration guides | Qt, Kivy, Tkinter, Headless mapping |
| Browser conformance matrix | fixtures, tolerances, documented deviations |
| Inspector geometry protocol | computed boxes, lines, gutters, diagnostics |
| Performance notes | invalidation, complexity, benchmarks, memory behavior |

## 11. Decisions requiring explicit approval

- Public component design: Flex/FlexItem vs enriched Row/Column, and where
  child flex properties live.
- Naming convention: CSS-like hyphenated markup attributes or Python-friendly
  snake_case props, including aliases.
- Initial CSS support subset and detailed defaults.
- Percentage, intrinsic-size, auto-minimum-size and overflow policy.
- Whether measurement can be asynchronous or must remain UI-thread-bound.
- Initial browser fixture baseline and approved logical-pixel tolerances.
- Boundaries between SFLE, responsive Flexbox Grid and future CSS Grid.

**Implementation milestone sequence:**

F1. Approve semantics, public API, measurement protocol, and fidelity criteria.

F2. Implement backend-neutral SFLE with browser-reference geometry fixtures.

F3. Integrate Qt, Kivy, Tkinter and Headless geometry application.

F4. Implement portable responsive 12-column Flexbox Grid atop SFLE.

F5. Feed layout geometry into the Playground's Visual Layout Inspector and
future Visual UI Builder.

**Do not interpret this architecture document as implementation completion.**
