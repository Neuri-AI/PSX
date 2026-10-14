# Responsive Grid — implementation and certification progress

> **Living agent handoff.** Update this file in GitHub whenever an increment changes state, and **in the same work cycle as implementation, tests, impact routing and census receipts**. This is an internal F4/G1 planning record; never use stage codes as opaque names for production files, functions, or tests.
>
> Last evidence review: 2026-10-14. Working branch: `feature/responsive-grid-public-contract`; draft PR #16 to `develop`. The SHA and workflow results below describe **the reviewed execution**, not a promise that the branch has not advanced. Always inspect current HEAD and PR checks first.

## Where to resume

**F4 / G1 / C4 — CLOSED (certified native fail-closed contract). G1 overall remains IN PROGRESS pending global settings integration.** Do **not** restart G1 at its first increment and do **not** begin G2 until G1 acceptance is explicitly certified.

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

**Updated disposition (2026-10-14):** C4 native negative evidence has since been completed and certified (see section below). F4-G1 overall remains **IN PROGRESS** because global settings integration is still missing. The earlier findings in this historical audit are retained for traceability. The documentation-only audit commit must not trigger product test suites.

## C4 remediation certified — 2026-10-14 (CLOSED)

Code SHA `b842f20e49d1a221f478ca52a693a6a36031002c` adds a Kivy native negative-mount driver and contract census receipts (`kivy_fail_closed` for both Grid and GridItem), plus native widget allocation assertions in Qt and Tk tests. The Kivy driver checks no Kivy Widget constructor runs during rejection. Existing impact routing already selects Kivy for changes to `tests/test_kivy_public_behavior.py` and the shared census and Qt/Tk tests select their respective jobs; confirm actual selection and run success before closure.

**Final evidence:** re-ran cancelled code workflow `38551782482` (attempt 2) without modifying the certified source. All selected native jobs (Kivy, Qt all four bindings, Tkinter, Headless), core, router, public behavior aggregate, and mandatory conclusion completed SUCCESS. Scoped Grid/GridItem certificate: **59/59 executed_pass, pending=0, complete=true**, checkout SHA `84b5eef90c6828d55dfea72ed88aef557f38b887`. Source commit: `b842f20e49d1a221f478ca52a693a6a36031002c`. Evidence: https://github.com/Neuri-AI/PSX/actions/runs/38551782482/attempts/2 and aggregate job `115813083147`. The later documentation-only commit had a successful workflow with skipped product jobs; that run is **not** used as C4 evidence. Global settings integration remains a separate G1 acceptance gap.

## Immediate next actions for the incoming agent

1. Inspect current branch HEAD, PR #16, latest Actions and the approved contract. Preserve C4's certified source/checkout SHA distinction.
2. Implement and certify application-wide customizable Grid breakpoint settings and wiring to responsive resolution, with focused tests, CI impact routing and public census receipts as applicable.
3. Audit all remaining G1 acceptance items and certify G1 on a new immutable SHA before starting G2 mathematical Grid geometry.

**Roadmap boundary:** G1 public contract and normalization → G2 SFLE/Cinnamon Grid mathematics → G3 native integration → G4 responsive/nested runtime → G5 adversarial verification → G6 final certification. `Grid` is not yet a supported native geometry container merely because fail-closed checks pass.
