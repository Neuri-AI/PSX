# PSX implementation roadmap

Implementation status is evidence-based; milestone placement does not certify a
feature as complete.

## Commit convention — binding agreement for all remaining PSX phases

**Approved 2026-10-12. Applies to all new commits in the remaining F3 work
(including G2–G5), F4, F5, and subsequent PSX development.** Follow
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <concise imperative description>
```

- Write commit subjects and bodies **in English**. Describe the actual
  behavior or implementation change, not merely the milestone identifier.
- Select the scope from the **subsystem actually changed**, not the phase:
  `sfle` exclusively for changes to the renderer-neutral mathematical
  engine; `layout` for PSX layout integration/viewport geometry;
  `renderers` for Qt/Kivy/Tkinter native adapters; `components` for
  portable components; `measurement` for intrinsic measurements;
  `reconciler` for reconciliation/ownership; `events` for interactions;
  `ci` for workflows; `docs` for documentation. For tests use the
  relevant subsystem (e.g. `test(layout)`, `test(renderers)`) rather
  than a redundant generic `test(testing)` scope.
- Use the appropriate Conventional Commit type (`feat`, `fix`,
  `test`, `refactor`, `perf`, `docs`, `ci`, `chore`, etc.).
- **Do not use `sfle-f3`, `sfle-g2`, `f3`, `g2`, or future phase/gate
  names as generic scopes.** Reserve `sfle` for actual SFLE Core changes,
  even if a commit takes place during F3–F5.
- Track roadmap and certification linkage in the PR, issue, milestone,
  documentation, or, when useful, in the commit body using `Phase: F3`,
  `Gate: G2`, `Block: C1`. These are optional metadata, **not** required
  in every subject.
- **Do not rewrite existing commits** to retrofit this convention; apply
  it prospectively, including all remaining PSX phases.

Examples:

```text
feat(renderers): integrate Switch, SpinBox and Select with native layout
fix(layout): prevent native controls from overriding committed geometry
test(renderers): verify borrowed widget restoration on unmount
ci: require native backend lifecycle certification
fix(sfle): correct fixed-point overflow in the core engine
```


| Milestone | Name | Status |
| --- | --- | --- |
| M0 | Research & Architecture | implemented baseline |
| M1 | Core & Headless Renderer | implemented baseline |
| M2 | PySide6 Renderer | implemented baseline |
| M3 | Reactivity & Hooks | implemented baseline |
| M4A | PSX Markup | implemented baseline |
| M4B | Static Lexical Transform | implemented baseline |
| M5 | Pydux Integration | implemented baseline |
| M6 | Qyro Integration | implemented baseline |
| M7 | Tkinter Renderer | implemented; native macOS smoke testing remains environment-dependent |
| M8 | Intelligent Hot Reloading | existing vertical slice; remaining work postponed to F6 |
| M9 | Kivy & Qt Variants | implemented; native graphical smoke remains environment-dependent |
| M10 | Advanced UI & Native Interoperability | implemented; native adapter smoke is renderer-dependent |
| M11 | Alpha Release | alpha release candidate |
| M12 | PSX Playground & Visual Layout Inspector | implemented standalone React semantic development slice |
| M13 | PSX Visual UI Builder | planned |

## M8 — existing implementation baseline (remaining work deferred to F6)

Dependencies: M3 scheduling/disposal, M4B source transforms, and renderer
ownership. The implemented dev-only baseline uses a dependency-free polling
watcher, debounce, project-path classifier and supervised child process. Python
source, manifests and native extension changes receive `PROCESS_RESTART`;
caches, virtual environments, build output and editor artifacts are ignored.
The supervisor prevents overlapping children and continues watching after a
restart. Frozen and non-development configurations disable watching.

Acceptance currently verified: rapid changes debounce; atomic replacement is
detected; child restart is clean; snapshots are JSON-only/versioned; production
configuration is disabled. Deferred acceptance: compatible in-process component
refresh, hook-state preservation across a code edit, safe module rebind,
automatic snapshot restoration and Qyro CLI `--hot-reload` integration.

## Dependencies, risks and testing

M9 depends on validated backend API/version matrices. M10 depends on D11 layout
semantics and capability-gated native ownership. M11 requires CI, packaging,
performance/leak validation and documentation. M12/M13 are post-alpha and must
reuse D11 semantics. The principal M8 risk is pretending arbitrary Python or
native dependencies are safe to reload; the supervisor is therefore the
documented fallback, not a failed hot-update implementation.

Every supported renderer retains its own native identity/event/cleanup tests.
M8 requires watcher debounce, atomic save, ignored paths, child lifecycle,
syntax-error recovery, frozen/production disable, snapshot validation and
diagnostics tests. Native GUI smoke tests complement, but do not replace,
deterministic headless tests.

## Pending — SFLE CSS extensions after the F2 alpha scope

**Recorded 2026-10-11. Decision status: DEFERRED — FORMALLY APPROVED.**
The user explicitly approved both SFLE F2 point-5 deferrals on 2026-10-11.
Neither full feature is advertised as supported in the frozen F2 alpha
capability manifest or automatically assigned to F3. Previously certified
bounded positive cases remain available while unsupported cases fail closed.
See [F2 five-point closure tracker](architecture/sfle-f2-implementation.md)
and [F2 point-5 final certification](architecture/sfle-f2-point5-final-certification.md).

| ID | Deferred candidate / feature | User-visible value | Remaining implementation and certification | Planned timing / status |
| --- | --- | --- | --- | --- |
| **SFLE-CSS-01** | `aspect_ratio` and replaced-element transferred intrinsic sizing (images/media) | An image or other replaced element can infer its missing height from width and ratio (or vice versa), including native intrinsic sizing. | Define sizing rules and transferred size suggestions with min/max and box model constraints; implement in both Rust and Python; verify identical accepted/rejected classes and diagnostics, Chromium geometry ≤0.01 logical px and native projected geometry ≤1 px, including invalid ratios and fallback. | **DEFERRED — APPROVED IN WRITING 2026-10-11.** Post-F2 CSS milestone not yet scheduled; not part of F3. |
| **SFLE-CSS-02** | Intrinsically `auto`-sized Flex container with `flex_wrap` / multi-line sizing | A wrapping Flex can determine its own dimensions from children instead of requiring definite width/height to form and size lines. | Implement intrinsic size contribution and wrapped line formation under indefinite constraints, dependencies and min/max constraints; match Chromium and Rust/Python geometry/diagnostics including pathological and recursive cases; certify supported bounds and fail-closed behavior. | **DEFERRED — APPROVED IN WRITING 2026-10-11.** Post-F2 CSS milestone not yet scheduled; not part of F3. |

**Safeguards until implementation:** preserve previously certified
definite-main-axis `flex_wrap` and bounded definite-axis `aspect_ratio`
cases. A replaced element with `aspect_ratio`, two auto dimensions,
missing native intrinsic measurement and no cross-axis stretch must reject
with `SFLE_UNSUPPORTED_FEATURE`, not fabricate 0 × 0 geometry. An
intrinsically auto-sized wrapped Flex whose main axis remains indefinite
**without a definite max-size cap** must likewise reject rather than assume an intrinsic line width. Both
Rust and Python must agree on code and source node ID; other unlisted CSS
dependency graphs remain fail-closed. A partial supported case does not
constitute full CSS capability advertisement.

**How to retrieve this later:** ask for `SFLE-CSS-01` or
`SFLE-CSS-02`, or the "SFLE pending CSS extensions" section of this
roadmap. Implementation requires a separately approved future CSS
enhancement with corresponding Rust/Python/Chromium certification.
The seven normative F2 exit checks and same-commit CI must still pass
before F2 is declared CLOSED. F3 remains renderer integration/migration,
not a catch-all for unimplemented CSS features.

## F3 — native SFLE integration and component coverage (closed)

**Base:** `develop` at `979b6ed9e86c63b640d498439045910ed1a189aa`.
**Feature branch:** [`feature/f3-sfle-native-adapters`](https://github.com/Neuri-AI/PSX/tree/feature/f3-sfle-native-adapters).
**CURRENT STATE (2026-10-14): G1–G5 CLOSED. F3: 5/5 official gates CLOSED (100%).** G5 was accepted by the project owner after the cross-platform local certification matrix completed on Windows, macOS and Linux for Python 3.10–3.13 with no failed cell. PySide2 exclusions are accepted only where the runner records its documented Python-version or Apple-Silicon wheel limitation. The historical checkpoints are preserved in the [F3 Implementation Plan](architecture/sfle-f3-implementation.md).

**Formal G2 certificate:** [tested code SHA `700f1b3`](https://github.com/Neuri-AI/PSX/commit/700f1b3af3334b99f39fcf30a053d2a65838fc17); [full required F3 CI #38335949031 SUCCESS](https://github.com/Neuri-AI/PSX/actions/runs/38335949031) plus three companion workflows GREEN on that SHA. Native JUnit operation receipts: **409 required executed PASS**, **359 reviewed N/A**, **0 pending**, across Qt (all four bindings, normal and 1.5 DPI), Tkinter, Kivy and Headless. Seven native receipt artifacts archived; C4 external ownership and C5 resource/invalidation contracts remain separately verified. C6-1 numerical geometry, C6-2 registry/native/custom integration, C6-3 fail-closed JUnit operation receipts and C6-4 final code/documentation signoff are all CLOSED. Logical Chromium tolerance is ≤0.01 px with equivalent intrinsic inputs; Qt's native readback bound is in device-independent coordinates and must not be misreported as ≤1 physical framebuffer pixel at high DPR. G3 owns full Scroll; G4 removes legacy Row/Column; G5 audits end-to-end public props/events. **F3 complete; next phase: F4.**

**Documentation-only certification policy:** Final documentation changes keep the immutable code SHA above as product-test authority. The final docs HEAD is separately checked by the intelligent CI and must not execute product tests. Any subsequent code edit requires recertification.
[Read the full F3 implementation plan and mandatory G2 component matrix](architecture/sfle-f3-implementation.md).

**G1:** public Flex contract + explicit Scroll content policy.
**G2 (mandatory expanded scope):** integration of all applicable built-ins
from `psx/core/registry.py`, central layout props and lifecycle, Qt/Kivy/Tk/Headless
native ports, mixed component trees, and testable `Native`/custom adapter
measurement/application contracts. Tests must cover every supported
component/backend pair; unsupported pairs produce explicit errors.
**G3:** native Scroll viewport/content isolation, nested scrolling, events,
offsets, clipping and scrollbars.
**G4:** remove Row/Column builders, exports, registries, adapters, native
portable layout duplication and stale examples without compatibility shims.
**G5:** complete integration, cross-platform CI and **mandatory public functional behavior certification**. Audit the code-derived registry × backend × every advertised property, event, exposed method and meaningful interaction/edge-case scenario; require executed, behavior-specific native evidence with reviewed applicability and fail-closed receipts. No required gaps, skipped tests or false PASS statuses; certify the final immutable SHA. [Full G5 functional acceptance specification](architecture/sfle-f3-implementation.md#g5-functional--mandatory-exhaustive-public-behavior-audit).

**G5 closure record:** the owner accepted the successful local portability matrix as the final functional signoff. The code-derived public-behavior census remains a development coverage instrument; its remaining pending rows are not a reopening condition for this owner-authorized F3 closure.

**CI and test execution policy (F3, mandatory):**
[Smart CI selective routing and F2 workflow reuse](architecture/sfle-f3-ci-strategy.md).
Documentation-only edits run **no product tests**; regular code changes
run only impacted test suites and dependency consumers. For F3 PRs into `develop`, `.github/workflows/native-layout-selective.yml` now routes impacted suites using `scripts/ci/impact.py`, with an exact-SHA aggregate status; F2 legacy workflows remain available for `main` and explicit manual use. Verified G1.2 [RED #38153047652](https://github.com/Neuri-AI/PSX/actions/runs/38153047652), [GREEN #38153141925](https://github.com/Neuri-AI/PSX/actions/runs/38153141925). G2 certification is CLOSED on its cited immutable code SHA; G5 is CLOSED by the owner-authorized signoff above.

G2 **cannot** be closed using Flex + Button-only examples; all supported
component/backend matrix entries, tests and custom-adapter gates must pass.
**F4** — owner-approved responsive twelve-column Flexbox Grid contract (2026-10-14): [normative Grid and GridItem contract, mathematical cases and G1–G6 acceptance gates](architecture/responsive-grid-contract.md). The normative contract, [agent prompt](architecture/responsive-grid-agent-audit-prompt.md), [implementation handoff](architecture/responsive-grid-implementation-handoff.md), and [capability certification policy](architecture/capability-certification-policy.md) are **integrated into `develop` via [PR #15](https://github.com/Neuri-AI/PSX/pull/15)** (merge SHA `2cbdfb597624142cec74b2ef66fb74f07fccd71f`). The former documentation-only branch has been deleted; it is not the F4 development branch. **G1 is IN PROGRESS** in [`feature/responsive-grid-public-contract`](https://github.com/Neuri-AI/PSX/tree/feature/responsive-grid-public-contract) ([draft PR #16](https://github.com/Neuri-AI/PSX/pull/16)): preliminary validation, declarations, tests and CI routing are in progress, **not certified or merged into `develop`**. G2–G6 remain NOT STARTED; **0/6 gates CLOSED**. Do not reinterpret selective GREEN CI as complete public-behavior census receipts. Continue from F3 without reusing historical tests as F4 certification. Every product increment must include behavior-specific tests, verified `scripts/ci/impact.py` routing and applicable executed public census receipts. Documentation-only changes must select zero product tests.
`SFLE-CSS-01` and `SFLE-CSS-02` remain separately deferred; neither
becomes F3 work.

## SFLE — official phase status (2026-10-11)

**F1 CLOSED · F2 CLOSED · F3 CLOSED (G1–G5 CLOSED; 5/5 gates CLOSED = 100%).**

- [Formal F2 final exit certificate](architecture/sfle-f2-final-certification.md)
- [F2 current implementation and normative exit ledger](architecture/sfle-f2-implementation.md)
- [F2 point-4 Scroll and adapter authority certificate](architecture/sfle-f2-point4-final-certification.md)

**F3 implementation still ahead:** connect the tested SFLE geometry authority to production Qt/Kivy/Tkinter/Headless renderers, preserve native Scroll viewport/input/offsets while applying SFLE content geometry, remove Row/Column without compatibility aliases and retire redundant layout algorithms. The F2 port contract exists, but *production renderer migration is not claimed done*.

**Future CSS additions NOT part of F3:** SFLE-CSS-01 (full replaced-element aspect-ratio intrinsic sizing) and SFLE-CSS-02 (intrinsically auto-sized wrapped Flex) remain separately deferred above, without a scheduled milestone. Previously certified bounded subset remains supported; unsupported dependencies fail explicitly.

## Pending — SFLE incremental mathematical layout solver (future optimization)

**Status: PROPOSED / NOT STARTED.** Implement **after F3-G2-C5 closure** and
separately from the G2-C6 native precision and G3/G4/G5 acceptance contracts.
Assign a milestone when the current F3/F4 work is stabilized; this entry
does not change the F3 exit criteria or assert that mathematical incrementality
has already shipped.

**Motivation:** PSX Core's Reconciler already performs incremental VNode/widget
updates, and SFLE's native adapters can reuse unaffected intrinsic measurements
and avoid identical native geometry writes. However, both Rust-primary and
Python-fallback SFLE currently recompute the immutable **full mathematical
layout snapshot** on a layout commit. The proposed work is to reuse valid
subtree math where its inputs and dependencies are unchanged, while retaining
SFLE as the sole authority for Flexbox geometry.

**Proposed design:**

1. Propagate precise dirty-node/layout-input revision information from PSX
   reconciliation and native measurement invalidation into SFLE, without moving
   Flexbox layout decisions into the Reconciler.
2. Build a dependency graph for the mathematical solver (ancestors, sibling
   flex-line interactions, intrinsic sizes, constraints, percentages, wrap,
   min/max, root viewport, font/theme/DPI effects) and compute a conservative
   invalidation closure. Reuse results only when all dependent inputs remain
   valid; otherwise fall back to a full solve.
3. Add deterministic reusable layout-subtree/line results with explicit cache
   keys and transactional publication: no stale geometry on concurrent
   invalidations, generation changes, exceptions or disposed VNodes.
4. Implement the **same observable semantics in Rust and Python**. Do not
   weaken browser parity, fixed-point saturation, 0.01px logical precision,
   1px native tolerance, or Qt/Kivy/Tkinter/Headless readback contracts.
5. Add complexity and performance baselines on representative large nested
   trees (e.g., 1,000 nodes with one changed leaf). Instrument nodes/lines
   recomputed, cache hits, solver time and memory; compare against the current
   full-snapshot baseline and detect regressions.

**Exit criteria:** unchanged tree with no relevant invalidation reuses
mathematical results; localized updates recompute only a proven dependency
closure; updates that affect siblings/ancestors correctly propagate and produce
byte/precision-equivalent results to a fresh full solve in both engines;
viewport/theme/DPI changes conservatively invalidate applicable dependencies;
stale or failed rounds never publish caches; cross-backend and Chromium
differential tests are GREEN on one immutable SHA; measurements demonstrate
a meaningful performance gain without unacceptable memory/regression cost.
Document fallback cases and maintain a full-compute reference implementation
for certification.

**Not this proposal:** PSX VDOM reconciliation, already-certified selective
native intrinsic measurement, identical-rectangle write suppression, and
C5's three increments remain separate, existing responsibilities. This is
an **optional post-C5 SFLE solver optimization**, not a missing C5 guarantee.

## Pending — portable Flexbox/Grid layout system (proposal) (historical design proposal)

**Architecture document:** [SFLE — Shared Flex Layout Engine](architecture/sfle.md).
**F1 decisions:** [Approved architecture and component contracts](architecture/sfle-f1-contracts.md).
**Formal F1 closure:** [Final architecture, LTR/RTL, Rust fallback and SFLE migration](architecture/sfle-f1-final-architecture.md).
**D-F1.10 correction:** `Row`/`Column` will be removed, not preserved or
translated; `Flex` becomes the single public Flexbox distribution component.
This is an architectural decision only: no code removal or F2 start authorized.
**Historical F1 proposal only:** F2 was not yet authorized when this paragraph was written. Current official state: F2 CLOSED, F3 NOT STARTED. See the [F2 certificate](architecture/sfle-f2-final-certification.md).
**Ratified F1.6/F1.7 contract:** [CSS box model and percentage resolution](architecture/sfle-f1-box-model.md).
Approved: closed shared metadata validation with single-root components,
metadata inert outside Flex, layout_width/layout_height namespace, and tagged
immutable lengths. The CSS box model and property-specific percentage rules
are specified, while D-F1.8–D-F1.12 and F1-RUST remain pending.

D-F1.1–D-F1.12 and F1-RUST approved at architecture level: `Flex` with direct child layout props,
`snake_case`, progressive browser conformance, UI-thread native measurement,
strict geometry comparison, LTR + RTL, full SFLE replacement of layout math,
selective caching, and Rust-primary/Python-fallback computation.

SFLE is the proposed backend-neutral CSS Flexbox geometry engine. The design
prioritizes browser-like visual layout results across Qt, Kivy, Tkinter, and
Headless, with renderer-specific intrinsic measurement and geometry application.
The following is the historical architectural proposal; SFLE F2 is now certified and F3 renderer integration remains outstanding.

**Historical F1-only status:** at the time of this initial design proposal F2 had not yet been authorized. The current F2 phase is CLOSED; see the [final certification](architecture/sfle-f2-final-certification.md). Reference:
[Flexbox Grid](http://flexboxgrid.com/) (a responsive 12-column layout system
built on CSS Flexbox). PSX should reproduce the *layout semantics* in native
desktop renderers rather than embed CSS or assume a browser engine.

### Scope to design

- **Flex-style layout:** row/column flow, `gap`, `wrap`, `grow`, `shrink`,
  `basis`, `align_items`, `align_self`, `justify_content`, and ordering.
- **Responsive 12-column grid (Flexbox Grid-inspired):** spans, offsets,
  automatic/equal-width columns, nesting, distribution and alignment; column
  sizes may depend on breakpoint rules for the **container/window width**.
- **Optional CSS Grid-like track layouts:** consider a distinct `Grid` /
  `GridItem` contract with explicit rows/columns, track sizing and spans.
  Do not conflate Flexbox Grid's flex-based 12-column system with CSS Grid.
- **Portable measurement and layout:** intrinsic/min/max sizing, percentage or
  proportional widths, `gap`/gutters, padding, constraint propagation,
  overflow behavior, high-DPI scaling and deterministic recalculation on resize.
- **Responsive behavior:** define desktop-appropriate breakpoints, initial
  layout and resize transitions; avoid unnecessary widget recreation or loss
  of component state during reflow.
- **Renderer support:** Qt, Kivy, Tkinter and Headless share the SFLE computation
  authority, with native measurement and geometry adapters.
- **Approved D-F1.10 correction:** during authorized migration, **delete**
  `Row` and `Column` from public builders, markup/registries and exports
  entirely; no aliases, wrappers or compatibility layers. `Flex` is the sole
  public row/column/reverse Flexbox layout component. SFLE replaces redundant
  layout algorithms. Retain `Scroll` as a separate native viewport/clipping/
  scrolling/event/offset component, with SFLE-compatible content geometry but
  **without** implicit Flex formatting. Flex item props remain inert outside
  explicit Flex. Rust remains primary with a parity-matched Python fallback.
  Migrate all examples, boilerplates, docs and architecture references
  during implementation. Reuse SFLE geometry in Playground and UI Builder.

### Aspirational markup (not currently supported)

```xml
<Flex direction="row" gap={12} wrap="wrap" justify_content="between">
    <Grid columns={12} gap={12}>
        <GridItem span={8}>
            <Sidebar />
        </GridItem>
        <GridItem span={4}>
            <Details />
        </GridItem>
    </Grid>
