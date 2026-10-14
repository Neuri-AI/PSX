# Responsive 12-column Grid — approved F4 contract v1.0

**Status:** owner-approved architectural/product contract (2026-10-14); **not implemented or certified**. This document is normative for future F4 increments, not evidence of running features. The six gates below are approved planning gates; all are **NOT STARTED** until verified production code and mandatory executable evidence exist.

**Existing baselines:** [roadmap](../roadmap.md), [F1 portable layout contracts](sfle-f1-contracts.md), [F3 implementation](sfle-f3-implementation.md), [F3 intelligent CI strategy](sfle-f3-ci-strategy.md), [F4 capability certification policy](capability-certification-policy.md). Cinnamon is the commercial name for the existing SFLE authority; no runtime rename is required by this document.

## 1. Public surface and defaults

- Two declarative components: `Grid` (layout container) and `GridItem` (explicit child wrapper), supporting nested grids.
- F4 Grid is a **12-column Flexbox Grid**, not bidimensional CSS Grid. `Grid.columns` defaults to 12; only the integer 12 is supported during F4. `wrap` is always enabled; `wrap=False` is not a supported public mode. Do not create a parallel layout algorithm in a toolkit.
- `Grid.gap=0`; `row_gap` and `column_gap` use `gap` when omitted. These accept the supported nonnegative Cinnamon layout-length subset, in logical coordinates and subject to existing resolution rules.
- `GridItem.span="auto"` by default; accepts integers 1–12 or responsive mappings whose values are integers 1–12 or `"auto"`. `GridItem.offset=0`; accepts integers 0–11 or responsive mappings of those integers.
- Shared `align_self`, `order`, box and namespaced `layout_min_*`/`layout_max_*` metadata reuse their existing F3 contracts. `order` affects visual layout, not reconciliation identity. Direction uses existing supported inherited LTR/RTL layout context; avoid introducing an incompatible new direction enum.
- Strict validation: wrong types, unknown breakpoints, invalid numeric values, unsupported child/component/backend combinations, spans outside 1–12 and offsets outside 0–11 fail explicitly; no silent clamping, invented intrinsic measurement or mock geometry.
- **Child policy:** direct resolved layout children of `Grid` must be `GridItem`. A function component resolving to a `GridItem` is allowed; ordinary controls directly underneath `Grid` are not implicitly wrapped. `GridItem` admits a single PSX component root (which may itself contain children), consistent with existing function component/single-root constraints. Do not invent component state stores.
- `Grid`/`GridItem` add no bespoke user events or methods; their public layout props and responsive interactions **do** require census cases.

## 2. Responsive resolution

- Responsive mappings use `base`, `sm`, `md`, `lg`, `xl`. Default minimum widths in *logical layout pixels*: `base=0`, `sm=576`, `md=768`, `lg=992`, `xl=1200`.
- The defaults can be customized **per application via the application-wide settings** using a validated, ordered mapping. G1 schema: `App(root, renderer=..., settings={"grid": {"breakpoints": {"base": 0, "sm": 576, "md": 768, "lg": 992, "xl": 1200}}})`. The `grid` section and `breakpoints` field are optional; omitted values use the canonical defaults. A supplied table must contain exactly those five names, with `base=0` and strictly increasing integer thresholds (booleans excluded). Invalid tables fail before renderer creation. `app.grid_breakpoints` exposes an immutable snapshot; `app.resolve_grid_item_props(props, content_width)` uses that snapshot. This is a pure G1 metadata resolver, **not** native layout or automatic breakpoint reflow, which belong to G2–G4. Do not add a window component.
- Resolve against **the Grid's definite available content-box inline width**, excluding its own padding/border, not the top-level window width. Nested Grids independently evaluate their assigned content width.
- Threshold comparison is inclusive (`width >= min_width`); the highest matching named breakpoint wins. If a mapping lacks a matching override, it inherits the preceding smaller breakpoint setting; `base` is required for a map unless the property default is explicitly used. Standalone scalar properties remain unchanged across widths.
- Re-evaluation occurs upon relevant container constraints, intrinsic sizes, DPI or tree updates and must preserve reconciler identity/hooks/refs/focus/state when keys/component identity permit. No widget recreation solely for a breakpoint change.
- Cyclic or indefinite sizing that cannot be resolved under existing Cinnamon rules fails explicitly. It must not repeatedly oscillate between breakpoint layouts.

