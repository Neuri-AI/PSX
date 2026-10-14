# Responsive Grid — implementation and certification progress

> **Living agent handoff.** Update this file in GitHub whenever an increment changes state, and **in the same work cycle as implementation, tests, impact routing and census receipts**. This is an internal F4/G1 planning record; never use stage codes as opaque names for production files, functions, or tests.
>
> Last evidence review: 2026-10-14. Working branch: `feature/responsive-grid-public-contract`; draft PR #16 to `develop`. The SHA and workflow results below describe **the reviewed execution**, not a promise that the branch has not advanced. Always inspect current HEAD and PR checks first.

### G2 RTL and cross-axis CI certification — CLOSED (2026-10-14)

Source SHA `c445770b60d6db1a8e96901e39778a38fcc8c836` passed required Actions run `38556168341`: 20/20 jobs SUCCESS, including Rust/Python differential (292 Python tests passed), SFLE geometry contracts (624 tests passed), native Qt/Kivy/Tk/Headless/Chromium regressions, change router, aggregate and mandatory CI conclusion. The Grid/GridItem scoped census remains **62/62 executed_pass, 0 pending**; aggregate checkout SHA `7a2bae9e9db0da4f5a749a6ad0a06054cd8aff90` (distinct from source SHA). Evidence: https://github.com/Neuri-AI/PSX/actions/runs/38556168341 . This closes the *RTL/row-height/row-gap math sub-increment only*, not G2 overall. Cross-axis fixture `tests/fixtures/grid_cross_axis.json` and Rust/Python tests cover RTL, explicit heights, offsets, row gaps and invalid heights. Native Grid mounting and runtime reflow are still unsupported. Next: min/max constraints, overflow/saturation, full engine integration and final adversarial differential audit.

## G2 — Cinnamon mathematical Grid solver (new stacked branch)

**Branch:** `feature/grid-mathematical-solver` forked from G1 immutable closure `8044d5423ac69fecbce5b171e6c35905d2b9b031`; review as a **stacked PR targeting G1**, not as changes to the certified G1 branch. G1's 62/62 receipt certificate remains unchanged.

| G2 increment | State | Executable scope | Acceptance |
| --- | --- | --- | --- |
| Deterministic row packing and fixture schema | **CLOSED — certified 2026-10-14** | Rust-primary and Python-fallback `grid_math`, shared `tests/fixtures/grid_row_packing.json`, mixed auto/explicit row finalization, offsets, order stability, strict invalid rejection | Cargo unit tests, Python fixtures and randomized invariants, correct `sfle`+`rust` routing, green required Actions on immutable SHA |
| Fixed-point pixel geometry and gutters | **CLOSED — certified 2026-10-14** | Real content-box pixel widths, gaps, projections, non-divisible shares | Rust/Python pixel-level edge agreement, deterministic fixtures |
| RTL, row/cross-axis sizing and overflow | NOT STARTED | RTL logical reversal, row gaps/heights, constraints, overflow policy | Adversarial geometry tests, parity and error receipts |
| Engine integration and final G2 audit | NOT STARTED | Pure engine authority and native-facing math outputs only | Rust primary/Python fallback agreement on immutable SHA, regression preservation |

**Row-membership semantics frozen:** see [responsive-grid-mathematics.md](responsive-grid-mathematics.md). Mixed `[auto,8,auto,6]` produces rows `[auto(2),8,auto(2)]` and `[6]`; no closed-row backtracking. Logical offsets reserve columns but do not create native gaps. There is **no** native Grid widget layout at this stage.

**Census assessment:** no new public props/events/methods/interactions in this first internal solver increment. The existing G1 census remains the public contract; executable math fixtures and CI are mandatory. No fabricated Grid geometry receipts.

**Immutable certification of the first mathematical increment:** source commit `0b2e8d21fc0956a24ba1519c413f2f933b0ccbd0`; Actions `38554500438` concluded SUCCESS after all selected jobs, including Rust/Python differential, SFLE geometry tests, Qt/Kivy/Tk/Headless, Chromium, multiplatform native wheels, behavior aggregate and mandatory CI conclusion. Rust Cargo unit tests passed, Python interop + Grid fixtures ran **265 passed**, SFLE Python suite **597 passed**. Scoped existing public Grid/GridItem census **62/62 executed_pass, pending=0**, PR checkout SHA `92018a1ba1821ffd4b13d9602e77e631b29dea74`, aggregate job `115820826696`. See https://github.com/Neuri-AI/PSX/actions/runs/38554500438 . C1 introduces no new public contract receipts; the 62/62 are the unchanged G1 public contract. **G2 overall remains IN PROGRESS.**

**Next:** design and test fixed-point pixel geometry and gutter projection with exact Rust/Python edge agreement; do not expose native Grid geometry yet.


### Fixed-point horizontal projection — CLOSED (2026-10-14)

The second G2 increment adds `project_grid_rows` in Rust and Python, consuming finalized logical row memberships and producing stable 1/64px horizontal edges with exactly one column gap per adjacent actual widget, **no gap for empty logical offsets**. The shared fixture `tests/fixtures/grid_pixel_projection.json` and `tests/sfle/test_grid_math.py` include fractional/nondivisible widths, wrapped rows, offsets, impossible gaps and projection invariants. Existing `scripts/ci/impact.py` routes the solver and fixtures to Rust/SFLE suites, exercised by `tests/test_ci_impact.py`. The solver introduces no public props, events, methods or interactions, so no new public census rows are applicable.

**Immutable evidence:** source SHA `9d5ce3d5dfb64496461e14df557d867c3e196dc5`; PR checkout SHA `d537525507029e87ae6bfc25cac78a9272b60c5a`; required Actions run `38555560595` completed **SUCCESS**, including Rust and Python parity tests, SFLE geometry, native regression matrices, existing public-behavior aggregate and mandatory CI conclusion. Existing Grid/GridItem public contract census remained **62/62 executed_pass, pending=0** (aggregate job `115824318130`). The prior code run `38555221865` was cancelled due to intervening synchronization and is **not** closure evidence. Review https://github.com/Neuri-AI/PSX/actions/runs/38555560595 .

**Still pending for G2 overall:** RTL horizontal reversal, row heights and row gaps, min/max intrinsic overflow policy, integration of these pure calculations with the engine and a final cross-language parity audit. This step does **not** certify native Grid mount or runtime reflow.

## Where to resume

**F4 / G1 — CLOSED. G2 — IN PROGRESS (first row-packing increment CLOSED; pixel math next).** G1 is certified; do not restart it.

The last reviewed source commit was `a6b04aca29d374f4b686d2cf49702aa9a95d456a` (`test(grid): bind unsupported mount receipts to actual Qt runtime`). Its pull-request Actions run `38550633487` passed, including all selected Qt bindings, Tkinter, Kivy, Headless, core, impact-router tests, public-behavior aggregate, and mandatory CI conclusion. Other commit checks (commit subject, package boundaries, Flex certification) also passed.

