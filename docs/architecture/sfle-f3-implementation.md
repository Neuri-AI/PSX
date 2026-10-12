# SFLE F3 — native integration, complete component coverage and exit criteria

> **STATUS: F3-G1 CLOSED; G2 IN PROGRESS — C1 CLOSED; C2 CLOSED after executable contract/pytest-receipt re-certification at `9e071a1`; C3 CLOSED (built-in lifecycle); C4 CLOSED (Native/custom/borrowed ownership and resource receipts at `9df902d`); C5–C6 invalidation and final precision certification remain pending. G3–G5 NOT STARTED — 1/5 official F3 gates closed (20%).** Created 2026-10-11
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
  Its **Commit convention** section is the approved, binding agreement for
  all remaining F3–F5 and subsequent PSX work: use English Conventional
  Commits with subsystem scopes, reserve `sfle` for actual core changes,
  and do not rewrite historical commit messages.
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

### G5-FUNCTIONAL — mandatory exhaustive public behavior audit

**Status: SPECIFIED, NOT IMPLEMENTED OR CERTIFIED.** This is a mandatory
**G5 exit condition**, not a new F3 gate and not a reopening of G2-C3.
Passing native lifecycle tests does not imply that portable public props,
events or interactions behave identically on every supported renderer.

1. **Inventory, derived from code rather than curated screenshots.** Enumerate
   the live builtin registry, each component's published contract
   (child policy, permitted props, types/defaults/validation, event signatures,
   exposed public methods/ref behavior), public Markup syntax and applicable
   renderer capabilities. Produce machine-readable tuples
   `(component, backend, feature_kind, feature_name, scenario_id)`. A new
   component, property, event, method or changed contract must add rows
   automatically or fail census validation. Keep explicit `unsupported`
   and `not_applicable` explanations: do not count either as a PASS.
2. **Every advertised property:** Prove default, valid boundary/equivalence
   classes, live update, invalid value rejection, and native readback/rendered
   outcome on each supported backend. Include interacting properties when
   coupling is documented or technically meaningful (e.g. enabled × event,
   value × bounds, placeholder × focus, password/read-only × input, text
   wrapping × width, nested Flex sizing). Infinite input spaces require
   named partitions, deterministic combinatorial/pairwise sampling and
   property-based/adversarial coverage with reproducible seeds — never claim
   exhaustive enumeration of all possible values.
3. **Every advertised event and public method:** Execute real user/host
   interaction (native event dispatch, focus/keyboard/text input, scrolling,
   selection, edit and activation where applicable); verify payload,
   dispatch count, ordering, rebind/unsubscribe, disabled behavior, errors
   and teardown. Verify exposed methods, refs and lifecycle contracts with
   positive, negative and idempotence cases as relevant. Mock-only callback
   invocation is not a substitute for a native event test.
4. **All registered components across backends:** Execute on Qt bindings
   (PySide6, PyQt6, PyQt5, PySide2), Tkinter, Kivy and Headless only where
   the contract advertises support. Validate semantics independently of
   toolkit-specific visual decoration; include screenshots/goldens only
   for observable style/painting claims. Native/custom/borrowed variants
   must use C4's explicit capability matrix, never inherit builtin proofs.
5. **Functional evidence is distinct from C2/C3 lifecycle evidence.**
   Each applicable row must identify one specific executed assertion/test,
   source revision and environment; persist JUnit/results plus JSON
   `executed_pass | pending | not_applicable | unsupported | failed`.
   A passing general-purpose test name, AST mention, reference-only item,
   synthetic oracle, skipped/xfail case or undocumented N/A must not certify
   a row. A failing or missing required row fails G5.
6. **CI fail closed:** Add a code-derived functional census, manifest
   consistency test, functional scenario suites and receipt verifier. CI
   fails for a newly advertised feature without a behavior-specific test;
   stale/duplicate evidence; absent backend; missing execution artifact;
   failed/skipped mandatory assertions; or conflicting contract/applicability.
   During development, use existing selective impact routing and test only
   affected suites. Formal G5 signoff executes **all** mandatory suites
   and supported platform/toolkit variants on **one immutable SHA**, including
   geometry (≤0.01 logical CSS px / ≤1 native px), Scroll, G4 removal,
   Rust/Python, source/frozen and packaging.
7. **Published acceptance artifact:** Generate a per-component report with
   counts by `backend × props × events × public methods × scenarios`,
   lists of exclusions and unsupported cases, failed or pending rows,
   exact executed test identifiers, environment and SHA. G5 cannot close
   unless the applicable public behavioral matrix has **zero pending,
   zero uncertified and zero failed rows**, required tests are GREEN and
   all exclusions are independently reviewed. This is bounded by the
   explicitly *documented supported* API, not imaginary permutations,
   unsupported CSS extensions or undisclosed proprietary widgets.

**Boundary:** G2-C3 proves native lifecycle, G2-C4 proves
external/borrowed ownership, G2-C5 proves invalidation, G2-C6 proves
native precision/integration; G3 owns full Scroll; G4 removes legacy
layouts. G5 alone consolidates functional behavior and cross-platform
end-to-end certification. None of these certificates replaces another.

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

**Current F3 progress: 1/5 gates CLOSED (20%). G1 CLOSED: builder, Markup, shared item metadata, normalizer, explicit Scroll content policy, fail-closed renderer routing and adverse cases certified at `df6fe1c`. G2 IN PROGRESS; G3–G5 NOT STARTED. F3 change-aware CI is implemented and verified. See the G1 certificate and G2 increment below.** This document is the acceptance
specification only. Implementation and executable certification are separate.


## G1.2 implemented evidence — 2026-10-11