</Flex>
```

The snippet illustrates layout intent only; Grid component names and responsive syntax remain **not yet decided**;
Flex and direct-child layout property architecture is approved. Future design
cards should settle those choices before any implementation. Do not add
automated tests as part of the current component DX-first rollout.

## F5 — Expressive Markup (architecture approved, implementation not started)

**Owner approval:** 2026-10-14. **Normative specification:** [F5 expressive markup contract](architecture/f5-expressive-markup-contract.md). F5 contains **only** expressive markup; **M8 Intelligent Hot Reloading belongs to F6 and is postponed** pending owner-led changes to Qyro CLI and Qyro Engine.

The approved M4B developer-authored syntax is `{condition && <Element />}`, `{condition ? <A /> : <B />}`, `{items.map((item) => <Element key={item.id} />)}`, and `on_click={() => handler()}` arrow callbacks. `==`/`!=` retain Python comparison semantics; `===`/`!==` are rejected. Falsy conditional results produce **no VNode**, including numeric zero. Static compilation produces ordinary Python AST and must retain lexical captures, source maps, security boundaries and native reconciliation. No JavaScript engine is introduced.

**Approved F5 gate plan:** G1 grammar and semantics; G2 conditional compilation; G3 `.map()` list transforms; G4 arrow functions; G5 reconciliation/security/composition; G6 integral immutable-SHA certification and owner signoff. **0/6 gates CLOSED; none is claimed implemented merely because architecture is approved.** Functional tests, `scripts/ci/impact.py` routing and executed public census receipts are required where applicable. See the normative contract for acceptance requirements, error behavior and exclusions.

## F6 — Intelligent Hot Reloading (future, postponed)

**Assigned milestone:** M8; not part of F5. **Status:** POSTPONED / NOT AUTHORIZED FOR NEW IMPLEMENTATION. Qyro CLI and Qyro Engine are currently being modified by the owner. Do not integrate or alter these external systems for hot reload until that work is ready and a separate F6 specification is approved.

**Existing baseline only:** `psx.devtools` watcher, debounce, safe process restart, constrained component refresh, and Qyro component reloader remain as currently implemented. The unfinished goals—safe in-process refresh across changes, stronger dependency invalidation and module rebind, automatic snapshot restoration, integrated CLI launch/flags, recovery, diagnostics, cross-backend certifications—remain in F6 for later review. They are **not** F5 blockers. See [M8 hot-reloading implementation boundaries](m8-hot-reloading.md). F6 gate count has not been approved.

