# PSX / Cinnamon — F4 audit, progress and continuity prompt (v2)

Role: Senior Software Architect, Rust/Python Engineer and QA Lead. Audit the **actual** state of `Neuri-AI/PSX`, identify the next *single* executable F4 increment, and report only observed source/test/GitHub Actions evidence. **This prompt is diagnostic and planning only: no production changes, commits, branch merges or PR creation while performing the audit.**

## Repository and required source of truth
- Base branch `develop`; detect current working branch and HEAD SHA (do not assume historical F4 document branch is the implementation branch). Identify open PRs and compare changed paths with base.
- Read completely `AGENTS.md`, `docs/roadmap.md`, `docs/architecture/responsive-grid-contract.md`, `docs/architecture/responsive-grid-implementation-handoff.md`, `docs/architecture/capability-certification-policy.md`, `docs/architecture/sfle-f3-implementation.md`, `docs/architecture/sfle-f3-ci-strategy.md` and relevant approved F1–F3 Cinnamon/adapter contracts.
- Inspect actual code/registry/Markup settings and `psx/sfle/`, Rust solver, `psx/renderers/`, `scripts/ci/impact.py`, `tests/test_ci_impact.py`, `tests/certification/` and relevant `.github/workflows/`. Cross-check documentation with live code and tests. If a document is not yet merged into `develop`, read it from its actual current branch and explicitly report the missing integration.
- Retrieve current HEAD and any final immutable-SHA F3 baseline with actual Actions run URLs and conclusions; no past certificate establishes new Grid features. For any F4 SHA fetch relevant CI, test IDs, census manifests and required native readback.

## Approved scope — do not redesign or invent
Owner formally approved **F4 Contract v1.0 on 2026-10-14**, including **six official gates** (G1 through G6):
1. G1: Grid/GridItem public contracts, defaults, child validation, normalizers, Markup and builder parity, diagnostics.
2. G2: Cinnamon Rust-primary/Python-fallback deterministic 12-column grid mathematics, spans/offsets/auto, wrapping, gaps, RTL, min-max/overflow, differential and Chromium when applicable.
3. G3: Qt/Kivy/Tkinter/Headless native measurement, geometry commit/readback, lifecycle and public behavior receipts.
4. G4: container-based breakpoints, independent nested Grid, Flex/Scroll interoperability, identity/state retention.
5. G5: adverse DPI, resize, resource invalidation, stale generation, rollback, cycle detection, precision and F3 regressions.
6. G6: complete required cross-platform/native/Rust/Python/Chromium/public census exact-SHA acceptance.

Approved public design: `Grid`, `GridItem`, exactly 12 columns, `span="auto"` by default and equal distribution of residual row width, automatic wrapping, full span followed by new auto row, logical offsets consuming columns, explicit overflow respecting minima, Grid-local content-width responsive evaluation, independent nesting, strict validation, RTL, F3 reconciliation identity guarantees, renderer-neutral Cinnamon sole geometry owner. Breakpoints `base=0`, `sm=576`, `md=768`, `lg=992`, `xl=1200`, configurable in application settings; exact settings field must be verified, not fabricated. `GridItem` is a required direct resolved Grid child; function components resolving to GridItem are allowed. Do not reintroduce Row/Column, alternate native layout authority, full CSS Grid tracks, or deferred SFLE-CSS-01/02. Use the **normative contract** for fine details and pending math fixture refinements. Do not call a planned feature implemented.

## Non-negotiable incremental certification rule
Each **new production capability** must, in its own increment, deliver all applicable:
1. **Specific RED→GREEN behavioral tests** for its real positive/negative behavior, props/defaults, update, geometry, limits, lifecycle, readback, interactions, identity/state and supported backend.
2. **Intelligent CI impact routing** for every new/relevant path in `scripts/ci/impact.py`, with correctness tests in `tests/test_ci_impact.py`; prove required transitive backend job selection and exclusion of unrelated suites. Check actual workflow job commands. Unknown routes must fail open conservatively. **Docs-only diff = ZERO product tests.**
3. **Public behavior census** registration/applicability and executed receipts for added public props, events, methods or interactions in `tests/certification/`, including expected result, backend, operation, real assertion/test ID, JUnit artifact, source SHA, environment, reviewed N/A and outstanding cells. Do not accept skipped, documentary, indirect, synthetic or mismatched-SHA receipts as PASS. No new public surface requires a justified N/A instead of invented evidence.

Never shrink assertions or silence backends to obtain GREEN. Selective suites per code increment; full mandatory suite only for formal gate closure. For each gate, only status values `CLOSED`, `IN PROGRESS`, `NOT STARTED`, `BLOCKED`: CLOSED iff implementation and mandatory execution evidence complete, not because docs were approved. Use exact closed-count X/6 and percentage; no claimed progress on unknown evidence.

## Audit and next increment
- Identify G1–G6 statuses on current code SHA and compare with prior F3 baselines; don't confuse historical F3 local owner signoff with complete coverage of newly introduced Grid.
- State branch and HEAD SHA, PRs, changes, source/test/CI observations, exact gaps and conflicts.
- Name one next increment only. If no Grid product implementation exists, recommend the first G1 increment in `responsive-grid-implementation-handoff.md`: registration/defaults/validation and public contract normalization. Specify actual probable paths after inspection, RED/GREEN test cases, required impact routing cases, public census applicability and receipts, actual CI workflows, acceptance evidence and remaining G1 work.
- Separate product defects, unresolved settings/math implementation detail, regression risks, backend coverage, CI/census gaps and external dependencies. If solving an undecided edge case would alter approved observable behavior, flag it for owner approval; otherwise propose a deterministic compatible rule.
- Keep descriptive production file/test/commit names rather than F4/G1/C1 code identifiers. Keep test-only inventories/matrices/receipts out of runtime.

## Required answer sections
A. Executive summary (branch, HEAD SHA, F3 baseline, PR, G1–G6 states, X/6 and prioritized increment)
B. Gate status table (Gate | Goal | Status | Completed | Outstanding | Executed evidence)
C. End-user developer experience: planned vs actually supported Grid, one Markup example
D. Intelligent CI and public census audit (actual routing, workflow links, run SHA and receipts)
E. Precise reasons current gate is not CLOSED
F. Single recommended next increment (paths, behavior, RED/GREEN, CI selection tests, census, workflows, acceptance)
G. Dependency path through G6
H. Confirmed technical failures vs unresolved contracts vs risks and external blockers
I. Direct recommendation with exact verifiable closure condition

Do not perform implementation or modify the repository while executing this audit prompt. If a required source or execution is unavailable, report the limitation, not an assumed PASS.