- Actions: https://github.com/Neuri-AI/PSX/actions/runs/38550633487
- Source commit: https://github.com/Neuri-AI/PSX/commit/a6b04aca29d374f4b686d2cf49702aa9a95d456a
- Public Grid/GridItem **scoped** census: `57/57 executed_pass`, `pending=0`, `complete=true` (aggregate job `115808108994`). The report binds to `00173edcf31287abc78bfeebed8cd4bb0c240bb2`, the **CI checkout SHA reported by the job**, which differs from the source commit. Do not conflate those SHAs; verify checkout/merge semantics before recording a formal immutable-SHA closure. The broader, historical global inventory is not equivalent to the scoped Grid/GridItem contract.

## Increment ledger

| Increment | Recorded state | Evidence / behavior | Follow-up |
| --- | --- | --- | --- |
| F4-G1-C1 | Previously reported CLOSED; re-check immutable evidence before relying on formal certification | Public `Grid` / `GridItem` declarations, registration, defaults, validation and fail-closed public contract. | Preserve API/child-policy behavior. |
| F4-G1-C2 | Previously reported CLOSED | Grid contract and gap/span/offset normalization; reported source SHA `445476ed48e2f00f1fac828729dc48c124ffedac`; scoped census `40/40` at that checkpoint. | Do not imply geometry is implemented. |
| F4-G1-C3 | Previously reported CLOSED | Pure responsive `GridItem` value resolution and inclusive width thresholds; code SHA `30071e6cd6f9e252bab1945cceb1f3b5f7d06f0a`, integration SHA `190c246227269022e9de0226f7b4f25280142f13`; scoped census `45/45` at that checkpoint. | Resolution is metadata-only, not native geometry or persistent settings. |
| F4-G1-C4 | **CLOSED; certified 2026-10-14** | Native unsupported Grid/GridItem mounts fail closed across Headless, four Qt bindings, Tkinter and Kivy; Kivy driver verifies no native widget allocation, Qt/Tk tests assert no new widgets. Scoped census **59/59 executed_pass, pending=0** on CI checkout SHA `84b5eef90c6828d55dfea72ed88aef557f38b887`, source code SHA `b842f20e49d1a221f478ca52a693a6a36031002c`. Re-run Actions `38551782482` (attempt 2): all selected functional jobs, aggregate and required CI conclusion SUCCESS. | Proceed to remaining G1 global breakpoint settings integration; do not claim G1 CLOSED or native Grid geometry support. |

Historical checkpoint SHAs/counts are recorded to help locate evidence; **they are not a substitute for rerunning or validating the current required gates**. If the branch changes, supersede the reviewed SHA/run rather than silently relabeling old results as current.

## Recent CI failure and correction history

1. Native Qt/Tkinter tests originally asserted a diagnostic containing **Cinnamon**. The runtime correctly used **SFLE**, the current internal name. The tests and technical messages were aligned to SFLE; Cinnamon remains the commercial name only. No broad renaming of `psx.sfle` is authorized.
2. The next CI run passed functional backend jobs but the census aggregator rejected duplicate `qt_fail_closed` receipts shared across four Qt bindings.
3. The census inventory and Qt test receipts were separated into `pyside6_fail_closed`, `pyside2_fail_closed`, `pyqt5_fail_closed` and `pyqt6_fail_closed`. Run `38550633487` passed the public-behavior aggregate and mandatory conclusion.

## Non-negotiable work and closure policy

Every **new F4 capability** must include, in the same increment:

1. **Specific functional tests** of the new behavior, including negative cases and actual native readback/side-effect checks where applicable.
2. **CI impact routing** in `scripts/ci/impact.py` and corresponding `tests/test_ci_impact.py` regressions; verify selected jobs actually run. Docs-only diffs must select **zero product tests**.
3. **Executed public behavior census cases and receipts** when adding public props, events, methods or interactions; each backend/binding must produce distinct, truthful evidence. No fabricated PASS or reusing a receipt.

For every closure: review code and contracts; run targeted tests; fix root causes, not assertions that conceal defects; confirm all required Actions SUCCESS on the intended immutable source/checkout; confirm scoped receipts and applicability; record SHA, workflow, coverage, known exclusions and next increment **here**. A workflow that merely starts or passes only some jobs is not CLOSED.

## G1 closure audit — 2026-10-14 (NOT CLOSED)

The last reviewed native-layout run `38550633487` is **SUCCESS** for all required selected jobs, and its Grid/GridItem scoped contract certificate reports **57/57 executed, zero pending**. These facts are necessary but insufficient for declaring the full G1 contract complete.

**Concrete gaps found in repository code and tests:**

- **Application settings integration is absent from the reviewed Grid implementation.** `psx/core/grid_contract.py` provides `validate_grid_breakpoints(...)` and `resolve_grid_item_props(..., breakpoints=GRID_BREAKPOINTS)` with a caller-supplied table, but no actual application settings field or configuration-to-resolution wiring is demonstrated. The approved contract explicitly requires globally customizable breakpoints in settings and says their schema must be documented before shipping G1. This is a G1 acceptance blocker, not G2 geometry.
- **Kivy-specific negative coverage is missing.** The renderer contains a fail-closed guard in `psx/renderers/kivy/kivy.py::_adapter_create` for Grid/GridItem, but `tests/test_kivy_public_behavior.py` and `tests/certification/kivy_public_behavior_driver.py` contain no Grid test/receipt, and `tests/certification/public_behavior_census.py` has no `kivy_fail_closed` inventory row. The current 57/57 certificate therefore **does not cover Kivy Grid mounting**.
- **Native no-side-effect assertion is not proven by the existing Qt/Tk Grid tests.** Their `test_grid_mount_fails_before_native_widget_creation` cases assert that an exception is raised and emit a receipt, but do not directly assert that no widget was created or attached. Review all renderers and add meaningful pre/post state assertions where applicable.
- **CI checkout SHA differs from source SHA.** The successful aggregate uses `00173edcf31287abc78bfeebed8cd4bb0c240bb2` while the reviewed source commit was `a6b04aca29d374f4b686d2cf49702aa9a95d456a`. Verify the PR merge checkout and retain both identities in the formal certificate; do not substitute one for the other.

**Updated disposition (2026-10-14):** C4 and application settings integration have since been certified (see sections below); **G1 is CLOSED**. Earlier findings are retained as historical audit context. The documentation-only audit commit must not trigger product test suites.

## C4 remediation certified — 2026-10-14 (CLOSED)

Code SHA `b842f20e49d1a221f478ca52a693a6a36031002c` adds a Kivy native negative-mount driver and contract census receipts (`kivy_fail_closed` for both Grid and GridItem), plus native widget allocation assertions in Qt and Tk tests. The Kivy driver checks no Kivy Widget constructor runs during rejection. Existing impact routing already selects Kivy for changes to `tests/test_kivy_public_behavior.py` and the shared census and Qt/Tk tests select their respective jobs; confirm actual selection and run success before closure.

