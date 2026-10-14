Warning: truncated output (original token count: 44049)
Total output lines: 2274

# SFLE F3 — native integration, complete component coverage and exit criteria

> **CURRENT STATUS (2026-10-13): F3-G1/G2/G3/G4 CLOSED; F3-G5 OPEN. F3 official gates: 4/5 CLOSED (80%).** Historical progress statements below are dated snapshots, not the current gate state.
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

**Status: CLOSED (2026-10-14, owner-authorized).** The owner accepted the
successful Windows/macOS/Linux local certification matrix for Python 3.10–3.13
as G5's final signoff. Documented PySide2 platform/version exclusions remain
accepted. The executable public-behavior census stays in the repository as a
development coverage tool; incomplete rows do not reopen this closed gate
unless the project owner explicitly schedules further F3 work.

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

**Status: accepted for F3 closure by owner authorization (2026-10-14).**
This specification remains the desired continuing coverage model, not a
reopening of G2-C3 or of the owner-closed G5 gate.
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
- **Tests:** `tests/test_flex_layout_contract.py` now covers Markup/builder equivalence, nested Flex, preserved boundaries, reorder identity, unresolved components, Scroll roots, nested Scroll and duplicate-key errors. [GREEN CI #38153141925](https://github.com/Neuri-AI/PSX/actions/runs/38153141925) certified SHA `3ac035b` (70 Core tests, all selected CI jobs green; G4 legacy removal deliberately not selected).
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

- **Canonical SFLE snapshot mapper:** [`aa245fe`](https://github.com/Neuri-AI/PSX/commit/aa245fe63677e22fb9943e8d34582ffea82a7d7a) introduced `psx/sfle/native_layout_snapshot.py`; it converts G1 normalized Flex participants into immutable `LayoutInput` styles and stable keyed IDs. Gap shorthand, padding longhands, flex item properties, native width separation, fragment/component transparency and unsupported Scroll are explicit. No second Flexbox algorithm.
- **Mounted Headless geometry:** `psx/sfle/headless_layout_bridge.py` and `HeadlessRenderer` now have an **explicit opt-in viewport**. The reconciler's existing mounted/hook/key tree supplies source identities and real handle bindings; `load_layout_engine()` uses Rust primary and Python fallback at load time. Successful commits apply only SFLE border rectangles, after snapshot/generation/liveness/grid checks, with readback and rollback on commit failure. Host-provided intrinsic measurements are required where needed; the bridge never invents text/widget size.
- **No misleading automatic fallback:** Unconfigured `HeadlessRenderer()` still rejects mounting `Flex`, and legacy `Row`/`Column` cannot act as competing layout authorities within an opted-in SFLE tree. Qt, Kivy and Tkinter Flex mounting remain intentionally fail-closed until their real G2 ports are wired.
- **Tests and single-SHA CI:** [`a03f300`](https://github.com/Neuri-AI/PSX/commit/a03f30056ceadc9372049b84d8133ec5ec3ba9a3) passed [F3 selective #38158347861](https://github.com/Neuri-AI/PSX/actions/runs/38158347861), including **151 Core tests and 19 Headless tests**, plus impacted SFLE, Rust/Python, Chromium, Qt/Kivy/Tk regressions and platform wheels. [G1 regression matrix](https://github.com/Neuri-AI/PSX/actions/runs/38158347847) was scheduled on the same SHA; G1 continues closed.
- **G2 remaining:** wire actual Qt/Kivy/Tkinter native measuring and rectangle commits (Kivy parent-relative Y inversion from existing `NativeGeometryCommitter`); cover all registered supported widgets plus `Native`/custom adapters and negative capability cells; width-dependent remeasurement, viewport/resize invalidation and strict native commit/readback/error separation. G3 still owns scrolling events/offset lifecycle. **Neither live Qt/Kivy/Tk Flex rendering nor full G2 certification is claimed by Headless-only evidence.**


## F3-G2 iteration — actual Qt native geometry (2026-10-11)

**Formal state remains G2 IN PROGRESS, not CLOSED. F3 remains 1/5 gates CLOSED (20%).**

- **Explicit SFLE-enabled Qt host:** `psx/renderers/qt/flex.py` implements a native `QWidget` Flex host with **no QBoxLayout** or native sibling distribution. `QtRenderer` and Qt facades accept opt-in `sfle_constraints` and an optional injected engine. Without opt-in, G1's fail-closed error remains. Unported widget/backend combinations fail with an explicit F3-G2 capability diagnostic; **only Flex, Text and Button are admitted into this incremental SFLE-Qt path**.
- **Real coordinate projection and native intrinsic measurement:** `psx/sfle/qt_layout_bridge.py` uses mounted reconciler identities and normalized markup/builder VNodes to form one SFLE `LayoutInput`, measures native `QWidget.sizeHint()/minimumSizeHint()` through the pre-existing `QtMeasurementSource`, computes using the renderer's chosen SFLE engine, and calls the F2 `NativeGeometryCommitter(GeometryBackend.QT)` to set Qt child geometries in parent-relative top-left coordinates. It does not install a competing Qt layout.
- **Commit guards:** UI-thread authority, duplicate/stale/disposed identities, no native `QLayout`, actual parent-graph validation, SFLE generation/rectangle shape and fixed-point preflight, ≤1 px Qt readback budget and rollback of native child geometry if application/readback fails. Root/window size remains host-owned; viewport constraints can be updated without remounting.
- **Real native test evidence:** [commit `8e4d3b5`](https://github.com/Neuri-AI/PSX/commit/8e4d3b5919a7855ae73108393d8054a69bf6dc1b) passed [F3 selective CI #38159181324](https://github.com/Neuri-AI/PSX/actions/runs/38159181324) with successful aggregate, including **28 PySide6 Qt native tests** (the new `tests/test_pyside6_native_layout.py` covers live `QWidget.geometry()`, nested parent-relative coordinates, PSX Markup, keyed reorder, hook-triggered reflow, button callbacks, viewport updates, explicit unsupported widgets and stale engine results). The [G1 3.10–3.13 regression #38159181381](https://github.com/Neuri-AI/PSX/actions/runs/38159181381) also passed on **the same code SHA**.
- **Still required for G2 closure:** Kivy bottom-left projection in its production renderer, Tkinter geometry application, other built-in Qt controls and complete Qt family matrix, `Native`/custom adapter ports, width-driven real text remeasure, font/DPI/resize lifecycle, fragment/Box ownership and fully instrumented per-backend and per-component matrix. Existing SFLE math and its precision thresholds remain unchanged. G3's Scroll events/offset integration is not considered complete.


## F3-G2 iteration — native Kivy geometry and inverted Y (2026-10-11)

**Formal state: G2 IN PROGRESS; F3 remains 1/5 officially closed (20%).**

- **Real Kivy production Flex host:** `psx/renderers/kivy/flex.py` implements an opt-in `Widget(size_hint=(None, None))` with **no BoxLayout**; reconciler insert/move/remove preserves declared identities. Direct children have `size_hint=(None, None)` and empty `pos_hint`, preventing Kivy sizing hints from overriding SFLE. Without `sfle_constraints`, G1's explicit fail-closed behavior remains unchanged.
- **F2-authoritative projection:** `psx/sfle/kivy_layout_bridge.py` resolves mounted/reconciled nodes to immutable SFLE `LayoutInput`, measures Kivy native label textures using `KivyMeasurementSource` on the owning thread, and invokes `NativeGeometryCommitter(GeometryBackend.KIVY)` with SFLE's untouched boxes. Kivy native child Y is computed by F2 as **parent border height − child top-relative Y − child height**, separately for each actual parent frame. Fixed-point preflight, root-border/host viewport consistency, generation/liveness, actual parent ownership, ≤1px readback and rollback are enforced.
- **CSS root content…24049 tokens truncated…ells. The original XML is archived alongside each
report. The aggregate required CI conclusion succeeded; the G4 legacy
Row/Column removal gate was correctly skipped because G4 is not C5.

**Scope exclusions and handoff:** External URL/virtual asset revisions
without a reliable toolkit event require host-supplied semantic invalidation.
No C5 result asserts full Rust/Python mathematical solver incrementality,
browser-owned rendering or rollback of external device side effects.
C6 still owns independent geometrical precision and final G2 acceptance.
The postponed incremental mathematical solver has its own roadmap item,
outside this C5 certificate.

**Formal disposition: F3-G2-C5 CLOSED.** C5 increments 1, 2 and 3 have
verified implementation, tests, documentation, JUnit evidence and completed
required GitHub Actions. **Next: F3-G2-C6**, without reopening C5 absent a
new regression or a changed contract.


## F3-G2-C6 — final numerical geometry and integration certification (IN PROGRESS)

### C6 iteration 1/4 — signed precision, physical projection and native coordinates (CLOSED, 2026-10-12)

**Certified code SHA:** [`cb69e2fadb9b28741a30256d1ddafcfed33ba80e`](https://github.com/Neuri-AI/PSX/commit/cb69e2fadb9b28741a30256d1ddafcfed33ba80e).
**Full required test matrix:** [F3 selective #38333768220 — completed SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38333768220).
The independent G1 contract, runtime package boundaries and commit-subject
workflows also completed SUCCESS at the same code SHA.

**Numerical audit:**

- `LayoutUnit` remains a **signed saturating 32-bit** fixed-point value
  at 1/64 logical CSS px; boundary raw values and signed overflow
  saturations were retested rather than changing the certified F2 math.
- Device-pixel projection snaps absolute edges, never independently rounds
  sibling widths; tests cover negative/fractional coordinates and DPR
  `1, 1.25, 1.5, 2, 2.5, 3`. Shared-edge continuity is exact after
  snapping, including signed negative LayoutUnits.
- Native parent-relative transforms are tested on a three-level tree,
  including a child to the *left* of its parent and the real Kivy
  bottom-left inversion. The native root/window rectangle must remain
  host-owned; this test exercises all three native commit algorithms
  independently of toolkit event loops.
- `Rect` rejects nonfinite `x/y/width/height` at construction
  (`ValueError`), **before** device projection. The initial C6 RED
  run showed a newly added test incorrectly expecting the downstream
  `SFLEError` instead. The corrected assertion was executed GREEN on
  the code SHA above; no production validation was weakened.
- Chromium logical-layout oracle and Rust/Python differential continue to
  run in the mandatory suite. The approved engine comparison limit
  remains **0.01 logical CSS px** on equivalent inputs. No new
  off-spec CSS feature or mathematical incremental solver is claimed.
- **Unit caveat:** Qt `QWidget.geometry` reports integer *device-independent
  Qt units*, which are not physical framebuffer pixels. The existing
  `DevicePixelSpace.allowed_physical_error = ceil(DPR)` is a translated
  tolerance for *one QWidget integer unit* and must **not** be described
  as a verified maximum of one *physical* pixel at DPR > 1.
  Kivy/Tk native geometry APIs use their respective window units and
  are not secondarily scaled. A true framebuffer-pixel acceptance
  contract would require framebuffer readback and belongs to the
  separate visual/OS certification scope; this increment certifies the
  published native geometry readback contract without fabricating it.

**Executed tests:** newly added
`tests/test_native_geometry_precision.py` exercises signed numeric boundaries,
fixed-point saturation, DPR edge seams, native parent graph transforms
and nonfinite preflight. The intelligent F3 workflow now includes it in
the required core job, alongside existing `test_native_pixel_scale`,
SFLE geometry contracts, Rust/Python differential and Chromium oracle.
The full required workflow covered Headless, native Qt bindings,
Tkinter, Kivy and Windows/macOS native wheels; its aggregate was SUCCESS.

**C6 handoff:** iteration 1/4 CLOSED. Iteration 2/4 remains responsible
for exhaustive supported/unsupported component/backend integration and
mixed/nested/native/custom ports. Iteration 3/4 must enforce a fail-closed
G2 precision/lifecycle evidence matrix with executed receipts. Iteration
4/4 consolidates G2 release documentation, removes conflicting historical
status summaries from the active header, and signs off the exact final
SHA. **C6 and G2 remain OPEN until all four iterations finish.**


### C6 iteration 2/4 — registry × native integration matrix (CLOSED, 2026-10-12)

**Certified implementation SHA:** [`c3bef12d6c5d2aa35337b2d049b73d865e5f979f`](https://github.com/Neuri-AI/PSX/commit/c3bef12d6c5d2aa35337b2d049b73d865e5f979f).
**Required code CI:** [F3 selective #38334904498 — completed SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38334904498), with independent G1 contracts, package boundaries and commit-subject workflows green at the same code SHA.

A new fail-closed integration census in
`tests/test_native_component_integration.py` enumerates the live
`builtin_component_registry().snapshot()` crossed with the four
backends. Every pair has a unique, reviewed status and native
classification must agree with the allowed ports; unported Headless
controls remain explicit, not silently upgraded to supported.
`Fragment` is transparent, `Native` requires an external geometry
port, legacy `Row/Column` remain G4-deferred, and Flex is structural.

Each registered native component is required to appear in a
backend-specific source-checked **real native geometry/lifecycle driver**
that asserts native rectangle/width and mounted handle identity.
The integration census tests that these drivers enumerate the full
native registry, actually invoke semantic invalidation and perform
geometry assertions. Backend execution (not source references alone)
is supplied by the corresponding native CI job:
Qt PySide6/PyQt6/PyQt5/PySide2, real Tk/Xvfb, Kivy/SDL2, and deterministic
Headless. The existing G2 per-component JUnit receipt pipeline remains
required in each native CI job. The checks also prevent a builtin
operation's certificate from silently conferring certification on a
`Native` or custom adapter.

External-ownership admission is verified against the independent C4
manifest, with explicit cases for `native_owned`, `native_borrowed`,
and `custom_adapter` on Qt, Tk and Kivy. Qt/Kivy borrowed ownership
must preserve and reparent the original widget; Tk borrowed ownership
is explicitly rejected without mutation because Tk cannot guarantee
that ownership transfer. The mandatory C4 actual-execution verifier
runs against native JUnit XML for every backend.

The required CI at the implementation SHA completed successfully with
Core, all native UI suites, Rust/Python differential, Chromium browser
oracle, multi-platform native wheel/fallback jobs and G1 regressions.
The G4 removal gate is deliberately excluded. The new census is an
**integration and evidence-completeness guard**, not yet a final C6
precision-per-operation receipt: the latter is owned by iteration 3.
A passing source/AST check alone is never called a native PASS.

**Status:** C6 iteration 2/4 CLOSED; iteration 3/4 must consolidate
executable component × backend × operation JUnit proofs and reject
missing/skipped/failed precision cases; iteration 4/4 owns final C6/G2
single-SHA closure and document reconciliation. C6/G2 remain OPEN.


### C6 iteration 3/4 — executed native operation matrix and future component families (CLOSED, 2026-10-12)

**Certified implementation SHA:** [`700f1b3af3334b99f39fcf30a053d2a65838fc17`](https://github.com/Neuri-AI/PSX/commit/700f1b3af3334b99f39fcf30a053d2a65838fc17).
**Required F3 CI:** [run #38335949031 — completed SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38335949031). Commit-subject, G1 contract and package-boundary workflows also completed SUCCESS on this same code SHA.

**Mandatory component × backend × operation certification:** The new
`tests/certification/native_acceptance_receipts.py` runs inside each required native
backend job against its **executed JUnit XML**, requiring every operation
with `applicability=required` in the code-derived `g2_operation_contracts()`
to reference a test that actually ran and passed. Missing, skipped, failed or
error receipts and unreferenced required operations **fail the job**. The
certificate contains the component, backend, operation, behavioral oracle,
original test reference, applicability and audited exclusion reason.
`tests/test_native_acceptance_receipts.py` executes negative tests to prevent
future weakening of these invariants.

| Backend | Executed required operation cells | Reviewed N/A cells | Pending |
| --- | ---: | ---: | ---: |
| Qt (each of 4 bindings, both standard and 1.5 DPR) | 130 | 62 | 0 |
| Tkinter | 130 | 62 | 0 |
| Kivy | 130 | 62 | 0 |
| Headless | 19 | 173 | 0 |
| **Distinct backend operation contracts** | **409** | **359** | **0** |

The Qt 130-cell matrix was verified independently on PySide6, PyQt6,
PyQt5 and PySide2 in both DPI configurations, without counting repeated
execution as distinct component contracts. Tk and Kivy execute actual
native host drivers; Headless uses deterministic real renderer handles.
The existing C4 external-port and C5 six-reason JUnit certificates remain
separate mandatory checks, so builtin lifecycle proofs cannot silently
certify borrowed `Native` ownership or resource-specific semantics.
All native JUnit XML and C6 JSON reports are archived by their respective
native GitHub Actions jobs.

**Future family policy:** `tests/certification/component_family_policy.py` has an
exact registry-derived census backed by **explicit reviewed family
classification** (`leaf`, `layout_container`,
`structural_container`, `native_viewport`, `transparent`,
`external_port`, `legacy`, and reserved `overlay_portal`).
Unknown/unclassified new registry names and stale classifications fail
automatically. The companion
`tests/test_component_family_policy.py` tests an example `Modal`:
an unregistered/unclassified Modal is rejected; declaring
`overlay_portal` requires a **dedicated overlay/portal driver**, explicit
child policy and portal lifecycle/ownership semantics, rather than
inheriting Button/Flex native-leaf evidence. This policy does **not**
implement Modal or declare future modal focus, stacking or keyboard
behavior as already certified. Those require a separately approved
component contract and behavior-specific tests (public API completeness
remains G5's separate gate).

**Scope and exit:** This C6 certificate proves all presently required
G2 lifecycle/invalidation operation rows have executed pass evidence,
**not** every possible UI prop/event or OS framebuffer pixel, nor G3
scroll interactions. The source-only manifest audit from iteration 2
remains corroborative, never counted as an executed native PASS. C6
iteration 3/4 is CLOSED. Iteration 4/4 must reconcile live header/roadmap
status, rerun the G2 aggregate and certify the final immutable SHA before
labeling **G2 CLOSED**.


### C6 iteration 4/4 — final G2 disposition and evidence reconciliation (CLOSED, 2026-10-12)

**Current G2 authority:** this section and the document's CURRENT STATUS
header supersede dated earlier notes that described C5, C6 or G2 as OPEN.
Do not rewrite past incremental audit checkpoints as if the older results
were known at that time.

**Final tested CODE SHA:** [`700f1b3af3334b99f39fcf30a053d2a65838fc17`](https://github.com/Neuri-AI/PSX/commit/700f1b3af3334b99f39fcf30a053d2a65838fc17).
**Full required product CI:** [F3 selective #38335949031 — COMPLETED SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38335949031).
All three companion workflows (`F3 G1 contract certification`,
`Runtime package boundaries`, `Commit subject clarity`) also finished
SUCCESS on **the same source SHA**. The required F3 selector executed
actual Qt binding parity at standard and 1.5 DPI, native Tkinter and Kivy,
Headless, Chromium and Rust/Python differential, plus supported Windows
and macOS native-wheel/fallback jobs. The unrelated G4 removal gate was
intentionally skipped: G4 is a separate future acceptance gate.

**Archived executed native evidence:** Seven checked workflow artifacts
from #38335949031: `g2-qt-receipts-pyside6`,
`g2-qt-receipts-pyqt6`, `g2-qt-receipts-pyqt5`,
`g2-qt-receipts-pyside2`, `g2-tk-receipts`,
`g2-kivy-receipts`, `g2-headless-receipts`.
Each backend's C2/C3 and C6 validator uses actual JUnit XML; C4 custom
owned/borrowed geometry-port certificates and C5 six-reason invalidation
certificates are separately mandatory and preserved with the same artifacts.
The C6 operation verifier on the final tested code SHA emitted:
**Qt 130 required / 62 reviewed N/A; Tkinter 130 / 62;
Kivy 130 / 62; Headless 19 / 173**. Thus **409 distinct required
backend × component × operation cells executed PASS; 359 reviewed
not-applicable cells; ZERO missing/failed/skipped required cells**.
Qt's repeated 1×/1.5× DPI and four bindings are not double-counted
as distinct component contracts. Missing or newly added component
families and stale classifications are rejected by registry-exact CI.

**G2 geometry authority:** SFLE owns all supported Flex mathematics
with one signed, saturating 32-bit `LayoutUnit` per 1/64 logical px.
Approved logical precision against Chromium remains ≤0.01 logical CSS px
on equivalent intrinsic data; native geometry readback is bounded by
the approved coordinate-system tolerance. Qt's integer QWidget readback
tolerance is expressed in **device-independent** coordinates, not a
blanket claim of ≤1 framebuffer pixel at DPR > 1. Kivy bottom-left
projection, parent-relative positions, fractional device-pixel edges,
concurrency/readback rollback, automatic semantic invalidation and
selective native intrinsic remeasurement were exercised independently
in C5/C6. This certificate does not assert full incremental SFLE
mathematical solving, pixel-accurate raster screenshots, native
scrollbar/scroll-offset semantics or exhaustive per-prop/event
functional parity.

**Scope and exclusions:** G2 admits every implemented native
built-in/backend pair under its audited capability matrix, and
the explicit Headless unsupported pairs are not counted as passes.
`Native`/custom adapter owned/borrowed contracts use C4's separate
native tests. A future overlay/portal such as `Modal` requires a
new reviewed family classification, child policy and dedicated
component-specific native lifecycle/geometry evidence; this is
not a shipped `Modal` implementation. G3 still owns complete
Scroll behavior, G4 public Row/Column removal, and G5 end-to-end
public behavior and final F3 acceptance.

**Final certification policy:** Because documentation-only changes
must not rerun product tests, the immutable **code SHA** above carries
the full native/browser/Rust product certificate; a later
**documentation-only HEAD** carries its own selective workflow
success and is not falsely labeled as a new full product run.
Any change to executable code or tests after the certified SHA
invalidates this signoff and requires fresh mandatory product CI.

**Formal acceptance: F3-G2-C6 CLOSED (4/4 iterations); F3-G2 CLOSED.**
F3 now has **2 of 5 official gates CLOSED (40%)**. Next **F3-G3**.

## Mandatory source naming policy — semantic names, not planning milestones

**Normative for all new and refactored PSX code, tests, scripts, tooling and workflows.** Internal planning labels such as `F1`, `F2`, `F3`, `G1`, `G2`, `G3`, `C1`–`C6`, `D13` and their composites are **documentation and release-tracking identifiers only**. Do not use milestone codes to name Python files/packages, functions, classes, constants, test names, fixtures, standalone scripts, CI jobs/workflows or diagnostic identifiers. A developer must be able to infer behavior without decoding a roadmap.

- Use purpose-driven module paths such as `sfle/native_intrinsic_cache.py`, `sfle/native_component_capabilities.py` or `tests/test_native_geometry_precision.py`, not `f3_native_cache.py` or `test_f3_g2_c6_precision.py`.
- Use action/contract names such as `native_leaf_needs_measurement(...)`, `certify_native_operation_receipts(...)` and `test_native_resource_invalidation(...)`, never `g2_native_leaf_needs_measurement`, `f3_g2_c6_receipts`, etc.
- Write actionable backend errors (`Unsupported native geometry for Kivy Slider`) instead of roadmap-only codes (`F3-G2 Kivy ...`). Preserve documented machine-readable diagnostic enums and compatibility when required; move milestone labels to historical prose and test-report metadata.
- Semantic categories (`leaf`, `layout_container`, `overlay_portal`), stable public names, protocol names and backend identifiers are allowed; phase/gate names remain acceptable **only** in architecture/roadmap text, dated certification reports and migration notes (not current executable symbol names).
- Refactoring requires a repository-wide reference update: imports and exports, source files, test collection and markers, workflows, selectors, packaging and runtime-boundary checks, documentation links, dynamic imports and AST-based source checks. Eliminate stale parallel wrappers and temporary aliases after migrating all consumers; new milestone-prefixed names must fail an automated source naming-policy gate.
- Semantic refactoring is behavior-preserving: run all applicable native Qt bindings, Tkinter/Kivy/Headless, Rust/Python differential, Chromium and native-wheel workflows on a single code SHA. Documentation-only follow-up commits use selective CI without executing product tests.

The archived historical references to F3/G2/C6 in this implementation plan remain valid as **history**, not as permission to reintroduce those prefixes into executable identifiers.


## F3-G3 implementation tracking — native scrolling (2026-10-12)

G3 is subdivided for implementation tracking only; **the five official F3 gates are unchanged**. These milestone codes belong exclusively in documentation; executable source and tests use behavior-descriptive names.

| Increment | Scope | Status |
| --- | --- | --- |
| C1 | Neutral scroll offsets, clamping, residual deltas, viewport/content coordinate projection and immutable engine geometry | **CLOSED — code SHA `abdf9f1`, required CI SUCCESS** |
| C2 | Real native offset, clipping and axis integration in Qt, Tkinter, Kivy and Headless | **CLOSED — code SHA `8209f26`, required CI SUCCESS** |
| C3 | Keyboard/wheel/touch event handling, edge chaining, nested viewport separation | **CLOSED — code SHA `dda1499`, required CI SUCCESS** |
| C4 | Resize/content reflow, offset restoration, unmount/rollback and focus preservation | **CLOSED — code SHA `2bff382`, mandatory CI SUCCESS** |
| C5 | Per-backend, per-operation executed behavioral receipts | **CLOSED — code SHA `c58c9f5`, 19 executed Scroll operation receipts, CI SUCCESS** |
| C6 | Final cross-platform immutable-SHA signoff and G3 gate acceptance | **CLOSED — immutable source SHA `2621ebd`, executed adversarial CI** |

### F3-G3-C1 — backend-neutral scroll offset mathematics

**Implementation:** `psx/sfle/scroll_offsets.py`, independently of the native toolkit adapters. `ScrollOffset` is an immutable logical top-left offset in viewport/content coordinates, `ScrollConsumption` contains the next clamped offset and residual event deltas. `clamp_scroll_offset` respects allowed axes and current overflow; `consume_scroll_delta` reports unconsumed movement for future native parent chaining; `content_to_viewport` and `viewport_to_content` are inverse transformations for native viewport-parent coordinates. All current SFLE `Rect` instances remain unchanged. NaN/Infinity offsets, deltas, and requested coordinates fail closed.

**Execution:** `tests/test_scroll_offsets.py` covers both axes, disabled directions, extremes, positive/negative residuals, resize/shrink, nested independent frames, inverse projection and invalid numeric inputs. This test is included in the mandatory Core CI command. It does **not** claim toolkit scroll gesture support, Kivy overflow enablement, scrollbar parity or native nested event chaining. Those are owned by C2–C6.

**Certified implementation SHA:** [`abdf9f1caa53809e7b47b9cb469e7d514b5d7138`](https://github.com/Neuri-AI/PSX/commit/abdf9f1caa53809e7b47b9cb469e7d514b5d7138). [Required native layout CI #38345388117 — SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38345388117), including core, semantic source naming, Qt four bindings, Tkinter, Kivy, Headless, Chromium, Rust/Python differential and Windows/macOS wheel/fallback. The other three commit workflows also completed SUCCESS. **C1 CLOSED**; C2–C6 remain OPEN. Documentation-only revisions must not rerun product tests.

### F3-G3-C2 — native viewport offsets, clipping and axis application

**Implementation certified:** `psx/sfle/native_scroll_hosts.py` binds
the existing immutable SFLE content and viewport rectangles to
`QScrollArea`, Tk `Canvas`, Kivy `ScrollView`, and a deterministic
Headless projection. `qt_layout_bridge.py`,
`tkinter_layout_bridge.py` and `kivy_layout_bridge.py` apply the
offset/extent projection after native SFLE geometry commit. No parallel
Flex solver is involved. Kivy overflow is no longer rejected merely
because content exceeds the viewport; its top-left logical Y offset
is mapped into the bottom-left ScrollView fraction. The Kivy geometry
committer continues to support rootless widget maps.

**Executed native acceptance evidence:** `tests/test_native_scroll_hosts.py`
checks shared clamping, axes, disabled scroll and immutable boxes for
all four ports. The native toolkit suites execute `QScrollArea`
readback with overflow, offsets, scrollbar limits and viewport parent
clipping; Tk `Canvas` scrollregion, readback and viewport extent; and
Kivy `ScrollView` overflow extent, top-left-to-bottom-left offset
conversion and child geometry readback. Existing native SFLE commit
readback checks remain mandatory. Headless is deterministic and has
no actual clipping widget; it certifies the same logical projection.

**Immutable source certificate:** [`8209f26a440e6ae19bf3376c26fd1fbc969488b2`](https://github.com/Neuri-AI/PSX/commit/8209f26a440e6ae19bf3376c26fd1fbc969488b2).
[Native layout selective CI #38347298765](https://github.com/Neuri-AI/PSX/actions/runs/38347298765)
completed **SUCCESS**: 18 successful jobs, zero failures, with only the
future G4 Row/Column removal gate intentionally skipped. The other three
required workflows (commit subject, runtime package boundaries and
Flex contract certification) also completed **SUCCESS** on the same
code SHA. The run includes Qt bindings, Tkinter, Kivy, Headless,
browser oracle, Rust/Python differential and Windows/macOS native
wheel/fallback.

**Boundary:** C2 certifies viewport binding, offsets, axes, native clipping
hosts and scroll extent/readback. It does **not** claim wheel/key/touch
event-chain or nested dispatch certification (C3); reflow/unmount
transaction recovery (C4); complete per-operation behavioral receipt
matrix (C5); or final G3 cross-platform gate signoff (C6).
Documentation-only revisions retain this tested immutable source SHA
and must execute zero product tests.

**Formal acceptance: F3-G3-C2 CLOSED. Next: F3-G3-C3.**

### F3-G3-C3 — native scrolling input and independent nested viewports

**Implementation:** `psx/sfle/scroll_events.py` dispatches wheel or
keyboard-derived logical deltas in inner-to-outer order, returning only
residual movement on each axis. Qt `QScrollArea` handles wheel
and keyboard input, including Shift/wheel horizontal translation,
native boundary release and chained remaining motion through ancestor
scroll hosts. Qt's optional native `QScroller.TouchGesture` enables
kinetic touch input on bindings exposing it. Tk `Canvas` wheel limits
are derived from the SFLE content scrollregion rather than requested
widget size, with keyboard paging/arrows and nested remaining-delta
routing. Kivy `ScrollView` retains native touch gesture/kinetic
handling, forwards touch-pan travel beyond a viewport edge to
ancestors, and routes discrete native wheel events through the same
independent logical offset/remaining-travel semantics.
Headless certifies the deterministic event routing model.

**Executed coverage:** `tests/test_scroll_events.py` validates
inner-first dispatch, edge residuals, disabled axes, mixed X/Y parent
chains, keyboard mapping and invalid deltas. Actual Qt widget tests
exercise keyboard and nested `QWheelEvent` propagation; Tk widget
tests exercise keyboard, wheel, SFLE overflow and nested Canvas handoff;
Kivy SDL2-backed `ScrollView` tests exercise wheel chaining and a
touch-pan edge-routing branch around Kivy's native gesture handler.
Native Kivy motion/kinetic physics remains toolkit-owned rather than
reimplemented. The full per-operation live-device and lifecycle
matrix is explicitly reserved for G3-C4/C5/C6; this certificate does
not mislabel their work as executed.

**Immutable source certificate:**
[`dda1499ee30614bdbd17585b11affc545195967b`](https://github.com/Neuri-AI/PSX/commit/dda1499ee30614bdbd17585b11affc545195967b).
[Native layout selective CI #38348735216](https://github.com/Neuri-AI/PSX/actions/runs/38348735216)
completed **SUCCESS** with 18 successful jobs, zero failed,
and only the future G4 final API gate skipped. The certificate includes
the applicable Qt bindings, Tkinter, Kivy, Headless, Chromium geometry
oracle, Rust/Python differential, and Windows/macOS wheel and fallback
jobs. The companion commit-subject, runtime-boundary and Flex-contract
workflows also completed successfully on the same code SHA.

**Acceptance:** **F3-G3-C3 CLOSED.** C4 owns resize/reflow/lifecycle
and transactional offset preservation; C5 owns the full executed
backend × operation behavior matrix; C6 owns formal G3 gate signoff.
The documentation-only closing commit must not rerun product tests.

### F3-G3-C4 — native Scroll reflow, DPI and transactional lifecycle

**Behavioral change:** `psx/sfle/native_scroll_transaction.py` records
the native viewport content extent, scroll positions, scroll ranges and
previous logical overflow *before* each SFLE native geometry transaction.
The Qt, Tkinter and Kivy commit bridges recover the previous logical
offset from the pre-commit snapshot, apply the newly calculated SFLE
viewport/content extent and clamp the old offset through the C1
mathematical contract. This avoids recomputing Kivy's old pixel offset
using the new content range or trusting a scrollbar reset by a resize.
SFLE border rectangles remain immutable. The existing UI-thread,
semantic epoch and generation gates remain authoritative.

**Failure recovery:** The three native layout bridges capture scroll
hosts before applying geometry, and restore native viewport content
geometry, Qt scrollbar limits and values, Tk Canvas scrollregion and
offsets, and Kivy content size/hints and scroll fractions if native
application or readback fails. Restored Scroll logical-offset/overflow
metadata also matches the pre-transaction snapshot. This extends
existing widget-geometry rollback without recreating widgets or
reassigning native focus. Current renderer invalidation/unmount
epochs and native resource cleanup continue to govern cancellation
and released handles.

**Executed evidence:** `tests/test_scroll_transactions.py` verifies
Kivy pixel-offset preservation over changed overflow extents,
clamping after content shrink, native rollback and Qt focus/identity
invariants with observable ports. The native `tests/test_pyside6_native_layout.py`
and `tests/test_tkinter_native_layout.py` suites certify reflow,
offset preservation, widget identity and injected failure after
native viewport mutation. The Kivy SDL2 native suite verifies
`renderer.commit_layout(root)` preserves logical X/Y offsets and
widget identity on a mounted overflown ScrollView. Existing native
semantic/DPI/viewport, unmount and stale-generation tests continue
in the same required CI selector. No new public event/prop contract
or parallel layout solver was introduced.

**Immutable source SHA:** [`2bff3823a9957476617428ce02c812b08a08937c`](https://github.com/Neuri-AI/PSX/commit/2bff3823a9957476617428ce02c812b08a08937c).
[Full impacted-source native layout CI #38349973963](https://github.com/Neuri-AI/PSX/actions/runs/38349973963)
completed SUCCESS on code SHA `aacfe567e17a31b396e50abf66f9411c2d30a713`
with 18 successful jobs, zero failures, and only the future G4 API
gate skipped, including Qt, Tk, Kivy, Headless, Rust/Python, browser
and Windows/macOS. The final source/test-only commit adds Kivy's
reflow/readback assertion without modifying production code.
[Incremental native CI #38350150740](https://github.com/Neuri-AI/PSX/actions/runs/38350150740)
completed SUCCESS on final source SHA `2bff382`: 3 successful jobs
(classifier, executed Kivy native suite, required verdict); all other
product jobs correctly skipped under selective routing. Combined
these certify all C4 modifications without falsely claiming that
a single final run reran unrelated suites. Subsequent documentation-only
closure must execute zero product tests.

**Acceptance:** **F3-G3-C4 CLOSED. Next: F3-G3-C5.**
C5 must build strict per-operation executed evidence for each
applicable native backend, with no borrowed pass statuses; C6
remains responsible for the final G3 gate signoff.

### F3-G3-C5 — executed, backend-specific Scroll operation receipts

**Fail-closed certifier:** `tests/certification/scroll_operation_receipts.py`
is the single source of the dedicated Scroll operation inventory. It
requires a passing, executed and **same-backend** JUnit testcase for
every applicable operation, verifies its actual originating test
module and rejects absent, failed, errored or skipped evidence.
Identically named tests from another backend or unrelated module cannot
certify an operation. The inventory explicitly identifies Headless
native focus, native kinetic touch and native widget unmount as
not-applicable, rather than inventing successful native execution.
`tests/test_scroll_operation_receipts.py` includes executed negative
fixtures for omitted tests, foreign evidence, skipped cases, mixed
pass/fail results and unrecognized backend identifiers.

**Mandatory backend matrix:** The executed mandatory Scroll-specific
inventory contains **19 unique backend × operation cells**:
Qt 5, Tkinter 5, Kivy 4, Headless 5. Each row names a distinct
operation-specific test. Qt verifies viewport clipping/offsets,
nested wheel chaining, keyboard boundary release, reflow/focus/widget
identity and injected-failure rollback. Tkinter verifies Canvas
clipping/offsets, nested wheel chaining, keyboard boundaries, native
reflow/identity and injected-failure rollback. Kivy verifies mounted
viewport, clipping/offsets, wheel/touch nested chaining and a separate
mounted Scroll reflow/identity test. Headless verifies offset clamp,
independent axes, disabled-input residual, nested offset independence
and content-shrink behavior. These receipts are **executed tests**,
not citations to source documentation or a passing Flex test.

**CI enforcement and archiving:** The targeted Qt, Tk, Kivy and
Headless native jobs now fail if their Scroll-specific JUnit contract
fails, even when the rest of their tests are green. Every job uploads
its JUnit-backed JSON receipt: the Qt native job archives
`scroll-qt-operations.xml` and `scroll-qt-operations.json`;
Tk/Kivy/Headless add their `scroll-*-operations.json` to the existing
native-layout receipt artifacts. The archival files are produced on
the same code SHA as their test execution. The full native selector
also retains the four Qt binding-parity jobs, Chromium, Rust/Python,
Windows/macOS wheel/fallback and the semantic naming guards.

**Immutable code SHA:** [`c58c9f594e0dbcc2db6c2512d798e7fb8f22fdaa`](https://github.com/Neuri-AI/PSX/commit/c58c9f594e0dbcc2db6c2512d798e7fb8f22fdaa).
[Native layout CI #38351225565](https://github.com/Neuri-AI/PSX/actions/runs/38351225565)
completed **SUCCESS**: 18 successful jobs, zero failures,
and the intentionally deferred G4 API-removal gate skipped.
The run archived eight corresponding artifacts, including the
dedicated Qt Scroll receipt and each other backend's Scroll JSON.
The accompanying code-SHA commit-subject, runtime-boundary and
Flex-contract workflows must remain green for formal F3 signoff;
documentation-only updates run no product tests.

**Scope distinction:** The 19-cell matrix certifies its explicitly
declared, applicable Scroll operations. It is not a claim that every
hardware-specific touch device, every OS input-method permutation,
or the later full public component × property × event matrix (G5) has
been tested. C6 separately owns adversarial review of coverage
completeness, cross-platform source signoff and formal closure of
the G3 gate. Missing additional applicable operations discovered
during C6 cannot inherit these 19 passes and must be tested.

**Acceptance: F3-G3-C5 CLOSED. Next: F3-G3-C6.**

### F3-G3-C6 — adversarial coverage audit and final Scroll gate acceptance

**Audit disposition: G3 CLOSED** on immutable product/test source SHA
[`2621ebd11dd8dea90ece6698f83e676d503eabcc`](https://github.com/Neuri-AI/PSX/commit/2621ebd11dd8dea90ece6698f83e676d503eabcc).
This gate extends, rather than merely reuses, the earlier C5 receipt
inventory. The source-SHA acceptance baseline has **25 mandatory
backend × Scroll operation receipts**: Qt 7, Tkinter 7, Kivy 6,
Headless 5, with three Headless-only native cases classified explicitly
as not applicable. The added mandatory cases cover live Qt/Tk teardown,
disabled-axis reset with nonzero prior offsets, and real Kivy native
unmount and failure-injection rollback.

**Adversarial challenges and dispositions:**
1. **Missing lifecycle coverage — corrected.** Added executable
   Scroll-specific native teardown cases on Qt, Tk and Kivy; no
   generic component lifecycle test is borrowed as Scroll evidence.
2. **Changing enabled axes with existing offsets — corrected.**
   Added real Qt and Tk viewport tests that begin scrolled,
   reconfigure allowed axes, and verify the forbidden-axis offset
   returns to zero while the permitted-axis offset survives.
3. **Native Kivy rollback evidence — corrected.** Injected an
   exception *after* a Kivy viewport mutation and asserted restoration
   of scroll fractions and content extent.
4. **Evidence shrinkage / phantom reference — rejected by CI.**
   The mandatory operation names have an independent 25-cell
   acceptance baseline, and AST checks verify every declared
   reference names an actual method in that backend's test module
   without duplicate method reuse. Foreign-backend, missing,
   skipped, failed and mixed-result JUnit negative fixtures remain
   enforced.
5. **Source integrity — accepted.** Native layout remains exclusively
   SFLE-owned; scrollbar values and Kivy fractions are runtime state,
   not a second layout solver. The prior native-transaction tests
   preserve logical offsets across reflow and restore native state
   after failed commits. Existing epoch, generation and UI-thread
   checks stay active. Source naming rules remain enforced.

**Cross-platform proof (two immutable code SHAs, not a fabricated
single-run aggregate):** [Full native validation #38352219760](https://github.com/Neuri-AI/PSX/actions/runs/38352219760)
is **SUCCESS** on SHA `bf5efe765402a3a6b44e2abb95ad454012d08f4c`:
18 successful jobs, zero failures, with only the later G4 API-removal
gate skipped. It includes Kivy SDL2, Tk/Xvfb, Qt bindings, Headless,
Chromium geometry, Rust/Python parity and Windows/macOS native wheel
build/fallback jobs. The final independent-baseline-only test commit
SHA `2621ebd` is separately certified by
[selective CI #38352462949](https://github.com/Neuri-AI/PSX/actions/runs/38352462949):
3 successful jobs (change classifier, executed core/inventory tests,
mandatory verdict), zero failures; unrelated product jobs were
properly skipped. All four workflows on the final code SHA completed
SUCCESS.

**Scope and residual limitations:** This certifies the declared
portable Scroll contracts and their concrete backend test operations,
not every physical touchscreen, trackpad model, compositor, accessibility
input mechanism or arbitrary third-party embedded native widget.
Kivy kinetic physics remains toolkit-owned. Headless cannot certify
native focus or touch. The broader all-components × props × events
matrix and removal of public Row/Column belong to later F3 gates;
those cannot inherit a Scroll-only pass. Hardware-specific or
unregistered operations must be recorded as new required tests if
they become release-blocking — never marked executed without receipts.

**Formal decision:** **F3-G3 CLOSED**. G1, G2 and G3 are closed;
the next F3 gate is **F3-G4**, not additional Scroll increments.
This documentation-only close must run no product tests.

### F3-G4 — final removal of legacy layout authority

**Decision: G4 CLOSED** on immutable code SHA
[`5bae7e1d5b764f7db1e1168d87be0402c4883e33`](https://github.com/Neuri-AI/PSX/commit/5bae7e1d5b764f7db1e1168d87be0402c4883e33).
The full native selector
[run #38361331349](https://github.com/Neuri-AI/PSX/actions/runs/38361331349)
completed **SUCCESS: 19 successful jobs, 0 failed, 0 pending**,
including the mandatory new G4 gate, real Kivy/Tkinter/Qt,
Headless, browser Chromium geometry, four Qt binding parity runs,
Rust/Python differential and native wheel/fallback on Windows/macOS.
Commit subject, runtime boundaries and Flex contract certification
also completed SUCCESS on that same SHA.

**Active code and API retirement:** Removed `Row`/`Column` from
`psx.__all__`, public Python builders, built-in registry,
component contracts/defaults/props/validators, native adapters
for Qt, Tkinter and Kivy, and competing Headless geometry paths.
Removed eight legacy adapter modules; a dedicated Scroll padding
helper retains the shared non-layout normalization without importing
deleted modules. No aliases, wrappers or silent markup translations
were introduced.

**Executable acceptance:** The G4 CI job now runs on **every
non-documentation code change**, not merely when the selector
explicitly requests the `legacy` suite. It runs a tracked-source
AST scan (`scripts/ci/legacy_layout_inventory.py --check`) that
fails for legacy symbol references or markup in shipped
`psx/`, `examples/` or `benchmarks/` code; historical negative
test fixtures and migration/audit scripts remain searchable but
are not mistaken for exported APIs. It then verifies that
`Row`/`Column` are absent from the public package, exports
and built-in registry. Core tests execute explicit public
import/markup rejection and no-backend-adapter checks.
The CI summary fails closed if the G4 job does not pass.
Qt, Tkinter, Kivy and Headless retained their SFLE-owned Flex
geometry and their native operations. A missing SFLE bridge still
raises instead of delegating geometry to a toolkit layout manager.

**Migration:** Shipped examples and benchmark layouts were migrated
to directional `Flex`, as were affected test consumers. The
public API, README and portable component references now document
`Flex`, preserving architecture/audit history separately.
Native widget measurement, events, Scroll and legitimate
toolkit viewport internals remain intentionally unaffected.

**Scope:** G4 certifies the *removal* of duplicate public layout
authorities. It does not replace G5 final integration certification
across every supported widget, backend, packaging mode and adverse
combination. Those guarantees must be tested separately.

**Next gate: F3-G5.**
