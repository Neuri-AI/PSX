# Canonical Geometry Consumption — Precedence, Intrinsic Measurement and Invalidation Contract

> **Status:** TECHNICAL DECISION RECORDED, pending independent implementation/certification and unresolved global architecture gate
> **Date:** 2026-10-18
> **Branch:** `feature/universal-box-model-and-styling`
> **Scope:** Safe consumption of existing canonical item box metadata by Cinnamon and the native Flex path. This contract **does not** introduce CSS syntax, HTML-like tags, new box-sizing props, CSS Grid tracks, or a new public Renderer protocol.
> **Authority:** [Owner-approved universal box model and CSS Core architecture](universal-box-model-and-css-core-contract.md), [ratified box model](sfle-f1-box-model.md), [ratified measurement/scheduler architecture](sfle-f1-final-architecture.md), and existing public component contracts.

## 1. Exact currently verified code boundaries

- `psx/core/props.py` exposes a closed set of `layout_*` item metadata. `psx/core/layout_item.py` validates recognized length kinds and signed-margin/nonnegative padding/border rules without changing widget props.
- `psx/sfle/canonical_box_style.py` provides `CanonicalItemBoxStyle` and pure immutable normalization; percent values remain tagged.
- `psx/sfle/native_layout_snapshot.py` creates `PreparedNativeLayoutSnapshot.snapshot` using existing specified styles and `box_styles` for each node. Its `canonical_snapshot()` method is an **opt-in** representation of explicit lengths, not yet the default native renderer consumption path.
- Existing `_style()` includes **component-specific** rules for Flex container `width`, `height`, `padding` and `gap`, Scroll viewport values and structural Box/RadioGroup/Divider behavior. Preserve these before substituting any representation.
- `psx/sfle/measurement_plan.py`, `measurement_round.py` and `native_measurement.py` already carry immutable constraints/revisions and reject stale rounds. Qt, Tkinter and Kivy have actual measurement sources; a new mandatory renderer protocol is unnecessary for the first integration.
- Historical `sfle-f1-box-model.md` includes `layout_box_sizing` and some edge shorthands. Those names **are not in the currently inspected closed `FLEX_ITEM_PROPS`**. A historical normative intention must not be misreported as a working API. This integration does not silently add those props.
- Existing `Grid` and `GridItem` keep their own approved 12-column packing, intrinsic measurement and renderer bridge; CSS Grid is a separately scoped future algorithm.

## 2. Deterministic property partition and precedence (closed for this integration)

### 2.1 Source property namespaces

1. **VNode identity:** `key`, ref and component identity must never enter style normalization or change in a layout pass.
2. **Component-owned props:** `Image.width`/`height`, `Scroll.width`/`height`, `Text.color`, etc., retain their own native/portable contracts. They are *not* generic CSS width/color aliases.
3. **Parent-facing item box:** explicit `layout_width`, `layout_height`, `layout_min_*`, `layout_max_*`, `layout_margin_*`, `layout_padding_*`, `layout_border_*` are validated and normalized into typed fields for a direct effective Flex item. The existing per-component metadata support matrix applies.
4. **Container formatting:** existing `Flex` container props (`width`, `height`, `padding`, `gap`, alignment/direction) retain their established interpretation *within that container*. When a Flex is itself a child of Flex, its parent-facing `layout_*` box and its own container formatting dimensions are separate semantic slots.

### 2.2 Resolution within the existing contract

- For **the same parent-facing item semantic slot**, an explicitly specified validated `layout_*` value wins over its established default. There is no unspecified global CSS style origin in this slice.
- A component's native `width` or `height` must **never override** an explicit parent-facing `layout_width`/`layout_height`. Conversely, an explicit `layout_width` must not rewrite or delete `Image.width`. The native dimension may influence its **intrinsic contribution** when the layout dimension is `auto`, but that is measurement, not precedence.
- Preserve the snapshot translator's existing Flex rule: explicit side-specific `layout_padding_{side}` takes precedence over `Flex.padding` shorthand-derived values for the same edge. Container `gap` supplies `row_gap` and `column_gap` defaults only when their explicit values are absent.
- Preserve the existing Scroll binding: viewport dimensions are used as fallback only under the translator's documented condition that an explicit `layout_{axis}` does not already exist. Do not convert Scroll into generic CSS overflow.
- For min/max constraints, **do not declare winner by source priority**: they combine with the chosen preferred width/height inside Cinnamon using the ratified box-model constraint rules (including min precedence in conflicts).
- `auto` is an explicit semantic value, **not absence** or numeric zero. `none` for maximum constraint is unbounded. Retain tagged `Length` and percent fractions; do not eagerly resolve percentages from the window width.
- Unknown names, disallowed units and invalid edge values continue to fail closed under existing validators. Preserve exact legacy error behavior unless a documented compatibility change is explicitly approved.
- **No new public CSS-vs-layout precedence is decided by this document.** The accepted higher-level CSS architecture already favors old component compatibility, but `style`, stylesheets, class syntax and CSS conflicts are still not implemented; they require a later bounded public-API decision.

