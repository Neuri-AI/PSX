# SFLE F1 — Final architecture decision record and implementation gate

> **Status:** all F1 architectural decisions D-F1.1–D-F1.12 and F1-RUST are
> **approved as of 2026-10-10**. F1 documentation and contracts are ready for
> formal sign-off. **F2 has NOT been authorized or started.**
>
> This document defines the target architecture and acceptance gates. It does
> not imply that PSX currently implements SFLE, that tests have run, or that
> CSS geometry conformance has been demonstrated.
>
> Normative context: [SFLE architecture](sfle.md),
> [F1.6/F1.7 CSS box model and percentages](sfle-f1-box-model.md),
> [F1 contracts](sfle-f1-contracts.md);
> [CSS Flexbox Level 1](https://www.w3.org/TR/css-flexbox-1/).

## 1. Approved decisions

| ID | Approved choice | Required architectural effect |
| --- | --- | --- |
| D-F1.1 | `Flex` + flex props on existing components | No required `FlexItem`; stable VNode and hook identities |
| D-F1.2 | `snake_case` | Canonical Python and markup property spelling |
| D-F1.3 | Incremental CSS-conformant core | Feature gates; no undocumented approximations |
| D-F1.4 | UI-thread native measurement, pure SFLE computation | No toolkit references in math input |
| D-F1.5 | Strict geometry comparison | Browser reference rectangles + backend tolerances |
| D-F1.6 | Shared validation and contextual metadata | Closed prop split, inert outside Flex, function components single-root initially |
| D-F1.7 | Typed CSS-like sizes and box model | Namespaced item `layout_width`/`layout_height`; deferred percentages; `calc()` deferred |
| D-F1.8 | Horizontal LTR **and RTL** from F2 | Direction-aware row and row-reverse behavior |
| D-F1.9 | Progressive compatibility with **explicit errors** | No silent fallback for unsupported CSS semantics |
| D-F1.10 | **Full replacement** of portable layout computation with SFLE | Retire parallel Row/Column/Scroll content-layout algorithms |
| D-F1.11 | **0.01** logical px pure / **1.0** logical px native, calibrable | Per-backend reporting and structural exactness |
| D-F1.12 | UI-thread measurement, selective caching, immutable snapshots | Batched invalidation and lifecycle-safe commits |
| F1-RUST | **Rust primary, Python fallback** | Same normative semantics, versioned compute contract, packaging policy |

All decisions above are approvals of the *design*. Runtime behavior stays
unchanged until F2 and subsequent implementation milestones are authorized
and completed.

## 2. Consistency review and clarified invariants

### 2.1 D-F1.6 versus D-F1.10

"Metadata is inert outside Flex" remains true even when `Row` and
`Column` use SFLE **internally**. **Engine ownership** and **public Flex
formatting-context semantics** are separate concepts:

- `Flex` applies its explicit CSS-like container/item contract.
- `Row` and `Column` retain their public `spacing`, `padding`, `align`,
  `expand` and default behavior where compatibility is possible, but their
  backend-specific layout math is replaced with translation into SFLE inputs.
- A `Text(flex_grow=1)` directly under `Row` has valid but inert Flex-only
  metadata unless/until Row explicitly opts into Flex semantics as a separate
  future public API decision. Legacy `Row.expand` may be translated into
  engine grow behavior **internally** without making `flex_grow` active.
- `Scroll` retains native viewport, clipping, input, wheel/trackpad and
  offset semantics. Its **content sizing/arrangement** uses SFLE through a
  scroll-content layout context; that does not make Scroll itself a public
  `Flex` parent with automatically active `flex_grow` on children.
- Existing component-owned `width`/`height` keep their meaning; child
  SFLE sizing uses `layout_width`/`layout_height` and related names.
- Explicitly identify semantic behavior that cannot be reproduced during
  migration, version it as a breaking change where required, and document
  it instead of silently changing a widget's meaning.

**No legacy layout algorithm remains the final geometry authority.** Native
platform APIs still place and render widgets based on SFLE output. The
migration can be staged internally, but the accepted endpoint is one engine.

### 2.2 D-F1.8 versus D-F1.3

LTR + RTL **horizontal writing mode** is in scope starting with F2; this
does not imply support for CSS vertical writing modes. A first supported
layout shape must respect both LTR and RTL rather than shipping an LTR-only
"complete" phase.

The coordinator supplies an explicit `writing_direction` of `ltr` or
`rtl`. No implicit machine-locale guess for geometry. For horizontal
writing mode:

| Flex direction | LTR main-start | RTL main-start | Cross-start |
| --- | --- | --- | --- |
| row | physical left | physical right | physical top |
| row-reverse | physical right | physical left | physical top |
| column | physical top | physical top | left (LTR) / right (RTL) |
| column-reverse | physical bottom | physical bottom | left (LTR) / right (RTL) |

`flex-wrap: wrap-reverse` reverses the cross-axis line stacking direction.
`justify_content`, `align_items`, `align_self` and
`align_content` are resolved in the logical main/cross axes before a
renderer writes physical coordinates. `order` does not mutate reconciliation
or keyboard/accessibility source order.

If any RTL-specific combination is not yet implemented during incremental F2
work, the feature must fail explicitly; do not claim its LTR geometry matches.

### 2.3 D-F1.9 diagnostics policy

Use a closed capability manifest with a declared version per engine/backend.
Validation follows this order:

1. Parse and validate public property **syntax/type**.
2. Normalize tagged values and check allowed property combinations.
3. Check **engine semantic capability** (Rust and Python parity).
4. Check **renderer measurement/geometry capability**.
5. Only then issue a pure layout calculation and native commit.

Unknown prop, invalid value and unsupported feature are distinct errors.
Suggested stable diagnostic codes (names pending implementer conventions):
`SFLE_UNKNOWN_PROP`, `SFLE_INVALID_LENGTH`,
`SFLE_UNSUPPORTED_FEATURE`, `SFLE_UNSUPPORTED_MEASUREMENT`,
`SFLE_MULTIPLE_ROOTS`, `SFLE_LAYOUT_CONSTRAINT_ERROR`, and
`SFLE_BACKEND_MISMATCH`.

An unsupported feature that would change geometry is an error, **not**
a warning-and-continue. A trace or warning can accompany a supported
feature with known platform appearance differences, but must never mask a
non-conformant layout as a successful CSS implementation.

### 2.4 D-F1.11 comparison and tolerances

**Approved initial targets, calibrable against browser fixtures:**

- Pure computation: maximum absolute coordinate/dimension difference
  `<= 0.01` logical px versus Chromium with equivalent intrinsic inputs.
- Native geometry: maximum absolute applied bound difference
  `<= 1.0` logical px (including coordinate translation/rounding), assessed
  separately for each Qt/Kivy/Tkinter backend.
- **Exact structural match:** flex-line membership, logical order, number of
  boxes, box association to stable IDs, and supported-feature meaning cannot
  be excused by numeric tolerance.
- Always report `measurement_error`, `engine_error` and
  `geometry_commit_error` separately. Font/text intrinsic differences are
  not evidence that the Flex algorithm is wrong.
- Record viewport, available dimensions, CSS reference fixture, pixel scale,
  platform/font and measurement revision; changes to numeric thresholds
  require a documented decision and before/after fixture results.

The 1.0 px target is an *initial acceptance threshold*, not permission
to introduce systematic geometry drift or change wrapping.

## 3. Engine architecture and Rust/Python parity

~~~mermaid
flowchart TD
    A["PSX VDOM + reconciler (Python)"] --> V["Closed component/layout prop validation"]
    V --> C["SFLE coordinator + cache + scheduler (Python)"]
    C --> M["UI-thread intrinsic measurement (Qt/Kivy/Tk/Headless)"]
    M --> S["Immutable typed layout snapshot"]
    S --> I["Versioned pure computation interface"]
    I --> R["Rust core - primary (PyO3/maturin)"]
    I --> P["Python core - fallback"]
    R --> O["Identical semantic LayoutResult contract"]
    P --> O
    O --> C
    C --> G["UI-thread geometry commit"]
    G --> W["Native widget geometry / viewport"]
    O --> X["Inspector diagnostics / Headless fixtures"]
~~~

### 3.1 Rust-primary, Python-fallback policy

The Rust implementation is the preferred production computation backend.
The Python implementation is **not** a simplified or approximate algorithm.
Both consume the same normalized input schema and yield the same semantically
equivalent layout tree within the pure tolerance.

- **Loading policy:** try the compatible Rust extension; if it is missing
  or cannot load on the current supported environment, switch to Python
  before layout execution. Emit a clear backend-selection diagnostic.
- **Version policy:** a versioned schema and capability manifest must match
  between coordinator and selected engine. Do not route a feature to a backend
  that does not implement it; return an explicit unsupported-capability error.
- **Failure policy:** do not automatically retry arbitrary Rust *runtime
  failures* with Python in the middle of an in-flight commit; this can conceal
  bugs, duplicate side effects or introduce inconsistent geometry. Fail the
  layout transaction and preserve previous committed geometry. A future
  narrowly scoped recovery policy requires a separate review.
- **Parity:** same feature matrix, line membership and ordering; compare
  geometry against Chromium and against the alternate engine with equivalent
  measurements. Fix drift rather than maintaining two interpretations of CSS.
- **Data boundary:** pass flat/batched immutable node IDs, tagged lengths,
  definiteness flags, min/max constraints, intrinsic data and content box
  dimensions. No GUI handles, callbacks, `VNode` objects or hook state in
  Rust; release the GIL for pure computation only when snapshots are isolated.
- **Precision:** finite `f64` internal values; do not round intermediate
  flex allocations. Percentages may be unresolved until applicable reference
  sizes become definite. Preserve tagged `AUTO`, `NONE` and intrinsic
  keywords rather than serializing them as zero.
- **Distribution:** define a CI/build matrix for supported Python versions,
  Windows/macOS/Linux architectures, PyO3 ABI strategy and maturin wheels;
  verify source installation and Qyro/PyInstaller-frozen builds. On a
  supported installation missing a binary wheel, the Python fallback must
  function without requiring users to install Rust.
- **Performance:** benchmark cold/warm layouts, nested wrapping, repeated
  resize bursts, memory, Python/Rust crossing overhead and UI stalls. Rust
  is primary by decision, but performance must still be demonstrated.

**Critical packaging consequence:** optional Rust binaries imply the package
must remain importable when the native extension is unavailable. Never make
top-level PSX import depend unconditionally on the native module.

### 3.2 Pure computation contract

| Input/output | Required fields | Constraints |
| --- | --- | --- |
| `LayoutInput` | stable node IDs, tree parentage, normalized styles, writing direction, measurements, constraints, capability revision | immutable; no GUI refs |
| `AvailableSize` | finite optional value, `definite` flag | definite zero distinct from unknown |
| `MeasureResult` | intrinsic min/max/preferred, baseline, font/theme/DPI revision | generated on UI thread |
| `LayoutResult` | logical content/padding/border/margin bounds, flex lines, overflow, diagnostics | deterministic by schema and measurements |
| `GeometryDiff` | changed IDs, new rectangles, commit generation | applied on UI thread and only to live nodes |

Feature parity means the two implementations must have the **same errors**
for unsupported semantic combinations as well as the same successful
results.

## 4. Measurement, scheduler and cache (D-F1.12)

~~~mermaid
sequenceDiagram
    participant P as Props/Resize/Font event
    participant S as Existing PSX Scheduler
    participant C as SFLE Coordinator
    participant M as UI-thread Measurer
    participant E as Selected Pure Engine
    participant A as Native Geometry Adapter
    P->>S: Invalidate mounted node/layout root
    S->>C: Coalesced dirty snapshot + generation
    C->>C: Reuse valid measurements and evict affected entries
    C->>M: Measure only stale nodes under constraints
    M-->>C: Immutable measured snapshot
    C->>E: Compute layout (Rust preferred; Python fallback)
    E-->>C: LayoutResult + capability/diagnostic data
    C->>C: Check generation and node lifecycle
    C->>A: Apply changed bounds on UI thread
    A-->>S: Commit geometry without remount
~~~

Cache keys must account for node/content identity, layout style revision,
effective available constraints, font metrics, theme, DPI scaling and
renderer measurement capabilities. Cache entries must be invalidated on
node removal/disposal, change of native widget type, relevant text/content
change, resize, font/theme/DPI change and any intrinsic-size mutation.

The coordinator should prevent reentrant geometry/measurement cycles and
drop obsolete snapshots when a newer reconciliation generation supersedes
them. Relayout must preserve key identity, hooks, event slots, focus and
scroll offset where the underlying current PSX contracts permit.

A physical widget resize emitted *because of* a geometry commit must not
cause an unlimited feedback loop. Record generation and diagnostic causes.
No worker thread may query GUI widgets; pure immutable computation may run
off-thread when safe, but the final application returns to the UI thread.

## 5. Complete portable layout replacement (D-F1.10)

~~~mermaid
flowchart LR
    A["Flex API"] --> T["Container-to-SFLE style translation"]
    B["Legacy Row API"] --> T
    C["Legacy Column API"] --> T
    D["Scroll content layout"] --> T
    T --> E["Single SFLE calculation authority"]
    E --> Q["Qt geometry adapter"]
    E --> K["Kivy geometry adapter"]
    E --> W["Tkinter geometry adapter"]
    E --> H["Headless geometry output"]
    D --> S["Native viewport/clip/input/offset (retained)"]
~~~

**Migration design (staged delivery permitted; final replacement mandatory):**

| Component | Public contract after migration | Internal geometry |
| --- | --- | --- |
| `Flex` | CSS-like Flexbox container, direct flex item metadata active | SFLE |
| `Row` | Existing Row builder/markup semantics as compatible | Translate legacy props, then SFLE |
| `Column` | Existing Column builder/markup semantics as compatible | Translate legacy props, then SFLE |
| `Scroll` | Existing scroll axes, viewport, clipping, input and offset API | SFLE handles content arrangement; native scroll mechanics retained |
| `Headless` | Deterministic layout metadata and debug geometry | Same SFLE computation outputs |

Every current native Row/Column/Scroll layout routine must be inventoried
before removal. Removal means **no duplicate layout arithmetic**, not
deletion of native widget adapters or necessary platform-event plumbing.
A compatibility translation must preserve old working semantics where
possible, and any unavoidable behavior change requires explicit migration
notes. Independent per-backend layout math must not survive as a hidden
parallel fallback.

## 6. F2 readiness gates (not permission to implement)

The approved architecture authorizes **planning**, not F2 code changes.

**F2.0 — implementation blueprint:** define module boundaries, Python
fallback algorithm structure, Rust extension boundary, wheel targets,
capability matrix, feature slices, and developer-experience checkpoints.

**F2.1 — shared data contracts:** tagged lengths, style normalization, tree
snapshots, definitely-sized constraints, errors and geometry results.

**F2.2 — Rust primary + Python parity:** develop the normative line-forming,
flex-sizing, alignment and box-geometry rules in both implementations in
approved vertical slices. Prefer shared browser-reference fixtures and
cross-engine parity verification. No feature counts as supported if one
backend accepts it and the other silently approximates it.

**F2.3 — early browser conformance:** verify LTR and RTL, main/cross axes,
row/column and reverse direction for the first shipped feature slice;
subsequently extend wrap, intrinsic measurements and min/max behavior
through explicit capability gates.

**F2.4 — migration planning:** inventory legacy Row/Column/Scroll geometry,
preserve public API where feasible, document expected deltas. Actual Qt/Kivy/
Tkinter integration and retirement of native layout algorithms remains
primarily F3, but F2 must define enough adapter contracts to prevent
architectural divergence.

**Exit criteria for F2:** a renderer-neutral, deterministic engine contract;
Rust primary with load-time Python fallback; matched capabilities and geometry;
headless/browser comparisons within the approved computational tolerance;
documented deviations; no unsupported-feature silence. Native full
integration and migration completion may be scheduled under F3, but the final
design must enforce SFLE as the sole portable layout authority.

## 7. Formal F1 closure checklist

| Gate | Status |
| --- | --- |
| All architectural decisions approved | **Complete** |
| No contradictory Row/Column/Scroll engine-ownership policy | **Complete** — SFLE only |
| D-F1.6 / D-F1.7 box model retained and compatible | **Complete** — namespace + contextual metadata |
| LTR + RTL requirement documented | **Complete** |
| Unsupported-feature errors documented | **Complete** |
| Numeric thresholds and calibration policy documented | **Complete** |
| Native measurement/scheduler design documented | **Complete** |
| Rust-primary / Python-fallback behavior documented | **Complete** |
| Implementation + conformance certification | **Not started — F2/F3** |
| **User authorization to start F2** | **Pending explicit approval** |

**F1 is ready for formal close-out, not automatically equivalent to an
instruction to start F2.**