## 3. Row placement and the agreed auto behavior

These are normative **observable** requirements. The detailed solver implementation may reuse existing Flex primitives *only where mathematically equivalent*; otherwise extend Cinnamon's Rust and Python solvers together.

1. Process children in logical placement order (`order` uses existing visual ordering rules); each row has capacity 12 logical column units.
2. An explicit span reserves that many units, and an offset reserves logical empty units before its item. Offsets consume row capacity; in RTL their physical side reverses while the logical order/identity remain stable.
3. An explicit item whose span + applicable offset cannot fit the remaining logical row capacity moves to the next row. When even an empty row cannot accommodate its required units, reject that declaration.
4. **Distributive auto:** on each determined row, equal-weight `auto` items share the remaining column width equally after explicit spans, offsets and gaps. No `auto` receives zero solely because a previous full-span item consumed the row: start a new row.
5. Auto children following a full-span explicit item form the next row and share it equally. Explicit examples: `[12, auto, auto]` => row 1 `[12]`, row 2 `[6,6]`; `[8, auto, auto]` => one row `[8,2,2]`; `[auto,auto,auto]` => three equal-width items in one row.
6. A later explicit item that cannot fit closes the current row; once closed, that row's membership never changes retroactively. Define look-ahead/row-finalization in a backend-neutral solver so grouping is deterministic even when mixed auto and explicit children appear in a different order.
7. Gaps reduce the actual usable *pixel* width inside a row rather than changing its logical 12-column capacity. Do not apply a gap to the logical empty offset units as if they were rendered widgets. Nonintegral auto shares are valid; use Cinnamon fixed-point/edge projection and existing precision/overflow invariants, not per-renderer rounding.
8. Span determines logical allocation. Intrinsic/native minima and maxima are respected separately; if a child cannot fit in its assigned box, expose/handle **explicit overflow** under existing layout/Scroll/clipping contracts rather than silently changing `span` or corrupting adjacent geometry. An overflow condition is not itself a column-wrap request.
9. Stable results for unchanged inputs; changes to viewport, constraints, scale or child data invalidate correctly, avoid stale commits and preserve rollback/readback contracts.

### Required numerical cases for G2 specification and executable tests

| Inputs (12 columns, unless specified) | Required observable result |
| --- | --- |
| `[auto]` | one full-width item |
| `[auto, auto]` | two equal items |
| `[auto, auto, auto]` | three equal items |
| `[8, auto, auto]` | one row: 8 + two equal shares of remaining four |
| `[12, auto, auto]` | 12 on row one; two equal items on row two |
| `[8, 6]` | separate rows in declared order |
| `[(span 4, offset 2), (span 6, offset 0)]` | one row, total logical capacity twelve |
| `[(span 12, offset 1)]` | explicit invalid declaration; fail closed |
| Nested Grid whose content width crosses `md` independently of window | breakpoint switches only for that Grid |
| Width exactly `md` threshold | `md` applies |
| Nondivisible usable pixel width among auto items | deterministic contiguous edges, equivalent Rust/Python geometry |
| Intrinsic minimum exceeding assigned size | explicit overflow; no silent span mutation |
| Unresolvable content-width/breakpoint circular dependency | explicit failure; no oscillation |

**Remaining solver-level precision work before G2 implementation:** Freeze a machine-testable line-packing fixture format and specify mixed `auto` + later explicit item grouping (for example `[auto, 8, auto, 6]`), overflow reporting interface and exactly which existing projection constraints apply. These are *implementation-specification refinements*, not authorization to alter approved semantics; any materially different user-visible behavior requires owner review.

## 4. Portability and architecture invariants

- Cinnamon is the **single source of geometry**: Rust primary, Python parity fallback. Python normalizes metadata, and renderers provide intrinsic measurement/real native geometry application under their existing contracts; no native `QGridLayout`, Tk grid manager or Kivy GridLayout as an alternative distribution authority.
- Reconciler retains mounted identity, hooks, refs, focus, callback lifetimes, existing key rules, and failure rollback. No automatic remount during resize or breakpoint transitions.
- Native Qt (supported bindings), Kivy, Tkinter and Headless participate according to their explicit capabilities. Preserve Flex, Scroll, native and custom adapter contracts, high DPI, intrinsic measurement, negative capabilities and existing numerical tolerances.
- `Scroll` remains owner of native viewport/input/offset/clipping; Grid owns only its own child layout. No `Row`/`Column` resurrection.
- `SFLE-CSS-01` (replaced-element aspect-ratio intrinsic sizing), `SFLE-CSS-02` (intrinsically auto-sized wrapped Flex), CSS Grid tracks, `fr`/`minmax`, named areas, subgrid, masonry, layout animations and generalized CSS selectors/stylesheets are **not** F4 commitments.