### 2.3 Box-sizing boundary

The parent-facing metadata supported **today** uses the existing content-box contract. The new canonical adapter must not add border-box behavior through hidden defaults. `layout_box_sizing` is a documented historical semantic but is **not accepted by current closed validators**; adding it requires a separate approved public property-contract delta and tests. Retain explicitly supplied border/padding in layout calculations using existing valid names.

### 2.4 Stable normalization requirements

- Perform component-owned/native validation separately from `layout_*` validation.
- Store canonical metadata as immutable ordered `Length` and `BoxEdges`, with exact normalized node IDs.
- Do not mutate original VNode props, native widget kwargs or component state; rebuilding normalized style must be deterministic for identical inputs.
- Preserve existing shorthand expansion, structural root normalization, Grid-as-leaf behavior and stable snapshots. The typed canonical path must not lose existing container style fields while converting explicit item dimensions.

## 3. Native intrinsic measurement and constraint handshake (closed for this integration)

### 3.1 Owner and stages

```text
VNode + legacy component props + canonical item lengths
  -> immutable normalized layout tree / stable node IDs
  -> formatting/constraint resolver (Cinnamon contract)
  -> measurement requests (node ID, generation, constraints, revision)
  -> UI-thread native measurement source (Qt/Tk/Kivy)
  -> immutable MeasuredBox snapshots
  -> Cinnamon Rust or Python layout (pure)
  -> generation-checked geometry diff
  -> UI-thread native geometry commit
```

Cinnamon is the only geometric layout authority. Native adapters may create widgets, obtain intrinsic hints, provide content-aware measurement, and apply geometry. They must **not** simultaneously arrange the same children with a competing native layout manager.

### 3.2 Definite versus indefinite constraints

- `AvailableSize(value, definite)` preserves definiteness; definite zero is a valid value. Unknown or indefinite sizes must never be fabricated by copying a parent width/height.
- Percent `layout_width` resolves against its containing block's definite inline size; percent height against its definite block size. Margin and padding percentages use the containing block's inline size, including top/bottom edges, according to the ratified F1 contract.
- For an indefinite percentage reference, preserve the unresolved tagged value and apply the *existing supported* Cinnamon fallback/cyclic sizing contract. If that formatting case is unsupported, return a capability/constraint error **before commit**, not a guessed zero.
- Constraint planning is layout-dependent: emit child constraints from an actually resolved formatting context, not directly from raw native root widget dimensions.

### 3.3 Measurement inputs, cache validation and error handling

- Use current `MeasurementRequest(node_id, constraints, generation, revision)`, `MeasuredBox` and `NativeMeasurementPort` primitives where applicable. Reuse a prior measurement **only when** the same live node type/identity, constraints and intrinsic-affecting revision (including font, theme, DPI, content/assets and applicable widget state) remain valid.
- Each measurement source remains on its UI thread. No native widget handle or GUI callback enters the pure layout input.
- Qt `sizeHint()` may be invalid before initialization; a negative invalid hint is not a valid content size. Any supported fallback to `minimumSizeHint()`, `ensurePolished()` or a component-specific intrinsic rule must be deliberate and verified. An intentional `(0,0)` is not automatically an invalid hint.
- For text that wraps or height-for-width inputs, remeasure against the **allocated content width** if the adapter/engine contract requests it; preserve the source component's focus/text selection/scroll state. Never measure by mutating live parent layout as an undocumented side effect.
- `prepare_round` and `fulfill_native_round` reject stale/incomplete batches; do not publish partially accepted measurements or silently substitute a fallback metric. Distinguish measurement errors from engine errors and geometry commit errors.
- Do **not** widen `Renderer` protocol. Use existing concrete backend hooks/ports; optional typed capabilities for third-party renderers can be separately specified after verifying actual adapter interfaces.