**Final evidence:** re-ran cancelled code workflow `38551782482` (attempt 2) without modifying the certified source. All selected native jobs (Kivy, Qt all four bindings, Tkinter, Headless), core, router, public behavior aggregate, and mandatory conclusion completed SUCCESS. Scoped Grid/GridItem certificate: **59/59 executed_pass, pending=0, complete=true**, checkout SHA `84b5eef90c6828d55dfea72ed88aef557f38b887`. Source commit: `b842f20e49d1a221f478ca52a693a6a36031002c`. Evidence: https://github.com/Neuri-AI/PSX/actions/runs/38551782482/attempts/2 and aggregate job `115813083147`. The later documentation-only commit had a successful workflow with skipped product jobs; that run is **not** used as C4 evidence. Global settings integration remains a separate G1 acceptance gap.

## G1 settings integration and final acceptance — CERTIFIED CLOSED (2026-10-14)

Application-level `App(..., settings={"grid": {"breakpoints": ...}})` is implemented in `psx/app.py` with immutable validated thresholds and `app.resolve_grid_item_props(...)` for G1 metadata resolution. The schema is frozen in `responsive-grid-contract.md`. The implementation does not claim native Grid geometry or automatic runtime resize; those are later gates. Added behavioral receipts for default/custom settings, invalid rejection and isolation in `tests/test_grid_contract.py`, census inventory entries in `tests/certification/public_behavior_census.py`, explicit routing in `scripts/ci/impact.py` and routing regressions in `tests/test_ci_impact.py`.

**Final acceptance:** source code SHA `1d0c246c69e218fb18debb35caa460f4488ea440`; PR CI checkout SHA `c63a67827914c92b6969412fb01926fcc01670c9`. Actions run `38552980373` completed successfully with selected native Qt (four bindings), Kivy, Tkinter, Headless, core, router, public behavior aggregate and required conclusion all **SUCCESS**. Grid/GridItem scoped certificate **62/62 executed_pass, 0 pending, complete=true**, aggregate job `115816083677`. Evidence: https://github.com/Neuri-AI/PSX/actions/runs/38552980373 . This current code-SHA contract certificate supersedes the historical C1–C3 checkpoint counts for G1 closure. Scope is metadata contracts, responsive resolution, per-application settings, explicit native unsupported rejection; native Grid geometry, automatic runtime resize and nesting remain G2–G4 work.

## Immediate next actions for the incoming agent

1. Preserve G1's certified code SHA `1d0c246c69e218fb18debb35caa460f4488ea440` and checkout SHA `c63a67827914c92b6969412fb01926fcc01670c9`; subsequent documentation commits are not retests.
2. Begin G2 with a machine-testable row-packing fixture format and freeze mixed auto/explicit grouping and overflow/projection semantics from the approved contract.
3. Implement Rust-primary and Python-fallback Grid mathematics with deterministic fixtures, differential certification and CI impact routes; do not claim native Grid mounting before G3.

**Roadmap boundary:** G1 public contract and normalization → G2 SFLE/Cinnamon Grid mathematics → G3 native integration → G4 responsive/nested runtime → G5 adversarial verification → G6 final certification. `Grid` is not yet a supported native geometry container merely because fail-closed checks pass.

## Current G2 increment: fixed-point overflow hardening

Implemented strict Rust/Python rejection of nonrepresentable widths, gaps, heights, and accumulated vertical extents. Added focused regression tests. Product CI is still running; do not mark this increment certified before the immutable code-SHA workflow completes. G2 remains open for min/max constraint policy and engine integration.

### Boundary correction and CI routing (2026-10-14)

Added executable Rust/Python shared fixtures at the exact signed `LayoutUnit` maximum (`2_147_483_647` raw), one quantum above it, impossible gap, exact maximum height, overflowing row gap and accumulated vertical extents. Fixed the missing `tests/fixtures/grid_pixel_projection.json` route in `scripts/ci/impact.py` and its routing test, so fixture-only modifications select both `sfle` and `rust`. Earlier docs-only green runs and cancelled code runs are **not** certification. This hardening increment remains **PENDING CI** until the latest code-bearing SHA has a completed mandatory run with Rust, Python and the relevant fixture tests actually executed. G2 overall remains IN PROGRESS.

### Fixed-point overflow hardening — CERTIFIED CLOSED (2026-10-14)

