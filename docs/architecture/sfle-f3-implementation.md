# SFLE F3 — native integration, complete component coverage and exit criteria

> **STATUS: F3-G1 IN PROGRESS; G2–G5 NOT STARTED.** Created 2026-10-11
> from `develop` SHA `979b6ed9e86c63b640d498439045910ed1a189aa` on feature branch
> [`feature/f3-sfle-native-adapters`](https://github.com/Neuri-AI/PSX/tree/feature/f3-sfle-native-adapters).
> This document records the approved scope, **not** an implementation
> certificate or a substitute for executable CI proof.

## Related F3 documents — agent handoff

- **[SFLE F3 — Intelligent CI Strategy](sfle-f3-ci-strategy.md):**
  mandatory selective test execution, F2 workflow reuse, dependency-aware
  change routing, documentation-only policy and full gate certification.
- **[PSX Roadmap](../roadmap.md):**
  overall phase status, F3-G1–G5 scope, F4's responsive grid and the
  explicitly deferred CSS enhancements.
- **[F2-to-F3 migration inventory](sfle-f2-migration-plan.md):**
  legacy Row/Column/Scroll ownership, native renderer migration surfaces
  and the F2-authorized ports carried into F3.

Start here when handing F3 to another agent. These links are **normative
references for scope and verification**, not proof that selective CI or
production renderer integration has already been implemented.

## 1. Purpose and F2 boundary

F2 certified a single renderer-neutral geometry source, Rust primary with
Python load-time fallback, bounded capability/diagnostic parity, native
geometry ports, precision and adversarial Scroll authority contracts.
**F3 uses those contracts in the real PSX runtime.** The public component
registry, reconciler, widgets and all production renderers must actually
consume SFLE geometry.

Only five workstreams are authorized: **F3-G1, G2, G3, G4 and G5**.
G2 is clarified/enlarged as the mandatory *whole-component and extensibility*
integration gate; this does not add a sixth gate or move F4 work into F3.

The phase fails if any production Flex tree can silently delegate layout
sizing/positioning to Qt QBoxLayout, Kivy BoxLayout/size_hint, Tkinter pack,
a legacy Row/Column adapter or a custom adapter's competing layout algorithm.
Native widgets still own drawing, intrinsic measurement, events, accessibility
and their own controls; the single SFLE result owns portable layout geometry.

## 2. Existing responsibilities and necessary edits

| Surface | Current responsibility | F3 responsibility |
| --- | --- | --- |
| `psx/core/registry.py` | Name → constructor and optional component contract, registry clone/version | Register public `Flex`, retire `Row`/`Column` at G4, preserve every other existing built-in; ensure registered components can be normalized as Flex children. |
| `psx/core/contracts.py`, `props.py`, validators, defaults, VNode builders and markup | Per-widget props, defaults, child policies and allowed events; today `Box` and `Native` have no core component contract | Add shared closed and typed SFLE layout-item metadata validation to all applicable components; separate it from native props. Use `layout_width`, `layout_height`, `layout_min_*`, `layout_max_*` where native names collide. Reject unknown/unsupported combinations explicitly. |
| PSX reconciler, scheduler, component lifecycle | Identity, reconciliation, batch scheduling, hooks and refs | Normalize a stable layout tree; collect constraints and native measurements; cancel stale generations; remeasure at derived widths; apply only current immutable SFLE rectangles without remounting components. |
| `psx/renderers/qt/`, `kivy/`, `tkinter/` | Native create, update, insert, reorder, remove, native events and widgets; legacy layout ownership | Provide real intrinsic measurement and rect-application bindings for built-ins; preserve identity, focus, input/event subscriptions and ownership. No native secondary portable Flex layout. |
| `psx/renderers/headless.py` | Non-GUI reconciliation and operation recording | Emit deterministic actual SFLE boxes and identity/updates; provide deterministic fixture-native size stubs or explicit unsupported-measurement errors. |
| `psx/core/native.py`, `register_primitive`, `register_adapter` | Native widget declaration/ownership and extensibility | Define explicit, typed and testable opt-in measurement/geometry/lifecycle capabilities. Do not require arbitrary third-party widgets to fake capabilities. |
| SFLE engine and F2 adapter contracts | Certified pure computation, coordinate projection, viewport boundaries, commit/readback | **Reuse as-is unless a reproduced regression requires repair**; do not expand Rust/Python CSS semantics or alter F2 thresholds just to make a renderer pass. |

A single generic bridge should handle SFLE snapshots, ID mapping, bounds and
commit. Per-widget/per-backend hooks supply **intrinsic measurement** and
native widget geometry methods as necessary, **not separate layout engines**.

## 3. Five mandatory workstreams

### F3-G1 — public Flex contract and normalization

- Export and register `Flex` in the core public API, component registry,
  builders, declarative markup and each renderer's adapter routing. Apply
  a closed typed set of the already-approved CSS-like Flex props and defaults.
- Support row, column, reverse, the admitted wrap cases, grow/shrink/basis,
  item layout metadata, padding/margins/gaps and LTR/RTL **only within F2's
  published internal admitted subset**; reject unsupported combinations.
- Map effective layout participants through nested `Flex`, single-root
  function components, `Fragment`, ordinary controls and custom components,
  preserving stable keys, refs and hook boundaries with no fake native boxes.
- **Scroll policy is a gate, not an implicit fallback:** keep `Scroll`
  native as a viewport, require explicit `Flex` for portable content layout,
  and resolve the existing `SCROLL_CONTRACT.child_policy="multiple"`
  before implementation. Any multi-child compatibility decision must
  preserve one unambiguous SFLE content root and must not insert hidden
  native Flex formatting or change sibling ownership.
- Positive and adversarial tests: builder/markup equivalence, nested
  parent/child identity, invalid props, unknown tags, invalid scroll root,
  boundary metadata, disposal/reorder and unsupported features.

**G1 CLOSED only when** all declarations, normalization and diagnostics
are executable with independently tested markup and builder paths and
the Scroll content-root rule is explicit and enforced.

### F3-G2 — mandatory built-in and extensibility coverage

**Hard acceptance rule:** every component registered in the built-in
registry that can participate in a Flex tree must have supported
component/backend positive geometry + lifecycle coverage, **or** a
pre-existing, explicitly documented backend limitation that rejects
with a stable capability diagnostic. Simply skipping a widget, hiding
a failed test, leaving an adapter on an independent layout manager or
counting a `Flex + Button` demo does **not** satisfy G2.

Implement a coherent production pipeline for Qt, Kivy, Tkinter and Headless:

`reconcile → normalize/validate → measure on UI thread → immutable snapshot
→ Rust (Python fallback at load) compute → width-driven UI remeasure
→ generation and node checks → atomic UI geometry commit → readback/rollback`.

- Translate global logical SFLE rectangles to toolkit coordinate spaces,
  including Kivy bottom-left Y, native child-parent offsets and DPI policy.
  No adapter may recompute Flex lines/order/size distribution.
- Support dynamic resize, text/content changes, intrinsic image/widget
  changes, fonts/theme/DPI, alignment and constraint invalidation; reuse
  valid measurement cache entries only when all relevant inputs match.
- Preserve keyed VNode identity and component state, hooks, refs, handlers,
  focus where the widget supports it, and inserted/moved/removed widget
  ownership. No remount caused solely by a layout change.
- Maintain independent `measurement_error`, `engine_error` and
  `geometry_commit_error`; reject stale generations, disposed IDs,
  unsupported measurement and native override; rollback atomically.
- Use the mandatory complete built-in and custom-adapter matrix below.
  G2 is blocked until every applicable cell has executable evidence and CI
  includes an automatic census of registry names versus tested cases.

**G2 CLOSED only when** complete per-backend supported-pair + negative-pair
coverage is GREEN in mandatory CI, including mixed/nested trees and the
custom/Native path. G3 exercises *full scrolling behavior* separately.

### F3-G3 — native Scroll/content integration

- Qt `QScrollArea`, Kivy `ScrollView`, Tkinter `Canvas`/content frame and
  Headless viewport fixtures expose native **viewport dimensions** as
  constraints; SFLE alone computes the content root, descendants and extent.
- Scroll remains a **separate public component**, not a Flex implicit root.
  Its native machinery owns clipping, scrollbars, keyboard/touch/wheel input,
  offsets, edge chaining and OS-appropriate overscroll.
- Apply clamped offsets and viewport/content resizes **without modifying
  immutable SFLE boxes**. Nested hosts must maintain separate content
  ownership and transform frames.
- Test horizontal, vertical, disabled axes, mixed and nested Scroll,
  reflow, content growth/shrink, restore of valid offsets, edge chaining,
  repeated resize, node removal, disposal and focus/event preservation.
- Remove native child layout computation inside Scroll (Qt QBoxLayout,
  Kivy BoxLayout minimum_size and Tk pack positioning) whenever it competes
  with SFLE; **retain native viewport mechanics**.

**G3 CLOSED only when** real toolkit nested/horizontal/vertical Scroll
scenarios and Headless tests are GREEN and native events remain usable.

### F3-G4 — remove all public Row/Column and redundant layout authority

- Delete `Row`/`Column` public builders, imports, registry entries,
  contracts, validator routes, backend adapters and old portable layout
  calculations. **No aliases, wrappers or silent markup conversion**.
- Rewrite existing docs, examples, recipes, boilerplates and tests to
  `Flex(direction="row")` / `Flex(direction="column")` as applicable.
  Historical architecture/audit references may retain the old names.
- CI gates: explicit import/markup rejection, whole-repository tracked
  source scan and evidence of no active QBoxLayout/BoxLayout/pack portable
  Flex distribution; do not mistake legitimate widget/event/viewport
  internals for forbidden layout arithmetic.
- Preserve `Scroll` public API and normal existing component/event
  behavior. Audit any external Qyro boilerplate at a pinned SHA where
  included in the release scope.

**G4 CLOSED only when** all public/API/no-alias and legacy geometry
authority checks are executable and GREEN.

### F3-G5 — final integration certification

- Qt family, Kivy, Tkinter and Headless real integration; each supported
  component/backend cell, native bridge and Scroll works as documented.
- LTR/RTL, reverse, admitted wrap, gaps, min/max, bounded intrinsic sizing,
  resize, updates, nested layout and adverse generations/readback.
- Rust primary, Python fallback (load time only), source/frozen runtime,
  Windows/macOS/Linux wheels and mandatory CI workflows, plus live GUI
  smoke on environments where practical; no false unsupported-platform
  claims.
- Preserve approved F2 ≤0.01 logical CSS px versus Chromium with equivalent
  intrinsic inputs, exact structural line/order/ID matching and ≤1px native
  bounds. Keep raw LayoutUnit signed saturation/precision unchanged.
- Repository hygiene, removed names, docs and examples, new component
  tutorial, adapters/ports reference and final source SHA/CI certificate.

**G5 and F3 CLOSED only after** CI, all integration/coverage gates, source
audit and docs pass on the **same final SHA**. Never infer certification
from older workflows or untested proprietary/custom widget paths.

## 4. Mandatory G2 inventory and test matrix

Census source: `builtin_component_registry()` in
`psx/core/registry.py` at the F3 base commit. This table lists every
built-in *other than legacy Row/Column, which G4 removes*.
`Flex` is the new additional public layout node from G1.

**Per-backend outcome must be either:**
1. **SUPPORTED:** tests mount an actual native control (Headless uses its
   deterministic handle), obtain constrained intrinsic measurement where
   relevant, consume exactly one SFLE rectangle, verify native/logical
   applied geometry under its tolerance, update/resize/reorder/dispose
   without losing widget identity or relevant events/focus/state.
2. **EXPLICITLY UNSUPPORTED:** document pre-existing unsupported backend
   capability and test its stable error on construction/measurement/layout
   before any inconsistent native mutation. No silent `pass` fallback.

**No backend is assumed to support every component merely because its name
appears in the common registry.** For example, Kivy currently reserves
`Input` without native support. An existing unsupported cell may remain
unsupported if rejected and documented, but an existing *supported* cell
cannot regress to unsupported to get a GREEN suite.

| Required component(s) | Required native/semantic coverage | Special evidence |
| --- | --- | --- |
| `Flex` (new) | Actual geometry host in each renderer, no native Flex engine | Flex nested, reverse, wrap, reflow, own dimensions |
| `Text` | Width-constrained intrinsic text measurement + native rect | Font/content changes, line wrap, auto sizing |
| `Button` | Intrinsic label and icon/control measurement + native rect | on_click, disabled, focus, identity |
| `Input` | Text control measure/apply in backends that support it | Value/selection, on_change/on_submit, explicit unsupported elsewhere |
| `TextArea` | Width-driven multiline measurements + native rect | Reflow, editing focus/selection, event preservation |
| `Link`, `Badge` | Native text/label measurement and SFLE position | Text/styles changes and interaction where available |
| `Image` | Native intrinsic dimensions **within F2 allowed subset** + native rect | Content changes, no promised full deferred replaced aspect-ratio |
| `Checkbox`, `Radio`, `Switch` | Actual control size + SFLE rect | Checked/selected, on_change, focus |
| `Slider`, `SpinBox`, `Select` | Control intrinsic sizes + SFLE rect | Value/options/selection and change events |
| `ProgressBar` | Control preferred dimensions + SFLE rect | Progress update without remount |
| `RadioGroup` | Group/container and descendants measured/laid out | Child ownership, selection and event propagation |
| `Spacer`, `Divider` | Explicit virtual/native participation in SFLE | Gaps/minimums, grow/shrink, no phantom children |
| `Box` | Portable content container + SFLE rect | Nested children, padding, update/disposal |
| `Scroll` | Single native host + verified SFLE content root | G2 binding and geometry; **G3** full events/offset behavior |
| `Fragment` | Structural boundary without invented visible box | Multiple children, stable IDs, refs/lifecycle |
| `Native` | Declared ownership-aware size and geometry ports | Owned/borrowed widgets, unsupported measurements, safe disposal |

**Registry-to-test census rule:** at test collection/CI runtime enumerate
`builtin_component_registry().snapshot()`, remove only the known
G4-deprecated Row/Column names, include the new `Flex` name, and assert
that every remaining built-in has at least one mandated coverage row.
Parameterize supported/unsupported outcomes across all four backends;
assert every registered supported pair has a positive executed case and
every unsupported pair has an explicit negative test (no skip/xfail as
substitute for evidence). Any newly added built-in automatically expands
the census and blocks G2 until its coverage is defined and GREEN.

### 4.1 Shared SFLE layout metadata across existing widgets

- Recognize `flex_grow`, `flex_shrink`, `flex_basis`, `align_self`,
  `order`, `layout_width`, `layout_height`, `layout_min_width`,
  `layout_min_height`, `layout_max_width`, `layout_max_height`
  (and other **already-approved** box-model layout props where supported)
  on eligible Flex child participants.
- Maintain a centrally validated typed namespace. Do not forward these
  props to Qt/Kivy/Tk widget constructors or overwrite widget-native
  homonymous `width`, `height`, `align`, `padding` props.
- Outside direct Flex formatting context, retain valid metadata inert per
  approved F1-D1.6; invalid types, unknown names and unsupported combos
  must still reject. Function components carry relevant item properties
  through their actual effective hosted root without new wrapper widgets.
- No automatic promotion of arbitrary `Native` children to measurable
  SFLE items unless corresponding capabilities are supplied.

### 4.2 Custom components, primitives and adapters

A third-party `register_primitive`, `register_adapter` or
`Native` implementation must be able to participate in Flex through
**the same canonical bridge**, not a separate third-party Flex algorithm.

Document and test these capabilities, mapping them to existing renderer
interfaces rather than mandating an incompatible new one:

| Capability | Contract and failure mode |
| --- | --- |
| Create / ownership | Valid stable child ID, actual native widget/handle, owned vs borrowed lifecycle, parent association and disposal hooks |
| Measure intrinsic | UI-thread constrained `width`/available dimensions → immutable intrinsic metrics + revision; no layout children computed by native widget; fail `SFLE_UNSUPPORTED_MEASUREMENT` when absent and required |
| Apply geometry | Receive already-computed logical x/y/width/height (normalized relative to required frame), convert and apply without reflow or overwriting sibling bounds |
| Update / invalidate | Prop/content/size/font/theme/DPI invalidation and remeasure without remount when safe, generation tracking, disposed-ID rejection |
| Events and identity | Stable refs, keyed identity, callback slots, focus and event subscriptions; safe teardown and no leaked handlers |
| Readback / diagnostics | Actual native rect snapshot after commit, ≤1px allowable projection error, atomic rollback/diagnostics on overrides |
| Unsupported capability | Typed, early and actionable diagnostic; never silently supply fictitious zero dimensions or use a native layout manager as fallback |

**Required positive tests:** one instrumented registered custom primitive per
backend (including Headless), dynamic change and correct geometry/readback,
and at least one hosted custom function component with a preserved
key/ref/hook boundary.

**Required adversarial tests:** missing measurement, missing geometry apply,
incorrect native rectangle, stale generation, disposed widget, ownership
violation, borrowed child mishandling, change-triggered duplicate event
registration, native layout overriding SFLE and mixed-tree reordering.
All must fail closed or preserve unaffected state per the existing contract.

## 5. Intelligent CI is mandatory (cost-aware selection)

**F3 CI policy, handoff and exact implementation checklist:**
[SFLE F3 intelligent CI and test routing](sfle-f3-ci-strategy.md).

The F3 user requirement is **change-impact-based validation, not full
test workflows on every commit**. A docs-only PR/commit requires
**zero product tests** (at most a minimal status router if a required
GitHub check needs to exist). Incremental code changes run affected
tests and transitive consumers only; e.g. a Qt-only adapter change
does not build Rust/macOS wheels, whereas shared SFLE layout math
requires Rust/Python differential and Chromium verification.

**Verified F2 inheritance and actual problem:** five workflows currently
exist under `.github/workflows/`. The two change detector jobs in
`ci.yml` and `sfle-core.yml` **do not gate the expensive test jobs**.
Also, Chromium and SFLE core workflows are triggered for arbitrary PRs,
and UI certification does not yet cover F3 renderer edits under
`psx/renderers/**`. These are **unimplemented optimizations**,
not claims that current CI is selective already.

The [CI strategy](sfle-f3-ci-strategy.md) is normative for the next
agent: full PR-base change classification, rename and dependency
awareness, explicit conservative fallback on uncertainty, one
registry/backend coverage census, workflow-specific triggers, and
`if:` conditions on all expensive jobs. A documentation-only PR
must be demonstrably 0 test runs. An explicit G1–G5 *gate
certification* runs **its complete mandatory gate suite**;
G5 is a deliberate complete cross-platform one-SHA override.

Implementing smart CI is a **foundational F3 task**, not a sixth gate
or permission to omit required G2 component coverage. Do not count
a docs-only status as a passing test suite.

## 5. Acceptance evidence, dependencies and reporting

- **G1**: Builder+Markup public Flex and Scroll normalization contract;
  positive and adversarial parser/registry tests; headless constructors.
- **G2**: Automated full registry census + parametrized
  `built-in × backend × operation` matrix for available combinations,
  custom primitive/adapters; measured, applied, updated, resized and
  identity-preserving; no double-geometry authority. **Any missing
  supported pair keeps G2 OPEN.**
- **G3**: Scroll horizontal/vertical/nested real native widgets, clipping,
  offsets, input/event propagation and resized content/viewport.
- **G4**: Row/Column absent from public registry/builders/markup/import
  surface, old engines removed; docs/examples migrated and CI grep gate.
- **G5**: Complete cross-OS/cross-toolkit CI, Chromium/Headless/natives,
  source/frozen, no skipped required cells, final same-head SHA signoff.

For each iteration report **commit SHA**, changed paths, added tests,
RED→GREEN evidence and mandatory CI state. Do not claim a gate CLOSED if
a required platform or component remains untested, a relevant workflow is
running, or a renderer silently ignores a layout property.

## 6. Explicit non-goals and phase ownership

**F4**, not F3: user-friendly responsive 12-column Flexbox Grid API,
`Grid`/`GridItem` spans, offsets, breakpoint names/rules and responsive
container/window-aware grid primitives. F3 may expose raw Flex behavior
needed to manually compose such layouts; a complete grid is not G2/G5 scope.

**Post-F2 CSS milestone, not F3**: `SFLE-CSS-01` full replaced-element
intrinsic aspect-ratio sizing and `SFLE-CSS-02` unconstrained intrinsic
auto-wrap. Continue F2's fail-closed diagnostics and do not advertise
these features as supported.

**Not permitted:** a new portable layout engine in an adapter,
a compatibility alias for Row/Column, wrapper boxes added by normalization
solely to make geometry pass, hidden 12-column system inserted in F3,
or modifications to F2 precision/parity without independent RED evidence.

**Current F3 progress: 0/5 gates closed. Smart CI policy is documented but workflow changes have not yet been implemented.** This document is the acceptance
specification only. Implementation and executable certification are separate.