## 4. Layout invalidation, reuse, and commit (closed for this integration)

### 4.1 Dirty causes

| Cause | Style resolve | Native intrinsic remeasure | Cinnamon layout | Native geometry commit |
| --- | --- | --- | --- | --- |
| Paint-only supported prop (e.g. color without font metric impact) | Only affected style node | No | No | No geometry commit; paint update only |
| `layout_width` 150 -> 200px | Affected item | Only if width-dependent intrinsic measurement changes | Yes: containing Flex formatting context and dependent ancestors/descendants | Only changed rectangles |
| Padding, border-width, `gap`, min/max, flex growth/order | Affected layout context | Affected intrinsic measurements when inputs change | Yes: impacted context(s) | Only changed rectangles |
| Text content/font/DPI/image intrinsic change | Relevant style/measurement dependency | Yes, on UI thread | Yes: dependent contexts | Only changed rectangles |
| Resize/parent definite-size change | Relevant dependency nodes | Only measurements whose constraint key changes | Yes, including percentage/line-wrap dependents | Only changed rectangles |
| Stable keyed reorder | Only nodes whose style dependency changed | Reuse unchanged valid intrinsic snapshots | Yes for changed ordering/placement | Only changed rectangles |
| Remove/unmount | Remove cached dependencies | Never measure disposed node | Recompute affected active ancestors/siblings | Destroy disposed handles; geometry diff on remaining live nodes |

The table specifies **required effects**, not a claim that fine-grained instrumentation already exists.

### 4.2 Dependency propagation and coalescing

- Classify dirty flags separately: **style**, **intrinsic measurement**, **geometry/layout**, **paint**, **structural/lifecycle**. Changes can carry more than one cause; the effective affected set is their safe union.
- Invalidate the **smallest provably correct** formatting context/subtree. For example, changing the width of one Flex item may move its siblings or alter wrapping, and may change ancestor intrinsic size. Propagate through dependency edges rather than always stopping at the edited leaf or always invalidating the whole app.
- Permit a conservative larger subtree recomputation when dependency tracking is incomplete; record the reason and prove it is bounded/terminating. Do not promise constant-time updates or a one-widget recalculation for all property changes.
- Coalesce repeated invalidations on the owner UI loop; maintain monotonic generation/revision tokens. Discard obsolete async/pure calculation results before native commit.
- Paint-only changes **must not** invoke Cinnamon or intrinsic measurement if their normalized computed geometry and intrinsic dependencies are unchanged.
- Preserve node identity and cache ownership on key-based reuse; unmount evicts per-node layout and measurement results, dependency edges and subscriptions. No unbounded retention by generation or native handle.

### 4.3 Commit integrity

1. Confirm all node IDs are current and mounted; check generation, constraints and measurement revisions.
2. Compute geometry in logical layout coordinates (historical Rust/Python fixed-point contract remains authoritative); convert to native/device units only at the backend boundary.
3. Diff computed rectangles against the **last successfully committed** geometry, and write only changed native rectangles.
4. Ensure geometry writes do not immediately cause an unbounded resize -> measure -> layout feedback cycle; track commit origin, skip equal geometry and guard reentrancy.
5. If calculation/measurement fails, retain the last known good geometry and report the error. If native commit fails midway, attempt the documented backend rollback/repair path and mark affected geometry state invalid until revalidated; never report a failed generation as committed.
6. UI thread alone applies widget geometry. No host/native children are recreated solely to apply a new rectangle.

### 4.4 Cache key and lifetime minimum

Measurement cache identity must include: stable node identity and native type, effective constraints, intrinsic content revision, font/theme/DPI/resource revision, measurement capability revision and applicable sizing mode. Layout cache identity must include: normalized style/geometry revision, tree/child ordering, available constraints, input measurement revisions, writing direction, engine schema/version and formatting-context type. Cache invalidation follows all relevant dependencies. Any cache retained across generations must be bounded and cannot strongly retain disposed components/native widgets.