- **RED:** [`4468dba`](https://github.com/Neuri-AI/PSX/commit/4468dba644cdc22e38e4d11dc1e3d7a35330b177) added 12 intentionally failing normalization/Scroll cases while 58 prior Core cases passed; [RED CI #38153047652](https://github.com/Neuri-AI/PSX/actions/runs/38153047652).
- **GREEN:** [`3ac035b`](https://github.com/Neuri-AI/PSX/commit/3ac035b58cc90a1f3f0f05223a881bb96ab0dc2a) added `psx/core/layout_tree.py` with immutable declarative normalization: transparent fragment and resolved-function-component boundaries, stable keyed paths, no synthetic visible boxes and a unique explicit `Flex` content root per Scroll viewport. Components are **not** invoked inside normalization; G2 will provide their already-rendered roots from the reconciler.
- **Tests:** `tests/test_f3_flex_contract.py` now covers Markup/builder equivalence, nested Flex, preserved boundaries, reorder identity, unresolved components, Scroll roots, nested Scroll and duplicate-key errors. [GREEN CI #38153141925](https://github.com/Neuri-AI/PSX/actions/runs/38153141925) certified SHA `3ac035b` (70 Core tests, all selected CI jobs green; G4 legacy removal deliberately not selected).
- **Completion:** The remaining metadata and adversarial tests were implemented and separately certified in the final G1 evidence below. This is **not** evidence of production Qt/Kivy/Tk/Headless SFLE geometry integration or completed Scroll migration; those remain G2/G3 responsibilities.


## F3-G1 closure certificate — 2026-10-11

**Formal state: G1 CLOSED (1/5 F3 gates, 20%).** All executable evidence below
refers to the **same source SHA**
[`df6fe1c`](https://github.com/Neuri-AI/PSX/commit/df6fe1c107c98d9506944d10ced923a45f5608d7).
Historical G1.2 incremental evidence is retained above.

- **Public and normalization contract:** `Flex` available in builders, root API,
  registry and PSX Markup; `psx/core/layout_tree.py` preserves component and
  Fragment boundaries, keyed paths and refs without evaluating hooks or adding
  physical layout wrappers. Unresolved/cyclic components, unknown tags,
  duplicate sibling keys, boolean keys and invalid Scroll content roots reject
  deterministically.
- **Shared item metadata:** `FLEX_ITEM_PROPS` and
  `psx/core/layout_item.py` validate factors, basis, alignment/order,
  `layout_{width,height,min_*,max_*}`, margin, padding and border
  longhands, including typed SFLE lengths, invalid values and forbidden
  combinations. The closed metadata is kept separate from native widget
  props such as `Image.width` and `Scroll.width`. A registry census asserts
  coverage of all 18 existing applicable contracted components plus Flex.
  Raw/native declarations receive the same validation during normalization.
- **Scroll contract resolution:** historical `SCROLL_CONTRACT.child_policy`
  remains `multiple` for existing pre-SFLE renderers; the *SFLE normalization
  path* is **strictly exactly one effective explicit Flex content root**.
  Fragments/resolved function components may expose this root but no synthetic
  Flex, invisible adapter box or sibling reassignment is permitted. G3 will
  finish the native Scroll migration.
- **Routing and authority:** Qt, Kivy, Tkinter and Headless explicitly
  register `Flex` as an adapter key. Before G2's actual geometry bridge,
  default creation raises a stable F3-G2 capability error; it cannot silently
  run a QBoxLayout, Kivy BoxLayout, Tk pack or dummy Headless Flex fallback.
  These routes are covered by real backend tests. This **does not** imply
  successful native Flex rendering, which G2 must implement and certify.
- **G1 dedicated matrix GREEN:** [run #38155096426](https://github.com/Neuri-AI/PSX/actions/runs/38155096426),
  same SHA `df6fe1c`. Python 3.10, 3.11, 3.12 and 3.13 all passed
  **125 tests each**, with final certification verdict successful.
  Python 3.14 is outside `pyproject.toml`'s published `<3.14` support.
- **F3 selective CI GREEN:** [run #38155096518](https://github.com/Neuri-AI/PSX/actions/runs/38155096518),
  same SHA `df6fe1c`; selected Core, Headless, Qt, Kivy and Tkinter
  jobs passed, with the required aggregate GREEN. Rust, Chromium, SFLE
  numerical recalibration, wheels and G4 removal were **correctly skipped**
  by impact routing; they are not counted as executed G1 tests.
- **At G1 signoff:** G2–G5 had not started. Subsequent G2 progress and open criteria are recorded below; G3–G5 are still NOT STARTED.


## F3-G2 implementation evidence — first incremental geometry bridge (2026-10-11)

**State:** G2 **IN PROGRESS**, **not CLOSED**. Whole-phase progress remains **1/5 gates (20%)**.

- **Canonical SFLE snapshot mapper:** [`aa245fe`](https://github.com/Neuri-AI/PSX/commit/aa245fe63677e22fb9943e8d34582ffea82a7d7a) introduced `psx/sfle/f3_snapshot.py`; it converts G1 normalized Flex participants into immutable `LayoutInput` styles and stable keyed IDs. Gap shorthand, padding longhands, flex item properties, native width separation, fragment/component transparency and unsupported Scroll are explicit. No second Flexbox algorithm.
- **Mounted Headless geometry:** `psx/sfle/f3_headless.py` and `HeadlessRenderer` now have an **explicit opt-in viewport**. The reconciler's existing mounted/hook/key tree supplies source identities and real handle bindings; `load_layout_engine()` uses Rust primary and Python fallback at load time. Successful commits apply only SFLE border rectangles, after snapshot/generation/liveness/grid checks, with readback and rollback on commit failure. Host-provided intrinsic measurements are required where needed; the bridge never invents text/widget size.
- **No misleading automatic fallback:** Unconfigured `HeadlessRenderer()` still rejects mounting `Flex`, and legacy `Row`/`Column` cannot act as competing layout authorities within an opted-in SFLE tree. Qt, Kivy and Tkinter Flex mounting remain intentionally fail-closed until their real G2 ports are wired.
- **Tests and single-SHA CI:** [`a03f300`](https://github.com/Neuri-AI/PSX/commit/a03f30056ceadc9372049b84d8133ec5ec3ba9a3) passed [F3 selective #38158347861](https://github.com/Neuri-AI/PSX/actions/runs/38158347861), including **151 Core tests and 19 Headless tests**, plus impacted SFLE, Rust/Python, Chromium, Qt/Kivy/Tk regressions and platform wheels. [G1 regression matrix](https://github.com/Neuri-AI/PSX/actions/runs/38158347847) was scheduled on the same SHA; G1 continues closed.
- **G2 remaining:** wire actual Qt/Kivy/Tkinter native measuring and rectangle commits (Kivy parent-relative Y inversion from existing `NativeGeometryCommitter`); cover all registered supported widgets plus `Native`/custom adapters and negative capability cells; width-dependent remeasurement, viewport/resize invalidation and strict native commit/readback/error separation. G3 still owns scrolling events/offset lifecycle. **Neither live Qt/Kivy/Tk Flex rendering nor full G2 certification is claimed by Headless-only evidence.**


## F3-G2 iteration — actual Qt native geometry (2026-10-11)

**Formal state remains G2 IN PROGRESS, not CLOSED. F3 remains 1/5 gates CLOSED (20%).**

- **Explicit SFLE-enabled Qt host:** `psx/renderers/qt/flex.py` implements a native `QWidget` Flex host with **no QBoxLayout** or native sibling distribution. `QtRenderer` and Qt facades accept opt-in `sfle_constraints` and an optional injected engine. Without opt-in, G1's fail-closed error remains. Unported widget/backend combinations fail with an explicit F3-G2 capability diagnostic; **only Flex, Text and Button are admitted into this incremental SFLE-Qt path**.
- **Real coordinate projection and native intrinsic measurement:** `psx/sfle/f3_qt.py` uses mounted reconciler identities and normalized markup/builder VNodes to form one SFLE `LayoutInput`, measures native `QWidget.sizeHint()/minimumSizeHint()` through the pre-existing `QtMeasurementSource`, computes using the renderer's chosen SFLE engine, and calls the F2 `NativeGeometryCommitter(GeometryBackend.QT)` to set Qt child geometries in parent-relative top-left coordinates. It does not install a competing Qt layout.
- **Commit guards:** UI-thread authority, duplicate/stale/disposed identities, no native `QLayout`, actual parent-graph validation, SFLE generation/rectangle shape and fixed-point preflight, ≤1 px Qt readback budget and rollback of native child geometry if application/readback fails. Root/window size remains host-owned; viewport constraints can be updated without remounting.
- **Real native test evidence:** [commit `8e4d3b5`](https://github.com/Neuri-AI/PSX/commit/8e4d3b5919a7855ae73108393d8054a69bf6dc1b) passed [F3 selective CI #38159181324](https://github.com/Neuri-AI/PSX/actions/runs/38159181324) with successful aggregate, including **28 PySide6 Qt native tests** (the new `tests/test_pyside6_f3_g2_renderer.py` covers live `QWidget.geometry()`, nested parent-relative coordinates, PSX Markup, keyed reorder, hook-triggered reflow, button callbacks, viewport updates, explicit unsupported widgets and stale engine results). The [G1 3.10–3.13 regression #38159181381](https://github.com/Neuri-AI/PSX/actions/runs/38159181381) also passed on **the same code SHA**.
- **Still required for G2 closure:** Kivy bottom-left projection in its production renderer, Tkinter geometry application, other built-in Qt controls and complete Qt family matrix, `Native`/custom adapter ports, width-driven real text remeasure, font/DPI/resize lifecycle, fragment/Box ownership and fully instrumented per-backend and per-component matrix. Existing SFLE math and its precision thresholds remain unchanged. G3's Scroll events/offset integration is not considered complete.


## F3-G2 iteration — native Kivy geometry and inverted Y (2026-10-11)

**Formal state: G2 IN PROGRESS; F3 remains 1/5 officially closed (20%).**

- **Real Kivy production Flex host:** `psx/renderers/kivy/flex.py` implements an opt-in `Widget(size_hint=(None, None))` with **no BoxLayout**; reconciler insert/move/remove preserves declared identities. Direct children have `size_hint=(None, None)` and empty `pos_hint`, preventing Kivy sizing hints from overriding SFLE. Without `sfle_constraints`, G1's explicit fail-closed behavior remains unchanged.
- **F2-authoritative projection:** `psx/sfle/f3_kivy.py` resolves mounted/reconciled nodes to immutable SFLE `LayoutInput`, measures Kivy native label textures using `KivyMeasurementSource` on the owning thread, and invokes `NativeGeometryCommitter(GeometryBackend.KIVY)` with SFLE's untouched boxes. Kivy native child Y is computed by F2 as **parent border height − child top-relative Y − child height**, separately for each actual parent frame. Fixed-point preflight, root-border/host viewport consistency, generation/liveness, actual parent ownership, ≤1px readback and rollback are enforced.
- **CSS root content-box caveat:** a root `width=160px; padding=10px` produces a **180px border box**; the host cannot pretend its viewport is 160px. The live nested-geometry test explicitly chooses a 140px content width + two 10px paddings to match a 160px native viewport. The G2 preflight rejects mismatched host/SFLE border sizes rather than silently redefining CSS math.
- **Real SDL2/Window certification:** [source SHA `2eb0fad`](https://github.com/Neuri-AI/PSX/commit/2eb0fad8f1eea2ac975f146281c6a99e0b5a9d8b) passed [F3 selective CI #38162867871](https://github.com/Neuri-AI/PSX/actions/runs/38162867871) including the `xvfb-run` Kivy native job; `tests/test_kivy_f3_g2_renderer.py` verifies real SDL2 `Window.add_widget` mounting, native bottom-left readback, nested parents and padding, keyed move, hooks/Clock, events, viewport update, unsupported controls and stale generations. The [G1 supported-Python regression #38162867872](https://github.com/Neuri-AI/PSX/actions/runs/38162867872) is GREEN on the same code SHA.
- **Scope:** new Kivy G2 path supports **Flex/Text/Button** only. All other pre-existing supported components need G2 native ports or explicit stable unsupported capability cases. Tkinter is not yet integrated, and Kivy's full Scroll/clipping/offset mechanics remain G3. Automatic Window resize invalidation, width-driven intrinsic text remeasurement, toolkit-specific DPI and complete native/custom adapter registry matrix remain **open**. There is **no claim of full G2 closure**.


## F3-G2 iteration — actual Tkinter native geometry (2026-10-11)

**State: G2 IN PROGRESS, not CLOSED; total F3 progress is still 1/5 gates (20%).**

- **Opt-in SFLE renderer:** `TkinterRenderer(sfle_constraints=..., engine=...)` accepts a definite explicit viewport and the F2 Rust-primary/Python-fallback engine via `load_layout_engine()`. `psx/renderers/tkinter/flex.py` instantiates an actual `ttk.Frame` with native `place()` host geometry; **no `pack()` or `grid()` is ever used by the SFLE Flex path**. Reconciler-created Text and Button remain native `ttk.Label` and `ttk.Button`; item layout metadata is stripped before backend primitive validation but remains in the SFLE source VNodes. Default renderer without opt-in still fails closed.
- **Mounted geometry bridge:** `psx/sfle/f3_tk.py` reuses the G1 normalizer, SFLE immutable `LayoutInput`, F2 `TkMeasurementSource` requested sizes, and `NativeGeometryCommitter(GeometryBackend.TK)` to project SFLE's top-left absolute border rectangles into parent-relative `place(x,y,width,height)` coordinates. The native root is explicitly sized from viewport constraints but the SFLE root border box must agree within ≤1px (content-box and padding are not overridden). Native master parentage, no competing `pack/grid`, Tcl/Tk owner thread, generation/liveness, signed fixed-point validation, ≤1px `place_info` readback, rollback on application/readback exceptions and stale-result rejection are enforced.
- **Regression tests with real Tk under xvfb:** Source commit [`85e1758`](https://github.com/Neuri-AI/PSX/commit/85e1758c8ba7feb771c8e753d526a25c8f7cdb3a) passed [F3 selective #38163393093](https://github.com/Neuri-AI/PSX/actions/runs/38163393093) **GREEN** (including Tk job **18 passed**, ten new G2 tests and eight existing tests). [G1 regression matrix #38163393026](https://github.com/Neuri-AI/PSX/actions/runs/38163393026) **GREEN** on the same code SHA. Assertions cover real `ttk` native `place_info` positions, nested parent frames and CSS padding, keyed reuse/reorder, hooks/events/flush, viewport updates, rejection of foreign geometry managers and unsupported primitives, stale generations, and worker-thread violations.
- **Current scope and next steps:** Four target engines have **some native G2 integration**: Headless, Qt (PySide6 tested), Kivy (SDL2 tested), and Tkinter (Tk tested), but the current Qt/Kivy/Tk native SFLE subset is only `Flex`, `Text`, `Button`. Full G2 closure requires the complete `registered component × backend × create/update/move/remove/measure/commit` coverage table, `Native` and custom adapter geometry ports, other Qt binding parity, width-dependent intrinsic remeasurement and actual resize/DPI lifecycle. Scroll viewport/offset ownership remains G3. Do **not** mark G2 closed based on these happy-path adapters.

## F3-G2 iteration — native leaf component expansion and measurement fail-closed (2026-10-11)

**Formal state remains G2 IN PROGRESS, not CLOSED. F3 remains 1/5 gates closed (20%).**

- **Single explicit capability policy:** `psx/sfle/f3_native_coverage.py` centralizes the per-backend G2 leaf allowlist; both mounted renderer creation and Kivy's measurement bridge consult it. An unported host or non-host participant fails with an explicit capability error; its toolkit does **not** take over layout.
- **PySide6 Qt native SFLE coverage:** `Flex`, `Text`, `Button`, `Checkbox`, `Input`, `Slider`, `Radio`, `ProgressBar`, `Select`. New live `QCheckBox`, `QLineEdit`, `QSlider`, `QProgressBar`, `QRadioButton`, `QComboBox` tests assert actual native border rectangles, parent ownership, no competing Qt layout and event/state preservation. `TextArea` remains deliberately outside the allowlist until its native ownership/remeasure contract is certified; Qt-family parity beyond PySide6 remains open.
- **Tkinter native SFLE coverage:** `Flex`, `Text`, `Button`, `Checkbox`, `Slider`, `Radio`, `ProgressBar`. New `ttk.Checkbutton`, `ttk.Scale`, `ttk.Progressbar`, `ttk.Radiobutton` tests verify exact `place_info` geometry, real parent masters, checkbox callback, keyed reuse and no `pack/grid`. `Input`, `TextArea` and custom controls are **not** declared G2-certified in Tkinter.
- **Kivy native SFLE coverage:** `Flex`, `Text`, `Button`, `Checkbox`, `Slider`, `Spacer`. `Checkbox`, `Slider` and `Spacer` do **not** expose valid native intrinsic content measurements; they are admitted only when **both** `layout_width` and `layout_height` are definite pixel dimensions. Their native widget's size/default `size_hint` is never substituted as CSS intrinsic width/height. The SFLE solver receives their explicit CSS sizes and no invented `MeasuredBox`; live Kivy readback verifies all three plus actual checkbox events and bottom-left coordinates. Auto, percentage, min/max-content or absent pixel dimensions fail closed for these controls.
- **Code certificate SHA:** [`8e9df15`](https://github.com/Neuri-AI/PSX/commit/8e9df157b681149c8a37018fcd6dd2419838063b). [F3 selective run #38164507647](https://github.com/Neuri-AI/PSX/actions/runs/38164507647) **COMPLETED SUCCESS**: **167 Core tests**, **30 native Qt tests**, **20 native Tkinter tests**, **3 Kivy integration/regression tests**; platform SFLE Rust/Python/wheel and other selected jobs completed green. [G1 certification #38164507621](https://github.com/Neuri-AI/PSX/actions/runs/38164507621) **COMPLETED SUCCESS** on the same source SHA.
- **Scope that still prevents G2 closure:** complete registry × toolkit × operation coverage, native/custom adapter port protocols, Qt binding family certification, unsupported widget/layout cases, content-width dependent intrinsic remeasurement, automatic resize/viewport/DPI lifecycle, and real native commit/readback under all relevant styles. Scroll offset/clipping remains G3. Historical sections above record earlier subsets at the time; this section and the document header describe the latest G2 coverage.

## F3-G2 iteration — explicit Native/custom measurement + geometry port (2026-10-11)

**Formal state: G2 IN PROGRESS, not CLOSED; overall F3 remains 1/5 CLOSED (20%).**

- **Port contract:** `psx/sfle/f3_external.py` defines immutable `SFLEExternalPort(measure, apply, read)`. `measure(widget, LayoutConstraints)` must return a real `IntrinsicSizes` on the toolkit's owner thread; `apply(widget, Rect)` receives the already-projected **native-parent-relative** border rectangle (top-left in Qt/Tk, **bottom-left in Kivy**); `read(widget)` must return a `Rect` in that same native frame for the ≤1px readback check. Invalid ports/return types fail explicitly; they never cause implicit toolkit layout fallback.
- **Native declaration API:** `Native(..., sfle_port=port)` and `NativeWidget(..., sfle_port=port)` are accepted by opted-in Qt (PySide6 proven), Kivy and Tkinter. Without a `SFLEExternalPort`, a `Native` leaf rejects mounting *before calling the native factory*. Props in the `layout_*` / flex metadata namespace never flow into the native widget-property adapter. Existing native ownership, borrowed widget detachment, event subscriptions, and reconciler identities remain toolkit-owned.
- **Custom host adapter API:** `renderer.register_adapter("CustomBadge", CustomAdapter())`, where the adapter exposes `sfle_port = port` and implements normal native lifecycle methods. The external host is a **leaf** (no children needing layout). Builtin controls not yet migrated to G2 remain explicitly **not certified** even when they have older non-SFLE custom native adapters. All `Native` and registered custom-host leaves still participate in the same key-aware immutable SFLE snapshot; the provider does **not** calculate sibling layout.
- **Geometry authority:** The F2 `NativeGeometryCommitter` accepts explicit `external_ports`, retains its signed 1/64px-grid preflight, computes all toolkit parent-relative placements from SFLE border boxes, and delegates only the actual native write. All three production bridges (`f3_qt.py`, `f3_kivy.py`, `f3_tk.py`) perform external measurement with generation checks, read back via the external port, and restore prior native geometry on commit/readback failures. F2's neutral engine and Chromium precision thresholds are unchanged.
- **Minimal example (Qt):**
  ```python
  from PySide6.QtWidgets import QLabel
  from psx import Flex
  from psx.core.native import Native
  from psx.sfle.f3_external import SFLEExternalPort
  from psx.sfle.model import IntrinsicSizes, Rect

  port = SFLEExternalPort(
      measure=lambda w, c: IntrinsicSizes(12, 30, 10, 20, 30, 20),
      apply=lambda w, r: w.setGeometry(round(r.x), round(r.y),
                                       round(r.width), round(r.height)),
      read=lambda w: Rect(w.x(), w.y(), w.width(), w.height()),
  )
  element = Flex(
      Native(QLabel, renderer="pyside6", sfle_port=port,
             layout_width="80px", layout_height="24px",
             flex_basis="80px", flex_shrink=0),
      width="160px", height="80px",
  )
  # Mount element using PySide6Renderer(sfle_constraints=...) and Reconciler.
  ```
- **Certification:** Code commit [`63544c6`](https://github.com/Neuri-AI/PSX/commit/63544c69b8879cd1081341520547628e9ba8b34c) passed [F3 selective #38166068973](https://github.com/Neuri-AI/PSX/actions/runs/38166068973) **COMPLETED SUCCESS** (**175 Core tests; 35 PySide6; 23 Tk native; 3 Kivy subprocess pytest functions covering real SDL2 scenarios**), and [G1 Python matrix #38166068974](https://github.com/Neuri-AI/PSX/actions/runs/38166068974) **COMPLETED SUCCESS** on that same SHA. Direct/native tests cover `Native` on all three GUI backends, custom registered leaves on all three, foreign/missing port preflight, invalid measurement/readback, F2 mixed builtin/external projection and Qt geometry restoration on bad readback. The first CI attempt exposed an import-order cycle in F2 and an incorrect unported-builtin diagnostic; both were corrected before this certified SHA.
- **Open for G2 closure:** remaining custom lifecycle / borrowed widgets matrix, unsupported per-backend builtins and port variations, all Qt bindings, actual automatic viewport resize, width-dependent intrinsic remeasure and DPI, complete `registry × backend × operation` table, rollback under toolkit destruction, and remaining full cross-platform acceptance. **This port increment is GREEN but G2 is not formally closed.** G3 continues to own full Scroll offsets/events and clipping.

## F3-G2 iteration — mandatory four-binding Qt SFLE parity (2026-10-11)

**Formal status: G2 IN PROGRESS; F3 officially 1/5 gates closed (20%). This is Qt binding parity for the currently supported G2 leaf subset, not full platform parity.**

- **Implementation reused:** All four concrete Qt renderer facades — `PySide6Renderer`, `PyQt6Renderer`, `PyQt5Renderer`, `PySide2Renderer` — reuse the same `QtRenderer`, production `QtSFLEFlexAdapter`, `QtMeasurementSource`, F2 `NativeGeometryCommitter(GeometryBackend.QT)`, immutable `LayoutInput`, generation/owner-thread guards, explicit `Native` and registered custom `SFLEExternalPort(measure,apply,read)`. No separate Qt5 CSS solver or `QBoxLayout` fallback was added.
- **Actual defect repaired:** `Native()` previously rejected `renderer="pyside2"` despite the Qt renderer correctly supporting it. `psx/core/native.py` now accepts PySide2 and correctly infers it from `PySide2.QtWidgets` classes/instances (including existing borrowed widget ownership behavior). This defect was discovered by the first live PySide2 matrix run, not papered over by a skip.
- **Binding matrix with explicit platform/Python constraints:** `tests/test_f3_g2_qt_family.py` is executed in a **fresh process per binding**, all with actual widgets under Ubuntu `QT_QPA_PLATFORM=offscreen`:
  | Binding | Tested Python | G2 common parity |
  | --- | --- | --- |
  | PySide6 / Qt 6 | 3.12 | **14/14 PASS** |
  | PyQt6 / Qt 6 | 3.12 | **14/14 PASS** |
  | PyQt5 / Qt 5 | 3.12 | **14/14 PASS** |
  | PySide2 / Qt 5 | **3.10 only** | **14/14 PASS** |

  PySide2's last published wheel series is `5.15.2.1` (January 2022), with interpreter tags up through Python 3.10. The CI pins `PySide2==5.15.2.1` in an independent Python 3.10 Linux x86-64 job; no unsupported 3.11–3.13 PySide2 claim is made. The other Qt bindings are tested on Python 3.12, not yet every supported OS/Python combination.
- **Parities exercised:** real `QWidget.geometry` and correct native parent for nested Builder and Markup `Flex` with padding/gaps; Text/Button; Checkbox/Input/Slider/Radio/ProgressBar/Select native types and exactly matching border rectangles; `key` moves with stable widget identity; coalesced hooks/state and callback rebinding; explicit viewport recomputation; owning UI thread; valid/invalid SFLE generation; reject unported primitive and non-SFLE `Flex`; `Native` explicit and inferred toolkit binding plus `SFLEExternalPort`, and registered custom leaf adapters with actual native projection/readback. `ProgressBar` checks **normalized progress**, not raw Qt scaled integer units.
- **CI enforcement:** `.github/workflows/f3-selective.yml` has a required four-cell `qt-parity` job; the `F3 required CI conclusion` also fails when its aggregate is not successful, even if the pre-existing PySide6 native suite passes. `scripts/ci/impact.py` now sends both Qt-family parity test changes and central F3 workflow changes through Qt testing, with explicit router regressions.
- **Certificate:** Source commit [`32050c0`](https://github.com/Neuri-AI/PSX/commit/32050c0b5af59f0997e0718c7d2f029025870086) passed [F3 selective CI #38167340136](https://github.com/Neuri-AI/PSX/actions/runs/38167340136) **COMPLETED SUCCESS** with all four binding jobs (14 tests each) and **35 existing PySide6 native tests**; [G1 certification #38167340147](https://github.com/Neuri-AI/PSX/actions/runs/38167340147) also **COMPLETED SUCCESS** on the identical source SHA.
- **Open for full G2 closure:** Qt OS × Python × toolkit-version matrix beyond the certified Linux subset; remaining components and custom/borrowed lifecycle cases; automated native window resize propagation; width-dependent text intrinsic remeasurement; DPI scaling; complete registry × backend × operation tests. Cross-platform final acceptance remains **G5**.

## F3-G2 iteration — automatic real native viewport resize (2026-10-11)

**Gate state: G2 IN PROGRESS, not CLOSED. F3 is still 1/5 gates officially closed (20%).**

- **Native lifecycle, not another sizing algorithm:** Each backend attaches a native viewport-size observer **only after the first successful mounted SFLE commit**. On native resize it schedules a new SFLE generation for the **existing** `MountedInstance` tree (without re-executing hooks or remounting controls); the F2 `NativeGeometryCommitter` remains the only child geometry writer. Native root size/Window ownership stays with the toolkit and app host, not the SFLE projector.
- **Qt / PySide6, PyQt6, PyQt5, PySide2:** A binding-native `QObject.eventFilter` watches the actual root `QWidget` for `QEvent.Resize`. The root's initial native size is recorded as the baseline, so Qt's delayed first-show/realization event cannot silently replace the initial explicit constraints. Meaningful size changes are coalesced by a **16 ms trailing-edge frame window**, then `set_sfle_constraints()` + `commit_layout()` runs on the Qt UI thread. The filter is disconnected at `invalidate_layout()`; pending callbacks are invalidated by an epoch number. Exceptions stay out of the Qt C++ event boundary and are logged/captured in `_sfle_resize_error`.
- **Kivy:** A root `Widget.size` binding schedules a single `Clock.schedule_once(..., 0)` commit for latest size. An actual Kivy `Window.on_resize` listener also updates the SFLE root size **when the widget is attached to that Window**. The already-certified Kivy bottom-left parent-relative projection remains unchanged. Unmount unbinds both `size` and `on_resize` and cancels queued Clock events, including callbacks after detach.
- **Tkinter:** Only real **host** `<Configure>` events are observed (not child `ttk.Frame` changes caused by SFLE's own `place()` output). Baseline host dimensions filter out initial realization, and `after_idle()` coalesces host size changes. The previously mounted root `ttk.Frame` gets its explicit viewport size updated through `set_sfle_constraints()`, followed by one F2 geometry pass. `invalidate_layout()` and `close()` cancel the `after_idle` task and remove only this renderer's binding, retaining other host listeners.
- **Responsive CSS contract:** Use `<Flex width="100%" height="100%" ...>` for the viewport-filling root. A root with fixed CSS `width`/`height` remains fixed under CSS semantics; native host resize does **not** rewrite source CSS sizes. Existing explicit `set_sfle_constraints()` and manual `commit_layout()` APIs remain supported.
- **Native certification:** Code [`c88cbd0`](https://github.com/Neuri-AI/PSX/commit/c88cbd0e29a0d74dce6475138a7293e269592fe8) passed [F3 selected CI #38197333708](https://github.com/Neuri-AI/PSX/actions/runs/38197333708) **COMPLETED SUCCESS** (four real Qt binding parity jobs **16 passed each**, PySide6 legacy native **35 passed**, Tk native **25 passed**, Kivy SDL2 native **4 passed**), and [G1 Python matrix #38197333717](https://github.com/Neuri-AI/PSX/actions/runs/38197333717) **COMPLETED SUCCESS** on the same exact source SHA, including Chromium, Rust/Python, native wheel and platform jobs selected. New tests assert latest-only native resize, correct new child geometry, unchanged mounted widget identities, no alternate native layout, tolerance ≤1px and teardown invalidation.
- **Still open before G2 closure:** Width-constrained intrinsic text / image remeasurement and dependency propagation, DPI/device pixel scaling and host content/safe-area differences, full built-in/native/custom/borrowed component matrix and operation/liveness failures, and broader platform/Python coverage. These are **not certified by resize event wiring alone**. G3 retains Scroll/clipping/offset responsibilities.

## F3-G2 iteration — real post-flex width-sensitive intrinsic remeasurement (2026-10-11)

**State: G2 IN PROGRESS; F3 officially remains 1/5 gates CLOSED (20%).**

- **Neutral coordinator:** `psx/sfle/f3_width_remeasurement.py` introduces `compute_width_dependent`, `seed_unconstrained_width_measurements` and `auto_height_measurement_ids`. For width-dependent **leaf / auto-height** participants only, the renderer submits its immutable `LayoutInput` to the current SFLE engine's **`compute_provisional`**. The provisional **actual leaf content-box width** (not the root's available viewport or an inherited guessed width) becomes a UI-thread native measurement constraint. Revised `MeasuredBox` metrics carry the current generation and definite measured content width. SFLE recomputes; repeated width passes stop when every width converges to **0.01px**, with an explicit bounded maximum of 5 passes. The final `compute` is checked against the measured widths before any native geometry writes. Stale/invalid revisions, foreign return types, unavailable provisional ABI, width oscillation and measurement failures **fail closed**; no provisional boxes are committed.
- **Qt all 4 bindings:** `QLabel.setWordWrap(True)` is enabled only for opted-in SFLE `Text`. `QtMeasurementSource.measure_width` asks the same live Qt `QLabel.heightForWidth(width)` / size-hint adapter for metrics after SFLE resolves actual content width. Fully implemented on **PySide6, PyQt6, PyQt5, PySide2** (using each binding's existing owner UI thread and no `QLayout`). The F3 parity suite proves a long multiline `Text` gains native height as width narrows from 160 to 90 and that the following button is repositioned **without remount**; verifies restoration on expansion. An additional test on **all four Qt bindings** confirms explicit external `SFLEExternalPort.measure(widget, constraints)` can adjust a `Native` leaf's auto height at widths 160 versus 90 and reposition its sibling. Controls with definite `layout_height` are not remeasured for auto height.
- **Tkinter:** `TkMeasurementSource` temporarily clears existing `wraplength` to recover the unconstrained requested inline basis for a later viewport change, then restores it (including on failure). Width measurement temporarily applies the actual post-flex `wraplength`; only after a successful SFLE solution does the native commit assign the same wraplength for **visible multiline rendering**. Native readback / rollback restore previous wrap and geometry when needed. Real `ttk.Label` and following `ttk.Button` change native size/position with width 160→90→160, and existing F2 synthetic Tcl requested-size tests remain GREEN.
- **Kivy:** For measured `Text` only, the bridge obtains a true **unconstrained natural texture size**, then uses a temporary `Label.text_size=(actual_content_width,None)` followed by `texture_update()` to obtain the wrapped block height on the owner UI thread. Temporary measurement settings are restored in `finally`; after successful SFLE projection `text_size` is set to the certified width for actual Kivy native painting, with prior texture configuration restored on geometry/readback failure. The real SDL2 test checks label height increases when content width narrows and the subsequent native button reflows in the Kivy **bottom-left** coordinate frame. No Kivy `BoxLayout` geometry fallback is admitted.
- **Native/custom:** Existing `SFLEExternalPort(measure, apply, read)` is also admitted to the width-specific measurement phase for an external **leaf with automatic height**. The callback receives `LayoutConstraints(AvailableSize(leaf_content_width, True), AvailableSize(None, False))`; its measured intrinsic height is fed back into the solver. Native/custom factory, readback, parentage and rollback paths remain unchanged. Ports with explicitly fixed heights continue their existing no-remeasure behavior.
- **Latest certified code:** [`ace5d4a`](https://github.com/Neuri-AI/PSX/commit/ace5d4ad979adba81c5b82952859bf4e02d03159), [F3 selective run #38202135054 GREEN](https://github.com/Neuri-AI/PSX/actions/runs/38202135054) and [G1 Python certification #38202135399 GREEN](https://github.com/Neuri-AI/PSX/actions/runs/38202135399), **both completed SUCCESS on the same SHA**. Counts: **182 Core**, **35 original PySide6**, **18 for each of PySide6/PyQt6/PyQt5/PySide2 Qt parity (72 total)**, **26 Tk native**, **5 Kivy SDL2 subprocess tests**. Full SFLE F2 regression and existing browser oracle jobs are also GREEN.
- **Not yet certified:** Full Chromium golden-parity fixtures for multiline wrapping at multiple widths, non-Text/complex replaced controls, images and rich text, font/DPI/scale-dependent exact measurement and cross-platform native binding matrices, borrowed widget/custom lifecycles and the full primitive×renderer×operation matrix. Passing an existing Chromium workflow does **not** mean the newly implemented multiline cases have a Chromium oracle fixture. G2 remains **IN PROGRESS**.

## F3-G2 iteration — device-pixel scale policy and native physical readback (2026-10-11)

**Formal G2 status remains IN PROGRESS. F3 stays 1/5 gates CLOSED (20%).**

- **Canonical units:** SFLE's `LayoutUnit` and `LayoutResult` remain in **CSS logical px**, with fixed 1/64px precision. The existing F2 `NativeGeometryCommitter` still projects parent-relative coordinates, including Kivy's Y inversion, and controls widget positioning. A separate `psx/sfle/native_pixel_space.py` `DevicePixelSpace(scale, backend)` now converts a toolkit-native `Rect` into actual **device pixel bounds**, snapping the four **edges** independently at each display ratio; it never re-solves CSS boxes or rounds individual sizes in isolation.
- **Qt / PySide6, PyQt6, PyQt5, PySide2:** `QWidget.setGeometry()/geometry()` accepts/returns **device-independent native Qt logical coordinates**, even when `QWidget.devicePixelRatioF() > 1`. The Qt platform itself converts these to physical pixels; multiplying positions/sizes by DPR before `setGeometry` would **double-scale**. The bridge queries the mounted root `devicePixelRatioF()` (with Qt5 legacy getter fallback) **for each commit**, then compares expected versus actual native rectangles in both native logical and physically projected pixels, without modifying SFLE's 1/64px boxes.
- **Kivy and Tkinter:** `Widget.pos/size` and `place(x,y,width,height)` already use their toolkit's native window pixel coordinates, respectively. Kivy `Metrics.density` controls `dp/sp` conversion in styling/text and Tk `tk scaling` controls pixel-per-point conversions/fonts; blindly multiplying the existing native widget geometry by either is incorrect. The per-backend contract deliberately uses **1 native coordinate unit → 1 physical coordinate pixel** for their native widget geometry readbacks. Font/theme/DPI-induced **intrinsic measurement changes** continue to be measured on the owning toolkit UI thread. This policy does **not** yet certify universal CSS-DP parity across operating-system DPI configurations.
- **Native/custom:** `SFLEExternalPort.apply/read` continue to use already-projected **native-parent-relative toolkit coordinates** (Qt DIPs vs Kivy/Tk window pixels), never raw frame-buffer pixels. The native port must not multiply those values again by DPR. Its readback passes the same physical audit as the built-ins.
- **Transaction:** `f3_qt.py`, `f3_kivy.py`, `f3_tk.py` record both `geometry_commit_error` (in widget API coordinates, max 1) and `renderer._sfle_physical_commit_error` (physical-pixel difference, bounded by the physical counterpart of the 1-native-unit tolerance). Nonfinite/negative DPR, invalid backend geometry, stale generation and native parentage fail before committing; readback violations retain existing rollback. Logical output is unchanged by DPR. No new F2 solver/rounding was introduced.
- **Certification:** Source [`b0f589f`](https://github.com/Neuri-AI/PSX/commit/b0f589ffcbc5f93f83fce1c1d7d6a3ccc143ec1a) passed [F3 selective #38203902046](https://github.com/Neuri-AI/PSX/actions/runs/38203902046) **COMPLETED SUCCESS** and [G1 Python matrix #38203902052](https://github.com/Neuri-AI/PSX/actions/runs/38203902052) **COMPLETED SUCCESS**, **same source SHA**. `tests/test_f3_g2_native_pixel_scale.py` exercises DPI ratios 1×, 1.25×, 1.5×, 2×, 2.5× and 3×, edge continuity, signed/invalid scale rejection and native-vs-physical error. All four isolated real Qt binding CI jobs now run **19 tests at normal scale + 19 tests at `QT_SCALE_FACTOR=1.5` each** (76 at normal + 76 at 1.5×), in addition to **35 PySide6 native tests**, **27 Tk native**, **5 SDL2 Kivy**, **206 Core** and the pre-existing browser/F2 geometry/native wheel checks.
- **Still OPEN in G2:** Detect and invalidate text/measurement caches for live runtime **screen migration / DPI changes without a window resize**; verify portable font metrics and actual visual CSS-DP size equivalence across disparate hardware DPI configurations in Kivy/Tk; new multi-DPI screenshot/golden fixtures against Chromium; complete OS×toolkit and primitive×backend×operation matrix and owned/borrowed lifecycle. The current increment certifies **device-coordinate projection and no-double-scaling**, not all possible high-DPI rendering permutations.

## F3-G2 increment — Qt native TextArea post-flex sizing and editing (2026-10-11)

**G2 stays IN PROGRESS. F3 has 1/5 official gates closed (20%).**

- **Qt backend coverage:** `TextArea` is admitted to the F3-G2 native leaf
  capability policy for **PySide6, PyQt6, PyQt5 and PySide2**, retaining the
  existing `QPlainTextEdit` native primitive, `on_change`, keyed identity,
  focus, cursor/selection and native editing. Tk and Kivy `TextArea` remain
  explicitly unported in the **SFLE path** and are not silently certified.
- **Real constrained measurement:** `QtMeasurementSource` creates a detached
  `QTextDocument` with the live edit's font, plain text, document margins and
  wrap policy. Its height is measured at the **actual leaf content-box width**
  delivered by the existing provisional SFLE pass. The live edit's document,
  signals, focus, cursor and scrolling are untouched during measurement; no
  alternative widget layout or fixed post-hoc geometry is introduced.
- **CSS contract:** `layout_height` definite overrides intrinsic auto-height;
  auto-height uses the existing bounded SFLE convergence, generation and
  readback/rollback gates. `QPlainTextEdit` still handles text painting/input
  and native internal scrollbars; no F3-G3 outer Scroll work is claimed.
- **Live edits:** `QPlainTextEdit.textChanged` schedules at most one deferred
  SFLE remeasurement per event-loop turn, never recursively inside Qt signal
  emission. Explicit/reconciler commits supersede pending remeasurement;
  unmount invalidates queued callbacks via an epoch. Diagnostic errors are
  retained in `_sfle_textarea_error` rather than crossing C++ boundaries.
- **Real Qt tests:** `tests/test_f3_g2_qt_family.py` checks the same editor
  reflows at width 160 → 90 → 160, sibling geometry follows, text, selection,
  focus and callback behavior survive, definite CSS height remains 36px,
  callbacks rebind, native text editing triggers remeasurement without a
  Reconciler remount, and no competing `QLayout` takes ownership. All four
  Qt bindings certify the same assertions, including `QT_SCALE_FACTOR=1.5`.
- **Proof:** Code commits
  [`079b5f5`](https://github.com/Neuri-AI/PSX/commit/079b5f5631ff84788e9996226be839212bd4314b)
  and [`9de4ea1`](https://github.com/Neuri-AI/PSX/commit/9de4ea1a1cd0ca72cc009a3d329c6a9244084150).
  [F3 selected CI #38206256655](https://github.com/Neuri-AI/PSX/actions/runs/38206256655)
  and [G1 contract CI #38206256646](https://github.com/Neuri-AI/PSX/actions/runs/38206256646)
  **COMPLETED SUCCESS on the same source SHA**. Each of the four Qt
  parity jobs passed **22 tests at standard DPI and 22 at 1.5×** (176
  Qt parity executions total); the separate native Qt job was GREEN.
- **Still open for G2:** complete registry × backend × operation and
  owned/borrowed lifecycle coverage; native `TextArea` on applicable Tk/Kivy
  combinations; live font/theme/screen DPI invalidation; complex image and
  other intrinsic control support; complete OS/platform matrix. This
  increment alone does **not** close G2.
 
## F3-G2 increment — Tkinter + Kivy TextArea native width reflow (2026-10-11)

**State: G2 IN PROGRESS; F3 1/5 gates closed (20%).** This is one
**combined** backend increment, not two independent certifications.

- **G2 capabilities:** `psx/sfle/f3_native_coverage.py` admits
  `TextArea` alongside the existing toolkit-native leaf controls in **both
  Tkinter and Kivy**. Legacy `Input` remains explicitly unported in those
  particular SFLE paths. Qt TextArea was previously certified on all four
  bindings; neither Row/Column cleanup nor the G3 Scroll migration is
  claimed here.
- **Tk intrinsic size:** `TkMeasurementSource` asks a temporary real
  `tk.Text` for the native `displaylines` count with the source widget's
  text, font, wrap and paragraph spacing/padding. It uses Tk's native font
  metrics for natural inline width and a new **post-flex leaf content-box
  width** for wrapped block height. An empty Tcl display-line count is
  correctly treated as zero transitions (one line). The measurement probe
  is destroyed after each reading: the live editor's selection, insertion
  cursor, content and native parent-relative `place()` are untouched.
  The Tk GUI import remains lazy to preserve G1 backend isolation.
- **Kivy intrinsic size:** `KivyMeasurementSource` uses a detached
  native `TextInput(multiline=True)` with the real font, text, padding,
  wrap and line spacing. Its synchronous native wrapped-line refresh and
  `minimum_height` feed the existing immutable SFLE width-dependent
  measurement path. No fake Label texture or Kivy `BoxLayout` sizing
  substitutes for SFLE; the mounted editor remains intact.
- **Live editing/lifecycle:** real Tk `<<Modified>>` events now use
  `bind()`/`unbind()` instead of treating a virtual event as a Tk
  `configure` option; they update the existing portable `on_change`
  subscription. Tk and Kivy schedule coalesced deferred SFLE commits
  after native edits, retain keyed widget identity and existing editor
  state, and invalidate pending callbacks on explicit commit/disposal.
  Programmatic TextArea updates do not fake user typing callbacks.
- **Sizing and coordinate authority:** CSS fixed `layout_height` still
  overrides auto height, as verified by real controls. The shared
  `compute_width_dependent` coordinator retains bounded iterations,
  current-generation checks, cross-backend geometry projection,
  ≤1 native-pixel readback tolerance, and rollback on failures.
  Tk uses top-left `place()`; Kivy retains its parent-relative bottom-left
  projection.
- **RED → GREEN evidence:** Initial executions uncovered Tk's valid
  zero-transition display-line response and a Kivy test that incorrectly
  set a **horizontal** flex basis in a **vertical** stack. Both were
  corrected, rather than removing supported behaviors or bypassing tests.
- **Certified source SHA:** [`44888af`](https://github.com/Neuri-AI/PSX/commit/44888af9a127d518f4d2ebe22ed4473d0a04e157).
  [F3 selective #38207227555](https://github.com/Neuri-AI/PSX/actions/runs/38207227555)
  **COMPLETED SUCCESS**, including **29 real Tk tests**, **7 real
  SDL2 Kivy subprocess tests**, Qt bindings, SFLE core, Chromium oracle,
  Rust/Python differential and native wheels on Windows/macOS/Linux where
  selected. [G1 matrix #38207227565](https://github.com/Neuri-AI/PSX/actions/runs/38207227565)
  **COMPLETED SUCCESS** on the same exact SHA (Python 3.10–3.13).
- **Remaining G2 work:** certify the rest of the builtin
  registry × backend × operation matrix, measured native image and
  complex-control dimensions where admitted, borrowed/custom lifecycle
  and failure modes, dynamic fonts/theme/screen DPI invalidation, plus
  the required platform matrix. G2 remains open; F3 global progress
  remains 1/5 official gates.
 
## F3-G2 increment — native Image in Qt, Tkinter and Kivy (2026-10-11)

**F3-G2 remains IN PROGRESS; official F3 gate progress stays 1/5 (20%).**

- **Coverage:** Image is admitted in the explicit G2 native-leaf
  capability policy for **Qt, Tkinter and Kivy**. Every source has a real
  intrinsic decoder/measurement port: loaded `QPixmap`, loaded Pillow
  image or Tk `PhotoImage`, and loaded Kivy texture (with synchronous
  local `CoreImage` fallback). Missing/undecodable native sources fail
  `UNSUPPORTED_MEASUREMENT`: no fabricated default widget dimensions.
- **SFLE is the sole geometry authority:** the existing immutable SFLE
  snapshot uses the source's real natural pixel size, modified only by the
  established portable `Image.width` / `Image.height` contract.
  `layout_width`, `layout_height`, Flex sizing and available constraints
  remain SFLE's responsibility. This **does not implement** the separately
  deferred SFLE-CSS-01 replaced-element intrinsic aspect-ratio rules.
- **Qt (PySide6, PyQt6, PyQt5, PySide2):** in SFLE mode the existing
  `QLabel` no longer calls `setFixedSize`; it composes its `contain`,
  `cover`, `fill` or `none` painting into the **already committed**
  SFLE rectangle, with Qt5/Qt6-compatible enum names. Normal non-SFLE
  Image behavior remains unchanged.
- **Tkinter:** the source's pixels are measured independently of the
  painted label size. After `place()`, Pillow recomposes the requested
  fit into the SFLE rectangle. Pillow is optional for users, but required
  for arbitrary scaling/cropping; without it native-size PNG with
  `contain`/`none` remains possible and unsupported scaling fails
  explicitly. The real Tk image CI job installs Pillow.
- **Kivy:** `kivy.uix.image.Image` supplies actual native texture
  dimensions and keeps ownership of `fit_mode` painting, but SFLE
  owns widget width, height and bottom-left position. In SFLE mode
  `_on_texture` must not call `widget.size = ...`.
- **Native tests:** decoded local PNG fixtures certify natural-size
  geometry, CSS width/height overrides, keyed identity on update,
  paint destination dimensions where accessible, no competing layout
  manager, and explicit missing-source diagnostics. Old Image-as-unported
  assertions were replaced by genuine unsupported Divider checks.
- **Source and CI evidence:** certified source
  [`befcd5e`](https://github.com/Neuri-AI/PSX/commit/befcd5efa19fb773e7a08a502ede54daedbaea2a),
  [F3 selective #38209152288](https://github.com/Neuri-AI/PSX/actions/runs/38209152288)
  **COMPLETED SUCCESS**, and
  [G1 certification #38209152156](https://github.com/Neuri-AI/PSX/actions/runs/38209152156)
  **COMPLETED SUCCESS** on the exact same SHA. Tkinter **31 native
  tests** and Kivy **8 SDL2 subprocess tests** passed; four Qt
  bindings each passed **24 parity tests at 1× and 24 at 1.5×**,
  totalling **192 Qt parity executions**. Selected core/Chromium/
  Rust-Python and native wheel jobs were GREEN.
- **Still open:** complete registered-component × backend × operation
  and native/custom lifecycle matrices, invalidation on image file
  change without a PSX prop change, complex font/theme/DPI changes,
  and F3-G3 through G5. Do not label G2 as CLOSED based on this increment.

## F3-G2 increment — Link, Badge, leaf Divider and Spacer across Qt/Kivy/Tk (2026-10-11)

**Status: increment certified, G2 itself IN PROGRESS. F3 still 1/5 gates closed.**

- **Ports/policy:** All four existing PSX builtins are admitted by
  `G2_LEAF_TYPES` in Qt, Kivy and Tk. They use the reconciler's
  keyed/native handle graph, immutable SFLE snapshot, Rust-primary engine
  with Python fallback, F2 parent-relative coordinate projection and
  readback/rollback. **No new portable component or contract** was added.
- **Link:** Native Qt QPushButton, Tk Label and Kivy Button retain
  their existing focus/interaction semantics and source `on_click`
  subscriptions. SFLE-enabled Qt and Kivy update paths no longer
  resize their native widget independently; intrinsic text hints/textures
  remain measurable and SFLE owns the outer rectangle.
- **Badge:** Qt PaintedBadge now reports genuine font-derived
  `sizeHint`/`minimumSizeHint` instead of fixing size under SFLE.
  Kivy Badge retains separate natural glyph/padding dimensions
  (`_psx_natural_size`) and does not override a committed rect.
  Tk Canvas uses its native theme/font request while `place()`
  remains SFLE-owned.
- **Divider leaf:** SFLE resolves its zero free-axis intrinsic
  dimension and `thickness`-sized cross axis. Qt uses a direct QFrame
  line **without QHBoxLayout/QVBoxLayout, setFixedSize or secondary
  geometry ownership**; Tk Canvas and Kivy canvas line paint inside
  committed rectangles. Orientation/thickness remain portable props.
  **Important limitation:** a Divider containing children still has
  an older native-internal child layout. The SFLE route explicitly rejects
  it *before mounting* with a stable capability error; supporting
  Divider-with-child using SFLE child boxes remains a separate G2 item.
- **Spacer:** A real intrinsic zero-size leaf in all three backends,
  independent of QWidget/ttk.Frame/Kivy Widget defaults. In particular,
  Kivy no longer requires two explicit px dimensions for Spacer.
  SFLE's own `flex_grow` and `flex_basis` distribute free space; neither
  the native adapter nor a hidden layout performs stretching.
- **Native real-toolkit tests:** mixed five-element Flex trees exercise
  exact logical and ≤1px applied native geometry (including Kivy
  bottom-left Y), true spacer growth, line-thickness updates,
  preserved keyed native identities, SFLE authority and event rebind
  on Qt/Kivy. Policy tests enforce explicit child Divider rejection
  and preserve negative unported-builtin checks.
- **Source certificate:** [`844d379`](https://github.com/Neuri-AI/PSX/commit/844d379f4043305b83812e0e8786863e12ccdcf7).
  [F3 #38210513225](https://github.com/Neuri-AI/PSX/actions/runs/38210513225)
  **COMPLETED SUCCESS**; [G1 #38210513235](https://github.com/Neuri-AI/PSX/actions/runs/38210513235)
  **COMPLETED SUCCESS** at identical SHA. Qt family: **25 tests × 4 bindings
  × 2 DPI scales = 200 passing executions**, Tk: **32 native tests**,
  Kivy: **9 SDL2 subprocess tests**. Required selective CI conclusion
  and selected core/geometry/Rust-differential/Chromium/wheel jobs passed.
- **Next G2 items:** full registry-backed coverage census;
  lifecycle/operation matrix and owned/borrowed/custom widget variants;
  interactivity ports (Switch/SpinBox/Select etc.); structural
  Box/RadioGroup/Fragment and Divider child semantics; basic Scroll
  viewport/host binding; invalidation on content, theme, font and
  screen DPI. Full scroll behavior is G3, legacy Row/Column removal is G4,
  and full platform/matrix certification is G5.
 
## F3-G2 increment — native Switch, SpinBox and Select on Qt/Kivy/Tk (2026-10-11)

**State: INCREMENT CERTIFIED; G2 NOT CLOSED. F3 remains 1/5 gates closed (20%).**

- **Existing portable controls:** No new host components or public props:
  `Switch` (`checked`, `label`, `size`, `on_change`), `SpinBox`
  (`value`, bounds, `step`, `decimals`, `on_change`) and `Select`
  (typed `options`, `value`, `on_change`) now join the explicit
  native F3-G2 leaf allowlists for Qt, Tkinter and Kivy.
- **Single layout authority:** Qt `AnimatedSwitch` now reports
  label-aware native `sizeHint`/`minimumSizeHint` and releases its
  constructor's fixed-size bounds under SFLE. Qt composite SpinBox uses
  `QHBoxLayout` for its **internal minus/editor/plus chrome only**,
  with its outer `QWidget` width/height allocated by SFLE. The Qt
  transaction still rejects `QLayout` for all other unapproved SFLE
  participants and any declarative PSX tree's competing layout.
- **Kivy intrinsic ports:** Native composite Switch measures from
  its actual Kivy label texture and portable track size, and SpinBox
  measures from its explicit internal-control natural size; neither
  overwrites the outer BoxLayout size during SFLE-driven updates.
  Spinner/Select uses native text texture measurement. All three
  keep actual native widgets and parent-relative bottom-left projection.
- **Tkinter:** Existing `ttk.Frame` Switch and SpinBox are measured
  from actual requested native dimensions; Select is the real
  `ttk.Combobox` with virtual event binding. Internal Tk `pack`
  only arranges private Switch/SpinBox subcontrols, never PSX siblings.
  SFLE still projects host rectangles using `place()`.
- **Controls/events:** Qt, Kivy and Tk tests verify keyed identity,
  parent ownership, exact SFLE/native rectangles, preserved
  `checked`, numeric values, selected option and `on_change`
  callbacks across controlled update/rebind. Prop synchronization
  does not emit spurious changes.
- **RED evidence and correction:** First CI exposed Qt falsely
  rejecting SpinBox's internal QLayout and old unported-widget tests
  treating now-supported Switch as unsupported. A second execution
  exposed `Box` was not exported in the PSX public Python namespace;
  stable negative tests now use public `RadioGroup`, genuinely
  unsupported until the future container increment. The final source
  commit passes all mandatory jobs; these were corrected, not skipped.
- **Code certificate:** [`5d50e95`](https://github.com/Neuri-AI/PSX/commit/5d50e95a5896d4be1a9ce0e3049e58049ad62ea6).
  [F3 selective #38211894255](https://github.com/Neuri-AI/PSX/actions/runs/38211894255)
  **COMPLETED SUCCESS**; [G1 contract #38211894319](https://github.com/Neuri-AI/PSX/actions/runs/38211894319)
  **COMPLETED SUCCESS** at the exact same code SHA. Qt **208 parity
  executions**, Tk **33 native tests**, Kivy **10 SDL2 subprocess
  tests** and required selected source/native-wheel jobs all passed.
- **Open gate blockers:** Container-aware `Box`, `RadioGroup`, and
  Divider-with-child geometry, G2 basic Scroll viewport binding,
  complete built-in × backend × operation/lifecycle census, native/
  borrowed/custom widget teardown and invalidations for changed
  font/theme/DPI/image source. None is mislabeled G2 CLOSED;
  full scrolling remains G3 and Row/Column removal remains G4.
 
## F3-G2 increment — SFLE structural Box, RadioGroup, Divider with Text child (2026-10-12)

**Increment IMPLEMENTED with native Qt/Tk/Kivy certification; G2 overall IN PROGRESS, official F3 closure 1/5 (20%).**

- **Structural engine contract:** The existing normalized/mounted tree is
  preserved. `prepare_f3_snapshot` maps the three *structural* nodes to
  SFLE Flex container semantics while retaining stable source VNode
  identities/handles and parent-relative projection. `Box` uses a
  single-child full-size passthrough, `RadioGroup` maps orientation,
  spacing and padding to SFLE properties, and `Divider` with child
  centers its child in the separator rectangle. This does not introduce
  or use another sizing engine.
- **Box is internal:** Its existing `psx.core.vnode.Box` implementation
  remains used by framework integration and is **not exported as a new
  public portable component**. Native hosts in Qt, Tk and Kivy no
  longer use QBoxLayout/pack/BoxLayout for its child in SFLE mode;
  all have explicit SFLE parent/child geometry, preserving legacy
  behavior when SFLE is not opted into.
- **RadioGroup:** Qt uses QButtonGroup only for native selection events
  (no layout), Tk uses its shared typed Radio variable and `place()`
  (not pack), and Kivy uses a plain Widget host instead of an owning
  BoxLayout. Kivy Radio obtains an intrinsic size from its real
  checkbox and measured Label texture. SFLE alone allocates child
  rectangles. Values remain controlled and the group retains
  on_change semantics. Invalid child node types fail explicitly.
- **Divider with Text:** The SFLE container determines the child's
  allocation; native adapters draw the decorative line *around* the
  child's final rectangle. Qt uses a QFrame subclass with painter,
  Tk Canvas uses `place_info` and never `create_window()`, and Kivy
  canvas consumes `child.pos/size` without mutating either.
  A post-commit paint refresh is necessary because native widgets
  may be positioned after their parent. Removing the child restores
  the full separator line in all three adapters. The certified
  child policy is exactly one native Text; arbitrary Divider children
  remain deliberately unsupported.
- **No double layout:** The Qt transaction still rejects competing
  QLayouts on structural PSX descendants; G2's special internal
  SpinBox chrome remains the only established exception. Tk and Kivy
  retain SFLE border-box/native readback and generation checks.
- **Evidence:** [source `b02e8b5`](https://github.com/Neuri-AI/PSX/commit/b02e8b525a33b96d0ef99c651c53b960592d2666).
  [F3 selective #38215003694](https://github.com/Neuri-AI/PSX/actions/runs/38215003694);
  [G1 #38215003715](https://github.com/Neuri-AI/PSX/actions/runs/38215003715).
  Real-toolkit tests verify nested native ancestry, lack of competing
  Qt layout/Tk pack, Kivy size_hint disabling, RadioGroup controlled
  selection and on_change, and native geometry ≤1px. Qt: **216
  passed** across 4 bindings and 2 DPI scales; Tk: **34**; SDL2
  Kivy: **11**.
- **Remaining:** complete component/backend/operation matrices and
  lifecycle/rollback/borrowed ownership coverage, targeted dynamic
  structural re-ordering and removals, font/theme/source/DPI
  invalidations and Scroll native viewport binding. Advanced CSS
  replaced-element sizing remains outside F3.

## F3-G2 increment — basic native Scroll viewport/content binding (2026-10-12)

**Increment: initial viewport geometry implemented and native-tested.
G2 remains OPEN; F3 stays at 1/5 closed gates (20%).**

- **Source contract:** Added `psx/sfle/f3_scroll_viewport.py` with
  backend-neutral `ScrollViewportBinding`, explicit Scroll -> one Flex
  root validation, immutable viewport/content rectangles, overflow extents
  and allowed scroll axes. The snapshot maps Scroll to an SFLE Flex layout
  participant with its source VNode identity unchanged; width/height props
  only seed dimensions when no conflicting `layout_width/layout_height`
  was supplied. No native CSS sizing fallback.
- **Native viewport ownership:**
  - Qt: `QScrollArea` retains its clipped viewport, but its inner content
    `QWidget` no longer owns a competing QBoxLayout. The mounted Flex
    is parented to the content QWidget and SFLE alone projects its rect.
    Scroll's internal Qt viewport/chrome layout is not a PSX layout.
  - Tkinter: `Canvas` and `create_window` retain native clipping; the
    explicit Flex is constructed with the native inner content `ttk.Frame`
    as its immutable master and uses SFLE `place()`, never `pack()`.
    Content canvas window extent follows committed SFLE content bounds.
  - Kivy: `ScrollView` retains its viewport, using a plain `Widget`
    content host rather than an owning BoxLayout. SFLE projects the
    explicit content Flex while `size_hint/pos_hint` are disabled.
    G2 prevents content-overflow geometry on Kivy until G3 can translate
    offsets correctly; this is a deliberate capability diagnostic,
    not a false assertion of complete scroll support.
- **Parent adapter bridge:** F3 Qt/Tk/Kivy commit recognizes exactly the
  known `Scroll._psx_content` intermediate native viewport owner during
  ancestry validation; all other mismatched parents remain rejected.
  Native geometry readback and rollback still follow F2.
- **Coverage and regressions:** Existing explicit Flex-only Scroll
  normalization is retained. Pure source tests verify root policy,
  immutable widths/heights, direction, enabled and overflow. Real native
  Qt/Tk/Kivy tests verify viewport geometry, explicit content widget,
  native ancestry, no competing sibling layout and children positioned by
  SFLE. The source commit `8e7e9e1` includes CI corrections for
  duplicate width declarations and the serialized SFLE `component` field.
- **Evidence:** [source `8e7e9e1`](https://github.com/Neuri-AI/PSX/commit/8e7e9e185026454305ed3737e1b9d57993362dbc).
  [F3 selective #38217152181](https://github.com/Neuri-AI/PSX/actions/runs/38217152181),
  [G1 contract #38217152170](https://github.com/Neuri-AI/PSX/actions/runs/38217152170).
  Qt family **28 × 4 × 2 = 224 parity executions**, real Tk **35**
  and real Kivy SDL2 **12**. See linked Actions for the exact per-job
  conclusion and platform wheel certificate.
- **Explicitly NOT implemented in this G2 increment:** complete G3
  offset-aware overflowing content projection on Kivy, nested wheel
  chaining/physics and scroll positions across dynamic changes. Qt and
  Tk still use existing native scrolling mechanisms, but these are not
  a cross-platform 1:1 scroll equivalence certification. G2 remains open
  for full component/backend/operation and lifecycle matrix.

## F3-G2 increment — registered component × backend × operation audit (2026-10-12)

**Increment: census and fail-closed CI evidence indexing implemented. Not a G2 closure.**

- New `psx/sfle/f3_g2_matrix.py` obtains the *live*
  `builtin_component_registry()` snapshot rather than copying a
  misleading manually maintained list of names.
- Enumerates every builtin across `qt`, `tk`, `kivy`, and `headless`,
  with statuses `native`, `unported`, `transparent`,
  `external_port_required` and `legacy_deferred`. Strict reviewed
  `UNPORTED_BY_BACKEND` sets mean any added/removed registry builtin
  or undeclared backend cell **fails** the test rather than silently
  becoming certified.
- The eight audit operation dimensions are create, update, reorder,
  unmount, event rebind, borrowed ownership, rollback and invalidation.
  `EVIDENCE` references actual executable test methods and CI verifies
  they still exist. **Existing backend-level tests are not considered
  proof of every operation on every individual component**: pending
  operations remain explicit for every native cell, with borrowed
  ownership deliberately unclaimed.
- Added `tests/test_f3_g2_matrix.py` and required its execution in
  the F3 core/registry CI job. The tests assert inventory exactness,
  backend coverage consistency, live evidence references and that
  G2 may not be marked complete from this aggregate evidence.
- **Remaining G2 gate blockers:** per-component operation matrix with
  actual create/update/move/remove/rebind probes on all applicable
  GUI backends; borrowed/native/custom ownership and destruction;
  theme/font/DPI/image source invalidation; complete regression
  and platform certification. G3 continues to own overflowing
  Scroll offset/chaining; G4 owns removal of Row/Column.

## F3-G2-C1 — native component SFLE geometry coverage signoff (2026-10-12)

**C1: CLOSED, native GUI geometry scope only. G2 overall IN PROGRESS.**

- The registry-derived G2 audit now has **no unported built-in GUI geometry
  cells** for Qt (PySide6, PySide2, PyQt5, PyQt6), Tkinter and Kivy.
  `tests/test_f3_g2_matrix.py` enforces this invariant so a newly
  registered GUI component cannot silently lack a declared geometry port.
- The missing Tk native geometry cells `Input` and `ProgressBar` were
  admitted; real Tk `ttk.Entry`/`ttk.Progressbar` tests verify
  `place()`, parent ownership, SFLE rectangles, identity and controlled
  updates. Tk Input's previous helper passed a nonexistent `placeholder`
  option to ttk.Entry and required an extraneous positional argument.
  The corrected adapter applies legal Tcl options and records the hint
  declaration; **Tk placeholder visual rendering is still an explicit
  portable UX gap**, not part of the C1 geometry signoff.
- Kivy `Input`, `Checkbox`, and `ProgressBar` now participate
  with real TextInput/CheckBox/ProgressBar native widgets. Because these
  controls currently lack a certified intrinsic host measurement,
  `layout_width` and `layout_height` **must both be definite px**.
  The preflight rejects CSS `auto`, percentage and missing bounds,
  rather than trusting an arbitrary Kivy `Widget.size` allocation.
  Real SDL2 tests certify native rectangles, parent-relative inverted Y,
  value/state reconciliation and precise commit/readback.
- Qt GUI cells were already covered by native Qt-family parity, text
  remeasurement and pixel scale suites and remained GREEN throughout C1.
  `Native`/custom/borrowed widgets belong to C4 extensibility/lifecycle,
  and `Row`/`Column` removal is G4. Headless is explicitly limited
  to its implemented renderer capabilities; it does not fabricate Qt
  or Kivy widget measurements.
- Source verification: [`890ec54`](https://github.com/Neuri-AI/PSX/commit/890ec54bcf63851e19ca0cd578c2e9b1b918e3a3),
  [F3 #38221740315](https://github.com/Neuri-AI/PSX/actions/runs/38221740315)
  SUCCESS, [G1 #38221740302](https://github.com/Neuri-AI/PSX/actions/runs/38221740302)
  SUCCESS, including selected native Qt/Tk/Kivy and platform wheel
  jobs. Automated C1 acceptance: [`6b0dc78`](https://github.com/Neuri-AI/PSX/commit/6b0dc78936a9a02914b6f8fc3475981a06475c26),
  [F3 #38221934245](https://github.com/Neuri-AI/PSX/actions/runs/38221934245)
  SUCCESS, [G1 #38221934188](https://github.com/Neuri-AI/PSX/actions/runs/38221934188)
  SUCCESS.
- **Scope boundary:** C1 certifies available built-in geometry ownership,
  not C2's detailed operation inventory, C3 per-component life cycle,
  C4 borrowed/custom ownership, C5 font/theme/DPI/resource invalidation
  or C6 independent precision and CI signoff. G2 remains OPEN until
  all its criteria are satisfied; advanced Scroll offsets remain G3.

## Post-C1 pre-C2 fixes — Tk Input placeholder and Kivy intrinsic controls (2026-10-12)

**State: Implemented; does not begin C2 or close G2.**

- **Tk `Input` placeholder:** `ttk.Entry` lacks a native Tk 8.6
  placeholder option. Its portable `placeholder` prop now renders
  through a child `tk.Label` inside the real Entry, rather than inserting
  hint text into the `StringVar`. It hides when focused or whenever the
  actual value is nonempty, and reappears after the controlled value is
  cleared. It uses the configured native theme Entry field background,
  preserves password/readonly/value state and does not emit `on_change`
  merely because the hint changes. The overlay is **not** a competing SFLE
  layout participant; the `ttk.Entry` outer box remains SFLE-owned.
- **Kivy `Input`:** UI-thread measurement uses isolated native CoreLabel
  glyph texture sizes, current text/hint, native TextInput font and padding;
  it never reads the committed widget width as a natural measurement.
  An automatic single-line `height` participates in the post-flex width
  measurement callback pipeline, with value changes remeasured on commit.
- **Kivy `Checkbox`:** native theme check artwork sizes are probed when
  available. Its fallback 32dp tap-target minimum is explicit design
  policy, independent of the previous `Widget.size`, not a fabricated
  measurement. `ProgressBar`, which has no content intrinsic-size API in
  Kivy, declares portable 120dp × 20dp preferred minima. Both controls
  support CSS auto/percentage sizing through SFLE and DPI-scaled design
  preferences, rather than requiring hard-coded pixel bounds.
  Kivy `Slider` still fails closed when either pixel dimension is
  unspecified, because its intrinsic sizing has not been separately ported.
- **Width-aware correctness:** Kivy Input, Checkbox and ProgressBar now
  participate in the post-flex height measurement callback registry,
  preventing the engine's `UNSUPPORTED_MEASUREMENT` error on `auto`
  heights. No private Kivy BoxLayout gets authority over host geometry.
- **Regression tests:** real Tk event-loop tests exercise hint/value/update
  visibility and retained native widget identity. Real Kivy SDL2 tests
  exercise auto-sized Input/Checkbox/ProgressBar, changed input text width,
  controlled values and native SFLE readback. The explicit-bounds Slider
  failure remains tested; original geometry tests remain intact.
- **Evidence:** [source `483cb6c`](https://github.com/Neuri-AI/PSX/commit/483cb6c951183587e4260a855d06acd41974077c);
  [F3 selective #38224056162](https://github.com/Neuri-AI/PSX/actions/runs/38224056162),
  [G1 contract #38224055984](https://github.com/Neuri-AI/PSX/actions/runs/38224055984).
  Acceptance is the linked workflow's completed SUCCESS status. This
  note does not extend C1's original signature into an untested claim
  of full C3 component lifecycle or C5 theme re-invalidation.

## F3-G2-C2 — complete registry, backend and operation evidence certification (2026-10-12)

**C2: CLOSED; G2 remains OPEN; F3 1/5 officially closed gates (20%).**

- **Reviewed registry coverage:** `psx/sfle/f3_g2_matrix.py`
  enumerates the live `builtin_component_registry()` for each of
  `qt`, `tk`, `kivy` and `headless`. Each name must match an
  expressly reviewed `native`, `unported`, `legacy_deferred`,
  `transparent` or `external_port_required` classification. New or
  removed names without a classification update fail CI; no automatic
  implicit "supported" status is allowed.
- **Operation evidence must be per component:** Added the immutable
  `psx/sfle/f3_g2_evidence.py` source index, associating
  `(backend, component, operation)` with a **specific real test method**,
  rather than applying a general backend test to every built-in.
  The eight dimensions are `create`, `update`, `reorder`,
  `unmount`, `event_rebind`, `borrowed_ownership`, `rollback`
  and `invalidation`. Nontrivial lifecycle claims are still pending
  until C3–C6 provide their own per-control probes.
- **65 reviewed references** currently count as operation-specific
  source evidence, including 62 creation and 3 update tests.
  The former Headless Button "create" reference was removed when CI
  demonstrated its purported test exercised `Flex` nodes instead;
  its pending status is the correct outcome, **not a skipped test**.
  Structural, external, deprecated and unsupported cases are never
  counted as silently passing per-widget native operations.
- **Auditable outputs:** `g2_certification_matrix()` produces
  per-component records with `operations_with_evidence` and
  `pending_operations`. `g2_operation_coverage_summary()`
  provides evidenced/pending counts by backend and operation.
  `g2_matrix_summary()` reports backend capability classification.
- **Executable fail-closed validation:** `tests/test_f3_g2_matrix.py`
  checks exhaustive registry × backend entries and exact classifications;
  parses actual Python ASTs to verify cited test methods exist and contain
  a component reference; checks manifest operation names and ensures
  evidenced and pending sets partition all eight dimensions.
  The existing F3 core CI job always executes these tests.
- **Certificate:** [`be7bec5`](https://github.com/Neuri-AI/PSX/commit/be7bec5c2da46cd53cde937ca1524ef4aab8a97a);
  [F3 selective #38225021690](https://github.com/Neuri-AI/PSX/actions/runs/38225021690)
  **COMPLETED SUCCESS**;
  [G1 certification #38225021774](https://github.com/Neuri-AI/PSX/actions/runs/38225021774)
  **COMPLETED SUCCESS**. Required selected native/platform jobs ran as
  classified by the workflow and all applicable jobs passed.
- **Next: C3** must turn pending per-control creation, reconciliation,
  keyed reorder, event rebind, unmount and rollback into direct native
  lifecycle evidence. C4 owns custom/borrowed/native resources; C5 owns
  font/theme/DPI/resource invalidation; C6 independently audits geometry
  tolerances and full green CI. C2 closure makes **no** claim of C3–C6
  closure or G2 final certification.

## F3-G2-C2 hardening — executable operation certification contracts (2026-10-12)

**C2: CLOSED following second-stage hardening. C3 begins in the next increment.**

The original C2 matrix verified that an existing test *mentioned* a component.
That was insufficient to prove runtime execution or the actual operation.
The strengthened contract now has all five acceptance properties:

1. **Exhaustive component registration:** Every builtin in
   `builtin_component_registry()` is classified explicitly for Qt, Tkinter,
   Kivy and Headless. Unknown, stale or unreviewed cells fail CI.
2. **Explicit applicability:** `psx/sfle/f3_g2_contracts.py` emits one
   contract for **every component × backend × operation** (eight defined
   operations), with `required` or justified `not_applicable`.
   Operation ownership is routed to C3 (lifecycle/rollback), C4
   (external/borrowed ownership) or C5 (invalidation). Builtin-owned
   controls cannot silently claim borrowed Native behavior. Exclusions
   never count as successes.
3. **Executable behavioral mechanisms:** `psx/sfle/f3_g2_oracles.py`
   contains real positive/negative assertions for create, update,
   reorder, unmount, event rebind, borrowed ownership, rollback and
   invalidation. Every required operation points to its oracle.
   Existing component-specific pytest tests are linked as references;
   operations without native-driver coverage carry the explicit
   `oracle_pending_driver` mechanism, not false PASS status.
   C3/C4/C5 will capture real native before/after observations and
   invoke these reusable oracles.
4. **Actual execution receipts:** `psx/sfle/f3_g2_receipts.py` reads
   pytest JUnit XML and marks a referenced test `executed_pass` **only
   when every parametrized case was executed and passed**. Missing,
   failed, errored or skipped references fail certification; merely
   mentioning a component in a test source is not runtime proof.
   `pending` and `not_applicable` remain distinct in JSON results.
5. **Fail-closed CI:** `tests/test_f3_g2_contracts.py` verifies exact
   cardinality, unique component-backend-operation identities,
   justified exclusions, oracle availability and synthetic
   positive/negative oracle behavior. It also verifies failed,
   skipped and missing pytest receipts are rejected. The core job
   runs these checks; native Headless/Qt/Tk/Kivy jobs run the receipt
   verifier against real pytest output and publish JSON reports as
   GitHub Actions artifacts, including separate **Qt DPI=1 and DPI=1.5**
   reports. Source [`9e071a1`](https://github.com/Neuri-AI/PSX/commit/9e071a1722841fdaf737360c291b17811a38fc6e):
   [F3 selective #38227744199](https://github.com/Neuri-AI/PSX/actions/runs/38227744199)
   **SUCCESS**;
   [G1 #38227744082](https://github.com/Neuri-AI/PSX/actions/runs/38227744082)
   **SUCCESS**.

**Interpretation:** C2 certifies the registry, applicability policy, test
mechanisms, runtime provenance and CI guardrails. It does **not** claim all
component-specific operations passed: these are explicitly pending real
native lifecycle drivers in C3, external-widget semantics in C4 and
resource/font/theme/DPI invalidation drivers in C5. The C3 iteration must
begin directly with those pending operations rather than redesigning C2.
G2 remains OPEN; no scope from G3/G4/G5 is silently absorbed.


## F3-G2 built-in lifecycle certification — C3 CLOSED (2026-10-12)

**Status:** C3 CLOSED. This closure does **not** certify C4 external/custom/borrowed ownership, C5 invalidation, C6 final precision/CI, or full G2.

- **Implementation certificate SHA:** [`8f35bb8`](https://github.com/Neuri-AI/PSX/commit/8f35bb88f90880ea51059a0b4d7896811c27ade0).
- **Full selective workflow:** [F3 selective #38236676505](https://github.com/Neuri-AI/PSX/actions/runs/38236676505) — **COMPLETED SUCCESS** on that exact code SHA.
- **Scope:** Every `native` cell in the registered built-in inventory for Qt, Tkinter, Kivy and Headless. Tests dynamically assert that the native factory set matches the registered adapter allowlist; newly admitted hosts cannot silently inherit evidence.
- **Operations:** Create (actual mounting), update (same native handle and changed geometry/props), keyed reorder (same identity and new placement), unmount (native disposal/detachment), event rebinding (same live slot, replacement handler, no stale callback after teardown) for controls defining events, and rollback (injected invalid callback rejected before native mutation, preserving geometry and widget state). Eventless hosts receive a justified `not_applicable`, not a fabricated PASS. Rejection before mutation is the certified rollback case; compensating recovery from partially applied native mutations remains an independent risk, not implied by this evidence.
- **Behavioral drivers:** `test_registered_builtin_lifecycle_keeps_real_native_identity` and `test_all_callback_controls_keep_one_live_slot_after_reconciliation` for Qt/Tkinter, `test_all_ported_builtin_lifecycles_keep_native_widget_handles` and `test_all_callback_controls_rebind_without_native_remount` for Kivy/SDL2, and `test_all_supported_headless_components_reconcile_without_remount` for Headless.
- **Execution evidence:** Every component × operation reference is resolved by `f3_g2_receipts.py` against successful executed JUnit cases for the corresponding backend. Qt is certified separately on PySide6, PyQt6, PyQt5 and PySide2 and at DPR scaling test conditions; Tk and Kivy use real native widgets, not mocked geometry.
- **Mandatory guardrail:** `test_all_required_builtin_lifecycle_operations_have_component_drivers` fails the required core job if a required create/update/reorder/unmount/event_rebind/rollback operation is left at `oracle_pending_driver`, including for a newly registered native host.

**Transfer to C4:** native/custom/borrowed widget ports, ownership, reparenting, and resource semantics remain separately unproven. C5 remains responsible for runtime invalidation and remeasurement; C6 remains responsible for final cross-platform precision and complete G2 closure. The C3 status never converts these other operations to PASS.


## F3-G2-C4 — external/native ownership and resource certification CLOSED (2026-10-12)

Developer-facing explanation and examples: [Native widget ownership and borrowing](../guides/native-widget-ownership.md).


**C4: CLOSED; C5 and C6 remain OPEN.** C4 certifies the documented
admissible `Native` and custom adapter ownership contracts, not every
unbounded third-party toolkit widget or an unsupported capability.

- **Source SHA:** [`9df902d`](https://github.com/Neuri-AI/PSX/commit/9df902dad699d4572ba871ee4882b3219bab1194).
- **Required full selective CI:** [F3 #38240211598](https://github.com/Neuri-AI/PSX/actions/runs/38240211598)
  **COMPLETED SUCCESS** at that exact code SHA. C4 tests executed in real
  Qt (PySide6, PyQt6, PyQt5 and PySide2), Tk (Xvfb), and Kivy (SDL2) jobs.
  Headless has no native-object ownership API; it is not reported as a
  successful borrowed-native backend.
- **Native owned:** factories allocate an instance managed by PSX; teardown
  deletes Qt widgets, destroys Tk widgets, or detaches Kivy widgets. The
  tests inspect the actual native instance, not just a recorded API call.
- **Native borrowed:** Qt preserves the instance and restores its caller
  parent without deleting it. Kivy transfers the caller-owned instance
  safely into the SFLE Flex container, restores the original parent, and
  restores original size/position hints after release. Tkinter cannot
  safely reparent a caller widget or guarantee its survival if its fixed
  native master is destroyed; borrowed Tk is **explicitly unsupported**,
  fails before mutation, and preserves the caller's instance.
- **Custom registered hosts:** custom Qt/Tk/Kivy adapters supply explicit
  SFLE measure/apply/read ports; adapters own their own resource cleanup.
  Tests assert a native widget is created and the registered destroy hook
  executes exactly once. An adapter without a usable geometry port is
  rejected before resource creation.
- **Events:** Qt and Kivy borrowed `Native` signal subscriptions are
  replaced on reconciliation and disconnected on teardown; subsequent
  native events cannot invoke disposed PSX callbacks. Tk's borrowed
  signal case is N/A because the borrowed host itself is unsupported.
- **Behavioral guardrail:** `psx/sfle/f3_g2_c4.py` enumerates ownership,
  custom adapter and signal-subscription scenarios. The independent
  `f3_g2_c4_receipts.py` validates executed JUnit cases, rejecting
  absent, failed, errored and skipped tests. Its JSON artifacts are
  published by the same mandatory Qt/Tk/Kivy workflows, including Qt
  scaling runs. `tests/test_f3_g2_c4_contracts.py` validates the census
  and negative receipt behavior in required core CI.
- **Safety:** invalid ownership declarations, mismatched backends,
  missing SFLE geometry ports and borrowed Tk are explicit errors rather
  than silent fallback. The resource contract does not authorize
  borrowing arbitrary incompatible host widgets.

**Out of scope:** C5 owns live font/theme/DPI/resource invalidation and
remesurement; C6 owns full numerical/native readback certification, and
G3 owns Scroll interaction. C4 passing does not imply those gates are
closed, or that G5's per-property/method/event functional audit passed.

**Next block: F3-G2-C5.**


## F3-G2-C5 — semantic invalidation and remeasurement (IN PROGRESS, 2026-10-12)

**Status: OPEN.** The first C5 increment establishes an explicit,
backend-portable invalidation coordinator, not full native automatic
invalidation coverage. G2 remains open and C6 must not begin under the
assumption that C5 is complete.

**Implemented:** `MeasurementInvalidations` tracks six reasons
(`content`, `font`, `theme`, `resource`, `dpi`, `viewport`),
pending coalesced reasons, epochs and a teardown lifetime fence. All
four renderers expose `request_sfle_invalidation(reason)` and schedule
one UI-thread re-commit of the existing mounted instance, without
re-running the reconciler or remounting its widgets. The normal SFLE
transaction validates generation and native geometry before applying.
Manual successful commits acknowledge pending invalidations to avoid
duplicate queued work. A queued task is canceled by root teardown.
Qt's mounted root observes native `FontChange`, `PaletteChange`,
`StyleChange`, `ScreenChangeInternal` and
`DevicePixelRatioChange` where the binding exposes those event
types. Tk listens for the native `<<ThemeChanged>>` virtual event
on its mounted root. Prior native viewport resize and TextArea
hooks continue to run. A transactional intrinsic cache in Headless
now reuses unchanged per-handle measurements on normal commits and
remeasures invalidated inputs; native toolkit dependency pruning
still remains open.

**New regression drivers:** the semantic invalidation/epoch unit suite,
parameterized Headless measured content and teardown tests, Qt-family
native style/font event tests, and native Tk/Kivy identity-preserving
explicit re-commit tests. The synthetic Headless measurement driver
proves measurement callbacks are re-executed; fixed CSS widths are
intentionally unchanged even when intrinsic width changes.

**Still mandatory before C5 CLOSED:**

1. Real native resource and image-source updates **without** a PSX prop
   change, on all backends that support live resources; accurate fallback
   for resource failures.
2. Live font/theme/screen migration/DPR changes with automatic source
   observers where available (or explicit, documented host notifications
   where the backend cannot observe them), plus child-level changes.
3. A dependency-aware measurement cache/dirty-subtree plan which
   remeasures **only invalidated nodes and their layout dependents**,
   with before/after counters proving unrelated widgets are not
   remeasured or repositioned; mere coalescing does not prove this.
4. Multi-trigger race, generation/teardown, failure-and-retry, off-thread
   scheduling, native readback and device-space assertions.
5. Component × backend × applicable invalidation operation evidence
   and executed JUnit receipts, enforced by CI with zero required C5
   gaps. A generic test reference may not certify untested components.

The implementation **must not be labeled C5 CLOSED** until each item
is supported by specific executed evidence on an immutable CI SHA.

### C5 execution checkpoint — 2026-10-12

**Verified code revision:** [`487b724`](https://github.com/Neuri-AI/PSX/commit/487b72444067e7a7626d0b6189725f699faf6010), [required F3 selective workflow #38249572032 — SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38249572032).

- **Native measurement selection:** `f3_native_cache.py` uses stable native widget identities plus declarative props, viewport constraints and measured width. Qt/Tk/Kivy bridge transactions preserve unchanged intrinsic results; a failed geometry commit never publishes partially updated cache entries. Specific native-loop assertions and the independent width-cache suite verify the behavior.
- **External resource changes:** `f3_resource_watch.py` detects local file timestamp/size revisions, including deletion and recreation, without a VNode prop update; the Qt/Tk/Kivy owners poll/reload in the GUI thread, with safe lifetime fencing and last resource error tracking. Kivy also listens for texture replacement. Remote URLs, virtual resources and non-file resources require explicit host invalidation; the watcher deliberately does not pretend to monitor them.
- **Platform events:** native Qt root and child font/palette/style/screen events, Tk theme event, and Kivy intrinsic texture and host notifications can trigger a coalesced layout transaction. Explicit `request_sfle_invalidation` is still the portable interface for changes not observable by a renderer.
- **Per-component evidence:** every registered native component has an explicit `invalidation` contract and a component-iterating native-driver JUnit reference. The required core contract test rejects any missing coverage, and the existing backend receipt verification rejects failed/skipped/missing cases.

**Outstanding for an unconditional C5 closure:** the contract must still demonstrate targeted **geometry application** (not merely selective intrinsic *measurement*) for unaffected subtrees, automatic coverage for other resource families where public contracts promise it, and explicit failure/retry and multitrigger races across all applicable backends. The CI success above does not independently prove these untested claims. C5 remains OPEN until they have native executed receipts.


### C5 selective native geometry application increment — 2026-10-12

The existing native intrinsic cache only avoids redundant **measurements**.
`NativeGeometryCommitter(skip_unchanged=True)` now also suppresses
redundant geometry **writes**, independently for each actual native leaf
in Qt, Tkinter and Kivy. It compares the next SFLE parent-relative
projection with the actual native geometry (or external port readback)
before writing. Root geometry remains backend-owned. Updated rectangles
still apply normally, and the bridges continue verifying post-commit
native readback under existing CSS-to-device-pixel tolerances.

The required core regression
`tests/test_f3_g2_c5_geometry_writes.py` verifies each toolkit backend
applies an initial rectangle, makes **zero** additional position/size
writes for an identical subsequent result, and does apply a changed
rectangle. For external Tk widgets the first placement is deliberately
not inspected through a port that requires existing `place_info()`;
this fixes initial-mount safety without silently skipping its placement.

Code source revision: [`d5ae5d8`](https://github.com/Neuri-AI/PSX/commit/d5ae5d81eaefbcd3516fb609875f3e7da4e364a5).
[Required selective CI run #38250924680](https://github.com/Neuri-AI/PSX/actions/runs/38250924680).

**Boundary:** This verifies selective native geometry writes and changed
readback, **not** a claim that the entire SFLE mathematical layout tree is
incrementally recomputed. Dynamic paint/texture updates can still occur
with an unchanged rectangle, as they should. C5 final signoff requires
all remaining owner-thread race/resource/DPI scenarios to be certified.