Immutable source SHA `47c03b587b1d653de3ff5c7275392fe160a9cb10` was certified by [required Actions run 38557432403](https://github.com/Neuri-AI/PSX/actions/runs/38557432403): **20/20 jobs SUCCESS**, including executable Rust Cargo + Python differential and Grid fixture tests (**307 passed** in the Rust/Python job), SFLE geometry (**639 passed**), CI change-router regression, native matrices, public behavior evidence aggregate and mandatory conclusion. Grid/GridItem scoped public census: **62/62 executed_pass; 0 pending**, PR checkout SHA `4fb1931b0e97de8708e7553ce7b88b6e2756ee4e` (not the source SHA). Shared fixtures cover exact signed `LayoutUnit` maximum, one-quantum overflow, row-gap/height limits, and cumulative vertical overflow. `scripts/ci/impact.py` now explicitly routes both shared Grid fixture files to Rust and SFLE; routing test executed. This certifies the **overflow hardening increment only**, not G2 overall, native Grid mounting, or engine integration. G2 remains IN PROGRESS pending min/max constraints, full engine integration and final adversarial parity audit.

## G2 min/max and pure Cinnamon engine entry points — awaiting certification

Implemented Rust/Python `compute_grid` math with resolved per-item min/max constraints, immutable allocated Grid rectangles, independently constrained used sizes, and explicit x/y overflow. Added shared fixture `tests/fixtures/grid_constraints.json`, Rust/Python fixture tests, `PythonLayoutEngine.compute_grid`, Rust PyO3 `compute_grid_json` binding, and `scripts/ci/impact.py` + router test. Native measurement/commit remains G3 and automatic snapshot Grid dispatch is not yet enabled. **Do not close G2 until source SHA CI confirms executable Rust/Python parity, and clarify that the Python engine entry point is not native Grid mounting.**

## G2 mathematical Grid solver — CERTIFIED CLOSED (2026-10-14)

**Certified immutable source SHA:** `8d772362208fbdd90cfb252859e49799ced1eb93`. **Actions:** https://github.com/Neuri-AI/PSX/actions/runs/38558618201 — all **20/20 required jobs SUCCESS**, including Rust/Python differential and Grid fixtures (**319 Python tests passed**), SFLE geometry (**651 passed**), Rust kernel tests, native wheel/fallback matrix, CI impact router, public census aggregate and mandatory conclusion. **Grid/GridItem public contract census:** 62/62 executed, pending 0; aggregate checkout SHA `89b319092ae82e5f3352712eaa8b4e851f648109` (distinct from source SHA). The existing public census is applicable unchanged: no new public Grid properties, events, methods or interactions were introduced by this internal solver increment.

**Completed G2 scope:** 12-column logical packing, auto/explicit spans, offsets and stable ordering; fixed-point pixel projection and gutters; RTL and row cross-axis placement; overflow rejection at signed LayoutUnit boundaries; resolved min/max used sizes with explicit overflow flags; shared Rust/Python constraint fixtures; pure Cinnamon mathematical entry point through `PythonLayoutEngine.compute_grid` and Rust `grid_math::compute_grid`/PyO3 `compute_grid_json`. Bounds never silently reflow spans or move adjacent allocations.

**Strict boundary:** this is a mathematical solver certification. Automatic dispatch from the general `LayoutInput` snapshot, native measurement, mounting, widget geometry readback, lifecycle and public Grid rendering are **not** claimed or certified; they must be completed in **G3**, followed by G4 responsive/nested runtime. G1 and G2 are closed; G3 is the next gate. Do not interpret green generic native regression jobs as proof of Grid native rendering.


## G3 — native renderer integration (stacked work branch)

**Branch:** `feature/grid-native-renderer-integration`, stacked on certified G2 `feature/grid-mathematical-solver`. Keep G1/G2 immutable until their PRs land in order.

### Native geometry preflight — implementation awaiting CI

Added `psx/sfle/grid_native_plan.py` to convert the existing Cinnamon constrained rectangles into an immutable native placement batch. It checks stable child identities, measured/mounted membership, duplicate and missing items, stale generation, signed fixed-point range and consistency of overflow receipts **before** any toolkit mutation. It preserves allocated sibling rectangles and separately records min/max-constrained used sizes; no native commit is performed by this module. The empty Grid case is supported.

Functional tests: `tests/sfle/test_grid_native_plan.py` covers placement, RTL, min-size overflow, identity mismatch, stale generations, duplicate and forged geometry. `scripts/ci/impact.py` routes the new production module and tests to SFLE, core, Headless, Qt, Kivy and Tkinter; `tests/test_ci_impact.py` asserts that route.

**Not yet supported:** actual Grid/GridItem widget mounting, real toolkit measurement, native placement/readback, lifecycle updates or public geometry receipts. Existing fail-closed Grid mounting guards remain in place until each renderer has end-to-end certified integration. No new public props/events/methods/interactions in this internal increment, so the G1 public census is unchanged. G3 is IN PROGRESS.

### G3 preflight audit correction

The placement batch now retains **both** the allocated border-box width/height and the min/max-constrained used width/height, as well as overflow flags. Native adapters must use the allocated origin for stable sibling placement while explicitly deciding and certifying the actual used widget dimensions, including clipping/overflow policy. Regression tests cover min and max constraints and fractional fixed-point coordinates. **This is not yet a native geometry commit or readback certification.**

### CI execution caveat for stacked G3 PR

The selective native layout workflow currently listens only to pull requests targeting `develop`, whereas G3 PR #18 targets the G2 feature branch. A successful `Runtime package boundaries` check on this stacked PR is **not** evidence that the SFLE/native geometry tests ran. G3 preflight remains uncertified until the relevant functional suite runs against an immutable source SHA. Do not change the workflow target filters merely to make an individual stacked PR green; run the existing required workflow explicitly or certify after the prerequisite PRs are merged.


### F4-G3-C1 — CERTIFIED CLOSED (2026-10-14)

**Immutable source SHA:** `3272b658d8760aeae498a3bd0659d3ec35c048e9`. **Required CI:** https://github.com/Neuri-AI/PSX/actions/runs/38560456678, triggered by the temporary certification-only PR #19 targeting `develop` because the production stacked PR #18 targets the G2 branch. **Outcome: SUCCESS; 15 jobs succeeded and 3 intentionally skipped by the change-impact router** (native wheel, Chromium oracle, Rust/Python differential; the G3 Python preflight does not modify those contracts). The executed jobs included SFLE geometry **668 passed**, router regression **36 passed**, core, Qt, Kivy, Tkinter, Headless, Qt-family parity, native public behavior aggregate and mandatory conclusion. **Public Grid/GridItem scoped census: 62/62 executed_pass, 0 pending**, aggregate checkout SHA `0d38474b1bdee4f421b6be0fd8c190f2fd5b8a41` (distinct from source SHA). Commit subject and package boundaries also succeeded.

**Certified scope:** immutable renderer-neutral geometry placement batch, stable identity and measured/mounted set validation, stale-generation rejection, signed LayoutUnit range and rectangle edge validation, preservation of allocated and min/max used dimensions, overflow receipt validation, RTL and fractional pixel precision, fail-closed malformed inputs, functional regression tests and CI impact routing. This closes **C1 only**. **Not certified:** native widget mounting, native measurement, layout tree dispatch, geometry commit/readback or lifecycle. Those remain C2–C6; do not remove the public Grid mount guards based on C1.

## F4-G3-C2 — normalized tree and native measurement handoff (IN PROGRESS)

Added `psx/sfle/grid_tree_measurement.py`: converts a normalized `Grid` with direct `GridItem` participants into stable key-aware Cinnamon `GridSlot` identities; resolves responsive spans/offsets at the definite Grid **content width**; requires real `MeasuredBox` records from native measurement ports with complete identities, explicit width constraints and revision receipts; consumes preferred intrinsic heights without guessing dimensions; computes constrained Grid rectangles and passes them through the certified C1 native preflight. This is an immutable handoff, **not** native widget measurement, mounting or commit. Functional tests cover breakpoints, keyed identity, measurement revisions, vertical reflow, min overflow, missing/duplicate/foreign measurements and stale generations. `scripts/ci/impact.py` routes this module and tests to core/SFLE/native backend suites. C2 is pending executable CI certification and audit of the measurement integration boundary.

### C2 normalized-tree/MeasuredBox handoff — CERTIFIED SUBINCREMENT (2026-10-14)

Immutable source SHA `9774e668839ece79c4014a4c4d22b0ac83665fc1`; [Actions run 38561071718](https://github.com/Neuri-AI/PSX/actions/runs/38561071718) **SUCCESS** (15 executed jobs SUCCESS, 3 correctly skipped by impact selection), including SFLE geometry **679 passed**, native Qt/Kivy/Tkinter/Headless regression, router, core, aggregate and mandatory conclusion. Grid/GridItem scoped public census **62/62 executed_pass, 0 pending**; aggregate checkout SHA `085abb20a555c25da6cb459b685bfeb041cd2a88` (distinct from immutable source SHA). No new public Grid contract surface.

**C2 remains IN PROGRESS**: the certified module consumes native `MeasuredBox` receipts supplied by a caller, but no renderer has yet been wired to gather and deliver its real widget measurements for GridItems automatically. Do not claim that C2 native measurement collection is complete or that Grid is mountable. The next increment must connect the existing measurement ports/lifecycle to the handoff, then prove real widget measurement and invalidation on Qt/Kivy/Tkinter/Headless.


### F4-G3-C2 — CERTIFIED CLOSED (2026-10-14)

**Immutable certified source SHA:** `21595fce593a432c1e4a03bca44cd302134e35a7`. **Required native CI:** https://github.com/Neuri-AI/PSX/actions/runs/38562176548 — **SUCCESS** (15 executed jobs passed; 3 correctly skipped by the impact router). SFLE geometry **689 passed, 2 skipped**; real Qt native source, real Tk widget requested sizes, real Kivy Label texture metrics, and explicit Headless VNode intrinsic callback were exercised in their corresponding native jobs. Native Qt, Tkinter, Kivy, Headless, core, impact router, Qt parity, scoped public census and mandatory conclusion all succeeded. Grid/GridItem scoped census **62/62 executed_pass, 0 pending**, aggregate checkout SHA `274b3a9375475c12fd8d642e3884326ad2b31f21` (distinct from certified source SHA). Commit subject clarity and runtime package boundaries succeeded.

**Implemented:** `psx/sfle/grid_native_measurement.py` composes stable normalized GridItem identities, responsive span resolution at Grid content width, Cinnamon horizontal allocation, per-leaf *actual* width-aware native measurement through existing `QtMeasurementSource`, `TkMeasurementSource`, `KivyMeasurementSource` ports and explicit `HeadlessGridMeasurementSource`, atomic UI-thread/generation-checked measurement acceptance, and constrained Cinnamon Grid calculation plus C1 preflight. Functional tests include responsive width-driven height changes, revision receipts, stale/incomplete/foreign inputs, off-owner-thread rejection, missing intrinsic metrics, and actual native widget reads. `scripts/ci/impact.py` and its regression tests route changes to the relevant native jobs; those jobs execute the new tests.

**Scope boundary:** C2 certifies native intrinsic measurement of already mounted **single-leaf** GridItem contents and the renderer-neutral handoff, not creating or mounting Grid/GridItem, not native geometry commit/readback, not composite GridItem intrinsic measurement, and not automatic renderer lifecycle wiring. The existing fail-closed Grid mount guards remain. These belong to C3 and subsequent integration gates; C2 closure must never be cited as proof that Grid is usable in native applications.


### F4-G3-C3 — native geometry transaction and mounted Headless subincrement CERTIFIED; C3 OPEN

**Certified source SHA:** `eaf88e90f37f0230de27009c109eddb5e4caf00c`. **Required native CI:** https://github.com/Neuri-AI/PSX/actions/runs/38564109494 — **SUCCESS** (all 18 jobs completed without failure; native impact skips are intentional). Public Grid/GridItem contract scoped census **62/62 executed, 0 pending**, aggregate checkout SHA `c0cae74b129e12027b6091b519f449e169513869` (not the source SHA).

**Native geometry:** `psx/sfle/grid_native_commit.py` implements actual Qt/Tk/Kivy/Headless widget rectangle writes, toolkit readback with bounded tolerance, full-batch identity and generation preflight, owner-thread checks, Kivy bottom-left coordinate conversion, and best-effort rollback (including initially unplaced Tk and uninitialized Headless widgets). The native backend CI jobs execute actual widget geometry tests. This port **does not** by itself make Grid mountable on Qt, Tk or Kivy.

**Mounted Headless root:** `psx/sfle/headless_grid_bridge.py` connects a reconciled top-level Grid with direct GridItem wrappers containing one native leaf each to width-aware intrinsic measurements, Cinnamon responsive row packing, stable keyed IDs, allocated/used rectangle placement, atomic native commit/readback, viewport resize, keyed reorder and teardown. Fail-closed guards reject missing SFLE viewport, standalone GridItem, unsupported nested Grid, composite GridItem, stale generation and unsupported measurements. `HeadlessRenderer.grid_result` stores the successful receipt; no toolkit fallback layout is used. `tests/test_headless_grid_native_layout.py` executes these behaviors; `scripts/ci/impact.py` and the native Headless job select them. The public census adds explicitly scoped `partial_native` Headless mount/readback/reflow/reorder/teardown receipts without claiming the full backend matrix is ported.

**C3 remains OPEN:** Qt, Tkinter and Kivy renderer adapters still reject Grid/GridItem creation; their layout-tree dispatch and reconciled native parentage, updates, readback and teardown must be implemented and independently tested. Headless support is root-only and single-leaf; composite/nested layout and general Flex/Scroll composition are outside this subincrement. Do not mark C3 closed or claim general portable Grid support based on the successful native geometry tests.


### C3 renderer-integration attempt — remains OPEN (2026-10-14)

Source integration SHA `6c61033baa09f0f7e83900a4960ad03237c0a842` was exercised by temporary certification PR #20 and required Actions run [38567094821](https://github.com/Neuri-AI/PSX/actions/runs/38567094821), whose selected jobs completed successfully. The change adds a renderer-neutral mounted native Grid bridge and replaces Qt/Tkinter/Kivy early Grid rejection with native wrapper parentage, Cinnamon width-aware measurement, transactional placement/readback and lifecycle dispatch; no QLayout, Tk grid/pack or Kivy GridLayout is used.

**This is not C3 closure evidence.** The currently selected Qt/Tkinter/Kivy workflow commands did not execute new mounted-Grid lifecycle scenarios (creation, parentage, geometry readback, keyed reconciliation/update and teardown) or corresponding public Grid/GridItem census receipts. Existing successful backend regressions therefore cannot certify those guarantees. C3 remains OPEN until those backend-specific executable tests, impact routes and truthful census cases are added and a new immutable-SHA run executes them.


### C3 Kivy nested coordinate correction — pending certification (2026-10-14)

Identified a concrete native Grid bug: Kivy child leaf coordinates were projected using the root viewport height instead of the immediate GridItem wrapper height. `grid_native_commit.py` now accepts an optional complete per-placement parent-height mapping and validates it before mutation; `native_grid_bridge.py` supplies root height for wrappers and their allocated height for child leaves. Added real Kivy regressions for nested coordinate readback and rejection of incomplete parent-height maps (`tests/sfle/test_grid_native_commit.py`). Latest code-bearing SHA at this checkpoint: `23ccb1534b169000d66d1142b06c12aa433228c3` (three successive code commits). This is **not yet an Actions certificate**. C3 stays **IN PROGRESS** until the code SHA passes native tests and mounted lifecycle + public census for Qt (all four bindings), Tk and Kivy is executed and certified. Do not infer native lifecycle coverage from `test_grid_native_commit.py` alone.


## F4-G3-C3 — CERTIFIED CLOSED (2026-10-14)

**Immutable source SHA:** `43bcf8bd49ceccf44d71cd0342a64a95d67bbf79`. **Required native-layout workflow:** https://github.com/Neuri-AI/PSX/actions/runs/38572675888 — completed **SUCCESS**, including the mandatory CI conclusion and public behavior evidence aggregation. The Actions PR-checkout/merge SHA recorded in the aggregate is `c5ff5b0e3324fd3280250fc28e022b9adc6ad22a`; do not conflate that with the source SHA.

**Executed census certificates on that checkout:** Grid/GridItem public contract **62/62 executed_pass, zero pending**; scoped native Grid/GridItem lifecycle **35/35 executed_pass, zero pending, complete=true**. Native scope includes **headless, kivy, pyqt5, pyqt6, pyside2, pyside6, tkinter**. The scoped-native certificate is an explicit required aggregate gate, not inferred from generic backend CI. The selected core, SFLE, change-router, Qt native/parity, Kivy, Tkinter, Headless, public-evidence aggregate and mandatory conclusion jobs passed. Chromium, Rust differential and native-wheel jobs were intentionally skipped by impact selection because their change domains were unaffected; this is not an assertion that those suites ran.

**C3 certified functionality:** mounted top-level `Grid` with direct `GridItem` wrappers containing one native leaf; widget creation, parentage, width-aware native intrinsic measurement, Cinnamon-only responsive allocation, atomic geometry projection/readback, resize/reflow, keyed reuse/reorder, and teardown. The Qt binding matrix runs each binding in an isolated process, including DPI validation. Tkinter and Kivy run real native widget assertions. Kivy leaf local Y projection uses each GridItem wrapper's immediate parent height, not the viewport height. Unconfigured SFLE layouts and unsupported standalone/nested Grid paths continue to fail closed. Native lifecycle receipts are asserted in executable JUnit and aggregated per binding. `scripts/ci/impact.py` and its selector regression select the mounted Grid functional tests for affected native backends.

**Scope explicitly NOT certified by C3:** nested Grid, arbitrary/composite GridItem content, embedding Grid within Flex/Scroll or other parent layouts, full automatic nested tree dispatch, and any G4 responsive/nested runtime guarantees. The prior OPEN subsections above remain historical audit checkpoints, superseded by this definitive CLOSED entry. **Proceed to F4-G3-C4 without reopening C3.**

## F4-G3-C4 — STARTED; implementation and certification PENDING (2026-10-14)

**Handoff baseline:** C3 closed at immutable source `43bcf8bd49ceccf44d71cd0342a64a95d67bbf79` and workflow `38572675888`. This is the starting reference, not an acceptance certificate for C4.

**Next integration audit target:** expand beyond the deliberately narrow C3 top-level, one-leaf Grid root while preserving Cinnamon/SFLE as the sole geometry authority. First inspect the tree, renderer and child-policy contracts to delineate which composition modes belong to G3 and which must be reserved for G4 responsive/nested runtime. Focus on unsupported Grid placement inside native layout containers, leaf/composite child ownership, measurement invalidation, geometry/readback and lifecycle under reconciliation. Any deliberately deferred composition case must fail closed with explicit executable evidence, never silently fall back to toolkit-managed layout.

**C4 acceptance policy:** (1) actual cross-backend functional assertions including native ownership, resize/update, teardown, error/rollback cases and readback; (2) `scripts/ci/impact.py` paths plus selector tests; (3) source-derived per-backend public behavior census rows with executed JUnit receipts for every newly enabled public interaction; (4) required GitHub Actions success and immutable source/checkout SHAs. **State: IN PROGRESS / NOT CERTIFIED**. Do not mark C4 or G3 CLOSED until these guarantees are implemented and verified.



## F4-G3-C4 — CERTIFIED CLOSED (2026-10-14)

**Immutable source SHA:** `e6a61c68aae02bf2a92699bcf69589b5f7a48f4e`. **Required CI:** https://github.com/Neuri-AI/PSX/actions/runs/38574473294 — completed **SUCCESS**, including the final mandatory conclusion and public-evidence aggregate. **PR checkout/merge SHA in the aggregate:** `f103f4ba82ee075e4e9f55c48e5ade0873f02949` (distinct from source SHA). No subsequent documentation-only run substitutes for this code certificate.

**Executed evidence:** Grid/GridItem public contract **62/62 executed_pass, pending=0**; scoped native Grid/GridItem **47/47 executed_pass, pending=0, complete=true**, over Headless, Tkinter, Kivy and Qt PySide6/PySide2/PyQt5/PyQt6. The 12 additional native scenarios (six rollback and six unsupported-nesting checks) were executed in the actual Qt/Tk/Kivy JUnit jobs and are required in the source-derived census; Headless's existing five native cases remain certified. Core registry, SFLE geometry, selective impact router, Qt native + four binding parity, Tkinter, Kivy, Headless, public aggregate and mandatory conclusion all passed. Rust differential, Chromium and native wheel runs were correctly excluded by the impact router; they did **not** execute on this SHA.

**Completed C4 hardening and acceptance boundary:** the shared native Grid bridge now treats the root host geometry as part of the same failure/rollback boundary as the child item batch. It snapshots the real Qt/Tk/Kivy root rectangle/placement before mutation, restores the root on native transaction failure, preserves the initially unplaced Tk state and propagates the failure without claiming success. Tests inject a failed child batch after entry into the real native renderer lifecycle, assert actual host/item readback equals the transaction-entry snapshot and verify a subsequent successful reflow. C4 also certifies that attempting to mount Grid under Flex fails closed instead of silently deferring geometry to a toolkit layout manager. That intentionally unsupported composition emits binding-specific negative JUnit receipts. Existing C3 mount/reorder/resize/teardown evidence is preserved. The production `psx/sfle/native_grid_bridge.py` is already explicitly routed through `scripts/ci/impact.py`; the native lifecycle test module is also routed to all affected backends with selector regressions.

**Strict scope:** this is the **C4 transaction-safety, error-recovery and unsupported-composition audit increment**, not implementation or certification of nested Grid, composite GridItem children, or arbitrary Flex/Scroll embedding. Those still fail closed and must not be announced as supported: the general nested responsive/runtime integration belongs to G4. C4 does not authorize alternative toolkit layout engines. The earlier C4 IN PROGRESS checkpoint above is historical and superseded by this CLOSED entry. **G3 as a whole remains IN PROGRESS**, pending its remaining acceptance increments.

## F4-G3-C5 — NEXT / NOT STARTED

Inspect the actual current G3 plan and existing layout coordinator before broadening native tree dispatch. Preserve the immutable C3/C4 acceptance SHAs. Build the next defined capability with native behavior tests, `scripts/ci/impact.py` routing/selector regression, executed public behavior receipts for newly supported interactions, and an immutable-SHA required CI certificate. Do not silently promote G4 nested/composite runtime work into G3 or claim the full Grid tree is generally supported.


## F4-G3-C5 — CERTIFIED CLOSED (2026-10-14)

**Immutable code/test source SHA:** `5d27ea3f65948b394d62f3fef1edad3c819b5d7f`. **Required GitHub Actions:** https://github.com/Neuri-AI/PSX/actions/runs/38577514935 — all selected required jobs and mandatory conclusion **SUCCESS**, including core, SFLE, Qt all four bindings, Tkinter, Kivy, Headless, impact router and public behavior aggregate. **PR merge-checkout SHA:** `a1d817f86c46a20b34963990582eff4e23796981` (do not confuse with immutable source SHA). Commit subject clarity and runtime package boundaries also concluded SUCCESS. Rust differential, Chromium oracle and native wheel were intentionally skipped by the change-impact classifier.

**Executed public evidence:** Grid/GridItem contract **62/62 executed_pass, 0 pending** and native Grid/GridItem scoped behavior **59/59 executed_pass, 0 pending, complete=true** over Headless, PySide6/PySide2/PyQt5/PyQt6, Tkinter and Kivy. C5 added **12 executed binding-specific receipts** on top of C4's 47/47: six component-boundary keyed update/readback scenarios and six composite GridItem fail-closed scenarios. JUnit evidence is bound to the workflow checkout SHA; no synthetic evidence was substituted.

**C5 scope and implementation finding:** audited the existing mounted Grid renderer bridge's handling of function component boundaries. The renderer-neutral normalizer already resolves component roots from the mounted reconciler; no production code changes were necessary to preserve that functionality. Added real native lifecycle cases with a function component returning the Grid root and another function component returning a GridItem leaf, verifying allocation, parentage, geometry, readback and reuse of the same real native leaf widget on keyed component property update. Verified a GridItem containing a single composite Flex host with multiple children fails closed during Cinnamon native measurement with `GridPackingError` rather than inventing composite intrinsic metrics or invoking a toolkit layout manager. The public census inventory and mandatory per-binding collector were expanded for these scenarios. `tests/test_mounted_grid_native_renderers.py` was already directly routed to the relevant Qt, Tkinter and Kivy CI jobs by `scripts/ci/impact.py` with a selector regression; verified actual execution, including the native public JUnit collection jobs.

**Scope boundary:** component *wrapper* participation with exactly one native leaf is certified; composite GridItem measurement, nested Grid, and general Grid-under-Flex/Scroll remain outside G3-C5 and unsupported. This increment proves a pre-existing production code path with new executable acceptance tests and census entries; it does **not** claim to implement arbitrary composite layout or a new layout math engine. G3 remains IN PROGRESS pending final G3 gate(s); do not call the entire G3 closed based solely on C5.



## F4-G3-C6 — FINAL G3 INTEGRATION AUDIT; CERTIFIED CLOSED (2026-10-14)

**Final G3 verdict: CLOSED.** This is an acceptance audit of the completed native integration scope defined in `responsive-grid-contract.md` §5 (Qt/Kivy/Tkinter/Headless measurement, geometry commit/readback, reconciliation updates, disposal, explicit unsupported cells and component participation). It is NOT authorization for G4 composite/nested responsive composition, nor for G5-wide asynchronous robustness or G6 integral release certification.

**Immutable functional code/test baseline:** `5d27ea3f65948b394d62f3fef1edad3c819b5d7f`. The subsequent `c228fa516142fa37d385112821065cbfd2ecebc5` commit modifies this living documentation only; it does not alter the certified implementation. **Required G3 Actions run:** https://github.com/Neuri-AI/PSX/actions/runs/38577514935 **SUCCESS**. **PR merge-checkout SHA** `a1d817f86c46a20b34963990582eff4e23796981` is different from the actual source SHA, and the census correctly binds to the checkout SHA.

**Mandatory selected CI matrix inspected at final audit:** 15/15 selected jobs SUCCESS — diff impact classification; router regression; core/registry; native Qt components; native Tkinter; native Kivy; deterministic Headless; SFLE geometry; Qt SFLE parity for PyQt5, PyQt6, PySide2 and PySide6; G4 public API regression gate; public behavior evidence aggregate; mandatory required CI conclusion. Three impact-unrelated jobs were SKIPPED as designed: Chromium browser oracle, Rust/Python differential and native-wheel fallback. Do not claim those three were executed or counted as G3 successes. Commit-subject and runtime package-boundaries checks associated with the code SHA separately concluded SUCCESS.

**Executed acceptance receipts:** scoped public Grid/GridItem contract **62/62 executed_pass; pending=0; complete=true**; scoped native Grid/GridItem **59/59 executed_pass; pending=0; complete=true**, including Headless, Kivy, Tkinter and all four Qt bindings. Native evidence exercises mounted Grid root with direct GridItem wrapper and exactly one leaf: creation/parentage, real intrinsic measurement, Cinnamon-only allocation, toolkit geometry write and readback, responsive viewport resize/reflow, keyed reconciliation, component boundaries, lifecycle disposal, failed transaction rollback/recovery and explicit negative unsupported-composition cells. Native tests actually ran in their respective CI jobs; no inferred coverage from a generic green smoke job.

**Adversarial/unsupported disposition:** mounting Grid without definite SFLE viewport, standalone GridItem, nested Grid underneath Flex, and composite GridItem leaf trees must reject explicitly rather than let a toolkit-managed layout determine Grid geometry. The public child policy rejects multiple direct GridItem roots. The supported G3 native composition remains a root Grid with direct single-leaf GridItem children (transparently component-wrapped where certified). Nested Grid, composite intrinsic measurements, Grid inside Flex/Scroll, independent nested content-width breakpoints and generalized composition are G4. Expanded async invalidation/resource/DPI and broader post-composition adversarial regressions are G5; cross-project full-platform/Rust/Chromium certification is G6. No undocumented exception is being promoted into support.

**Completeness assessment:** every G3 gate item in the approved contract has either a corresponding actual executed native test/census certificate or a documented intentional unsupported cell. CI impact routing for production native bridge, geometry preflight/measurement and mounted renderer test module exists in `scripts/ci/impact.py`, is exercised by `tests/test_ci_impact.py` and selects the affected native jobs; docs-only changes should not run product tests. This final audit introduced no new production API/behavior or files requiring additional public census rows. Historical IN PROGRESS/NOT STARTED checkpoints in this document describe prior states and are superseded by this final closure.

**G3 CLOSED — proceed to F4-G4 — Responsive composition.** Start G4 with its own native and engine contracts, fixtures, impact mapping and evidence. Do not reopen certified C1–C6 without a real regression or explicitly approved scope change.


## F4-G4 — Responsive composition — IN PROGRESS (2026-10-14)

**Branch remains `feature/grid-native-renderer-integration`, production stacked PR #18. G3 C1–C6 immutable closures remain historical and unchanged.** G4's approved exit criteria in `responsive-grid-contract.md` §5 are *independent content-box breakpoints, nested Grid, Flex/Scroll interoperability, resize and state/identity retention, and no cyclic oscillation*. The work below certifies two subincrements; **it is NOT a complete G4 gate certificate**. Do not change the G4 state to CLOSED before Flex/Scroll and the full lifecycle acceptance matrix are demonstrated.

### Responsive native cycles — CERTIFIED CLOSED subincrement

Source SHA `c85b67b9c6e1ff00465b82e124cac2d9979a2247`. Required Actions https://github.com/Neuri-AI/PSX/actions/runs/38579922831 **SUCCESS**, including required conclusion and public aggregate. Public Grid/GridItem scoped contract **62/62 executed, 0 pending**; native scoped census **73/73 executed, 0 pending**, over Headless, Tkinter, Kivy and all four Qt bindings. Aggregate checkout SHA `0cbd1aefb4ba20216065ce03b96d171bf9e54ff9`, distinct from source SHA. Qt/Tk/Kivy and Headless executable tests repeatedly cross the root Grid breakpoint (800→767→800 or reverse), verify actual native geometry and preserve original GridItem and native leaf widget identities; no new production API was introduced. `scripts/ci/impact.py` already maps both mounted lifecycle test paths to the relevant native jobs, and the route selection was executed. This is root-container behavior, **not** evidence that all nested composition or automatic native-resize paths are implemented.

### Recursive nested Grid — CERTIFIED CLOSED subincrement

**Immutable source SHA:** `34b69a4bc1b832a015665c087e641a47d111faba`. **Required Actions:** https://github.com/Neuri-AI/PSX/actions/runs/38582148248 — required conclusion **SUCCESS**, scoped contract **62/62 executed, pending=0**, scoped native behavior **80/80 executed, pending=0, complete=true**, covering Headless, Kivy, Tkinter and Qt PySide2/PySide6/PyQt5/PyQt6. Native JUnit aggregate checkout SHA `a2f9f0be718a07b9bea9d87422e303abdaea3e02` is distinct from the branch source SHA. CI change router, SFLE geometry, core, all native toolkit/binding jobs, public aggregate and mandatory conclusion passed; Rust/Python differential, Chromium oracle and native wheel tasks were impact-skipped, **not** executed.

**What is actually implemented:** `psx/sfle/grid_native_composition.py` computes a recursive hierarchy of explicit Grid hosts nested as the single content root of a GridItem, measuring only real terminal native leaves on the owning thread, resolving each GridItem breakpoint against *that Grid's own Cinnamon-allocated content width*, and producing one immutable flattened batch of native-parent-local rectangles. It uses the existing Cinnamon `measure_grid_native` / `prepare_grid_measurement` / `compute_grid` mathematics; toolkit adapters only create native parent/child widgets, read leaf metrics and apply/read back calculated rectangles. Recursive content heights are obtained from the inner Cinnamon placements, not guessed from QGridLayout, Tk grid or Kivy GridLayout. `psx/sfle/native_grid_bridge.py` integrates the composition on Qt/Tk/Kivy, `psx/sfle/headless_grid_bridge.py` integrates it on Headless, `psx/sfle/grid_native_measurement.py` accepts explicit nested-Grid measurement only when requested by this coordinator, and the four renderer adapters allow Grid under an immediate GridItem without opening unrelated container composition. Existing single-level C3 behavior retains its original tested path.

**Executed acceptance:** mounted nested Grid with outer width 398px at 800px viewport and local inner width 398px (below md) reflows at 1600px viewport to outer width 798px and inner children width 397px (at/above md), then returns to original geometry without native leaf remount, with <=1px native readback for toolkit backends and exact Headless readback. Tests execute on all seven runtime families. Native public inventory has seven distinct `nested_content_width/independent_breakpoint_reflow` receipts. `scripts/ci/impact.py` directly routes the new production composition module to core/SFLE/Headless/Qt/Tkinter/Kivy and its regression selector test verifies selection. No generic toolkit sibling layout manager was introduced.

**Still required to close G4 (blocking):**
1. **Flex/Grid interoperability:** the canonical Flex/SFLE snapshot and native bridges still do not accept and measure a Grid as an atomic responsive descendant of an SFLE Flex tree; unsupported cells must stay fail-closed until real width-dependent intrinsic measurements, transaction-safe native commit and readback are implemented and executed in all applicable backends.
2. **Scroll/Grid interoperability:** Scroll's explicit Flex content and viewport/offset/clip authority must remain intact while nested Grid children reflow; prove real scrolling input/offset preservation and no competing native layout manager. This is not completed by Grid-within-Grid nesting.
3. **Full compositional lifecycle / circularity audit:** certify component state, focus/identity, keyed moves, repeated native resize (including source-triggered resize), nested-content resource invalidation, no breakpoint oscillation in coupled definite/auto constraints, rollback and teardown across mixed layout trees. The simple deterministic crossing tests are not substitutes for this matrix.
4. **Final G4 immutable-SHA acceptance:** execute the affected-backend behavioral scenarios and scoped public receipts on one code SHA, then require successful aggregate and mandatory conclusion. Do not borrow this nested-only 80/80 certificate as proof that unimplemented Flex/Scroll interactions were tested.

**Recommended next implementation boundary:** extend `prepare_native_layout_snapshot` to treat a Grid subtree as a single container-sized Flex leaf with genuine Cinnamon height-for-width measurement and stable `path_identity`; then integrate its child layout into the existing Qt/Tk/Kivy/Headless transaction and rollback/readback, preserving Scroll ownership. Do not silently suppress descendants or delegate Grid sizing to native layout managers. Add every new operation to source-derived per-backend census and impact routing in the same increment.

**G4 status: IN PROGRESS, not CLOSED.** The two above subincrements are independently certified. Work on Flex/Scroll and mixed-tree lifecycle remains necessary for contract-compliant closure.


### Application-configured per-container breakpoints — CERTIFIED CLOSED subincrement (2026-10-14)

**Immutable source SHA** `a18c339b62ded6fa289a551209dae39a31656bbb`. **Required Actions:** https://github.com/Neuri-AI/PSX/actions/runs/38583505504 — all selected required jobs, public evidence aggregate and mandatory conclusion **SUCCESS**. Scoped public Grid/GridItem contract **62/62 executed_pass, pending=0**, native Grid/GridItem **87/87 executed_pass, pending=0, complete=true**, over all seven Headless/Tkinter/Kivy/Qt-binding runtime families. PR merge-checkout SHA `e0efd9275e56b0456944aeb5a4c76ae1810ecc0f` is distinct from source SHA. Three unaffected optional validation domains (Rust differential, Chromium, native wheels) were intentionally impact-skipped; they are not counted as executed.

**Runtime integration fix:** G1 previously exposed immutable `App.settings.grid.breakpoints`, but native Grid/measurement functions still used the hard-coded defaults. `App` now passes its validated, immutable per-application threshold map to SFLE-capable renderers, `measure_grid_native` and `prepare_grid_measurement` use that map for both preliminary row widths and final constrained geometry, and `prepare_composed_grid` forwards it through every nested Grid while resolving against each Grid's *own* available content width. No global mutable breakpoint table or alternate renderer layout authority was introduced.

**Real executed evidence:** with a custom md=350px setting at an 800px viewport, an outer Grid allocates 398px to an item while the nested Grid resolves md independently and splits its two inner leaves into 197px widths; at 600px viewport, the outer Grid still splits into 298px items, but the nested Grid correctly stacks its leaves because *its own* 298px content box falls below md. Qt all bindings, Tkinter, Kivy and Headless tests assert native geometry/readback and stable widget identity. Seven new `configured_container_breakpoints/isolated_nested_resolution` scoped-native receipts were executed and aggregated. App settings validation remains the G1 public contract; this increment certifies the previously missing native runtime wiring, not a new public prop.

**G4 remains IN PROGRESS.** The next contract-required cells are general Grid/Flex/Scroll composition (including scroll clipping/offset ownership) and full mixed-tree resize, state/focus, disposal, width-height cycle and rollback tests on a future immutable SHA. Neither the successful 87/87 nested-only census nor all-green selected jobs establish those missing behaviors. Do not mark the overall gate CLOSED.