## 5. Approved F4 implementation gates (G1–G6)

All gates begin **NOT STARTED**. `CLOSED` requires working behavior, all applicable functional test cells, actual CI routing and executed public census receipts on the relevant immutable SHA. An owner-approved document or selected GREEN smoke suite cannot close a gate.

| Gate | Scope and exit criterion | Depends on |
| --- | --- | --- |
| **G1 — Public contracts and normalization** | Grid/GridItem registered, typed props/defaults, child policy, responsive map validation/normalization, builder/Markup parity, explicit unsupported diagnostics; code-specific RED→GREEN tests and public census receipts. No live GUI geometry claim. | F3 baseline; this contract |
| **G2 — Cinnamon Grid mathematics** | Rust-primary + Python-fallback identical row membership, span/auto/offset/gap/RTL/min-max/overflow rules under approved precision; deterministic fixtures, differential and Chromium oracle where semantics overlap. | G1 |
| **G3 — Native renderer integration** | Qt/Kivy/Tkinter/Headless measurement, native geometry commit/readback, lifecycle, disposal, updates, unsupported cells, component participation; real native tests and receipts by applicable backend. | G2 |
| **G4 — Responsive composition** | Per-container breakpoint reevaluation, nested Grid, Flex/Scroll interoperability, resize and state/identity retention, no cyclic oscillation. | G3 |
| **G5 — Robustness and compatibility** | Adversarial constraints/overflow, DPI, asynchronous invalidation, resource changes, teardown, rollback, stale generation protection, native precision, F3 regression preservation. | G4 |
| **G6 — Integral immutable-SHA certification** | Required full cross-backend/native platform, Rust/Python, Chromium where applicable, public census and regression gates complete on one immutable SHA; explicit dispositions for unsupported cells and owner signoff. | G1–G5 |

Each gate's work is split into **small descriptive increments** with actual RED/GREEN functional evidence, affected-backend routing and public behavior census receipts *in the same increment*. G5 does not postpone negative testing; G6 does not postpone receipts. Do not encode F4/G1/G2 etc. as opaque production file/function names.

## 6. Mandatory CI and public acceptance contract

Per [capability certification policy](capability-certification-policy.md), *every production capability* must supply:
1. Specific behavior-focused tests (creation, props/defaults, updates, limits, identity, lifecycle, geometry, native readback where relevant, and fail-closed cases).
2. Changed-code, changed-test and dependency routing in `scripts/ci/impact.py`, with positive/negative/mixed/unknown-path cases in `tests/test_ci_impact.py`. Confirm the selected suites are actually invoked by the corresponding `.github/workflows/` jobs. Shared math changes must propagate to Rust/Python differential, Chromium when semantically relevant, and impacted native consumers; backend-only changes should not needlessly run unrelated backends.
3. Whenever props/events/methods/interactions are exposed, applicability cases and **executed** operation receipts from `tests/certification/`. Verify exact commit SHA, test ID, JUnit assertion evidence, native backend and environment; `N/A` needs documented reason. No skipped/indirect/manually fabricated PASS.

Do not call G1–G6 `CLOSED` on tests associated with old F3 SHA, in-progress/canceled/skipped runs, or documentation references. Perform selective tests on incremental code, with full certification at the formal required gates. **Docs-only diffs select zero product tests**, with lightweight routing/status only. This contract-only edit requires no product-test execution and must not be represented as newly executed evidence.

## 7. Public developer experience target (illustrative, NOT shipped)

```xml
<Grid gap={16}>
    <GridItem span={{"base": 12, "md": 8}}>
        <Analytics />
    </GridItem>
    <GridItem span={{"base": 12, "md": 4}}>
        <Activity />
    </GridItem>
</Grid>
```

Grid and GridItem are planned public names. Exact application settings storage, serialization details and exceptional-case error identifiers are to be finalized in G1 without inventing runtime APIs in this document. A native backend need not know these abstractions to apply rectangles committed by Cinnamon.
