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