## 5. Rollout choice and compatibility guardrail

1. Begin with a **single narrowly scoped native Flex callsite**, preserving the existing specified-snapshot path as a verification baseline. Check whether `prepared.canonical_snapshot()` is observably equivalent to `prepared.snapshot` for the approved old property grammar.
2. First characterize exact snapshot-style diffs and expected geometry of: explicit lengths, auto/none omission, percentage lengths, side-specific padding, Flex shorthand padding/gap, Scroll child, nested Flex, Grid-as-leaf, intrinsic content and zero-dimensional hints. Do not flip the default globally based only on pure serialization tests.
3. Run identical Rust and Python Cinnamon inputs and compare geometry/diagnostics under the established tolerances. Then exercise real native measurement and mount/update/resize/unmount on the matching backend. Retain a documented compatibility rollback switch only if needed for the staged integration.
4. Expand to additional backends **only after** that callsite is certified; all built-in backends must converge on the same normalized geometry model. Third-party adapters remain compatible until a separate capability contract authorizes new requirements.
5. Do not inadvertently convert `Grid` to CSS Grid, implement CSS cascade or reopen the deliberately deferred Kivy memory investigation.

## 6. Design and certification test vectors

| Vector | Required expected behavior |
| --- | --- |
| Explicit item width alongside `Image.width` | Item width follows typed `layout_width`, widget image dimension stays component-owned |
| `layout_width="50%"` with definite parent | Correct containing-block reference, same Rust/Python geometry |
| `layout_height="50%"` with indefinite parent | No guessed viewport height/zero, deterministic supported fallback or error |
| `layout_padding_left` explicit with `Flex.padding` shorthand | Explicit edge wins; no erased shorthand on other edges |
| `Flex.gap` with explicit `row_gap` | Explicit axis wins, other axis inherits `gap` |
| `layout_min_width` greater than preferred max | Historical min/max conflict behavior retained |
| Zero `sizeHint` vs invalid Qt hint | Valid intentional zero retained, invalid negative rejected or verified fallback |
| TextArea height-for-width | Remeasure only at changed allocated width, live focus/selection preserved |
| `layout_width` 150 to 200 | Relevant Flex siblings/context reflow, unrelated independent subtree not remeasured |
| Background color only | No Cinnamon passes, native measurements or geometry writes |
| Rapid consecutive width changes | One coalesced latest-generation commit where scheduler guarantees, no stale geometry applied |
| Breakpoint-dependent nested legacy Grid | Current 12-column semantics, no CSS track algorithm substitution |
| Stable keyed reorder and removal | Identity/state retained for kept nodes, disposed native/measurement/cache entries released |
| Native commit raises midway | No false successful generation, next pass can repair or safely restore prior geometry |
| Equivalent typed/legacy snapshot | No source prop mutation, compatible geometry and diagnostics at exact SHA |
| Unsupported renderer combination | Explicit capability failure, never fake green |

**Evidence required for each implementation slice:** behavior tests, impacted-backend CI selection tests and exact-SHA job receipts, applicable public-behavior census when public behavior changes, Rust/Python geometry parity, and native adapter readbacks where supported. A documentation-only edit is **not** a production test run.

## 7. Decision disposition and remaining gates

The project owner approved the universal Box Model and CSS Core architecture on 2026-10-18 and subsequently requested closure of the integration's detailed rules for precedence, intrinsic measurement and invalidation. This document **records the concrete technical contract** for that narrowly defined adapter integration; it does not invent owner approval of different public APIs.

**Closed for the limited integration:** legacy `layout_*` versus native prop partition, explicit-over-default and shorthand precedence, current content-box behavior, measurement request/revision and UI-thread rules, dependency-based invalidation, generation-aware commit, layout/measurement cache lifetime.

**Still outside scope / separate approval:** new CSS stylesheet attachment syntax, cascade between CSS and old props, exact lowercase tag defaults, public `layout_box_sizing` exposure, CSS Grid tracks, new mandatory renderer interfaces, missing package resolver and global architecture release gate. Memory soak and Kivy slope are tracked separately by the project's earlier deferral.

**Implementation start condition:** reconcile this technical contract with current selected backend code and the global gate's applicable safety/evidence rules, then implement the first smallest compatibility-preserving native Flex integration increment. No production changes are made by this document.
