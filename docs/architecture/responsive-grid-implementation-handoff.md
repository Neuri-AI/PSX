# Grid public contract — first G1 implementation handoff

**Planning status:** owner-approved F4 contract; this handoff is documentation only and does not authorize claiming production Grid support, a passing test, or an increment closure.

Read `docs/architecture/responsive-grid-contract.md`, `docs/architecture/capability-certification-policy.md`, `AGENTS.md`, existing registry/props/markup contracts and the G1–G5 F3 baseline. Check actual branch, SHA and outstanding PRs before working.

## Single first increment: Grid and GridItem validated public metadata

**Scope:** establish the smallest product-compatible public registration, typed declarations, defaults and fail-closed parsing/normalization for Grid and GridItem, without implementing responsive geometry or native rendering. Preserve existing interfaces, naming and reconciliation semantics; adapt to repository patterns found during implementation rather than inventing modules.

**Functional RED/GREEN cases (minimum):** Grid recognized in builders and Markup; GridItem recognized; defaults (`columns=12`, `span="auto"`, `offset=0`, gaps); only 12 columns; invalid span/offset/types/unknown responsive names rejected; responsive scalar/map structure validated (no geometry claim); direct-resolved-child policy with functional component resolution; mismatched builder vs Markup rejects consistently; unsupported attempts to mount without a Grid layout backend fail explicitly; existing Flex/Scroll/Row-Column removal regressions remain unchanged.

**Impact routing:** inspect actual created/modified paths. Extend `scripts/ci/impact.py` if generic routes omit affected core/markup/headless/native consumers; assert positive selection, unrelated exclusion, mixed changes, unknown paths and docs-only zero-product-tests in `tests/test_ci_impact.py`. Confirm `.github/workflows/native-layout-selective.yml` invokes every selected test; update workflows only when genuinely needed.

**Public census:** register newly exposed Grid/GridItem props/defaults, validation and public interactions in the actual code-derived inventory under `tests/certification/`. Emit behavior-specific assertions and true JUnit execution receipts tied to the tested SHA and applicable backend. Do not grant native geometry PASS before native layout is implemented; mark unsupported cells accurately with reviewed rationales, and never mark unexecuted cells PASS.

**Acceptance:** requirements and negative behavior in source; functional tests RED before implementation and GREEN after; targeted CI route tests GREEN; all applicable public census cells proven using executed receipts; mandatory selected workflow jobs completed SUCCESS for a fixed code SHA. If any element is missing, report IN PROGRESS. No broad integration behavior or new geometry in this increment.

## Planning dependencies and handoff boundary

Later G1 increments can finalize global settings storage for breakpoints and responsive value inheritance, but the exact field name must be checked against existing settings contracts before adding it. G2 owns precise line-packing, equal residual auto distribution, offsets, gaps, intrinsic constraints and Rust/Python math. G3 owns native geometry/readback. G4 owns runtime container breakpoints and nesting. G5 owns adverse regression coverage; G6 full one-SHA certification. Never substitute a historical F3 success for new F4 behavior.

### Before implementation: resolve testable semantics, not new product options
- Create deterministic machine-readable fixtures for `[auto]`, `[auto,auto]`, `[8,auto,auto]`, `[12,auto,auto]`, `[8,6]`, offsets and invalid spans.
- Specify grouping when a later explicit item follows autos, e.g. `[auto,8,auto,6]` under declared logical order: choose a deterministic rule consistent with the contract and seek explicit approval if the observable result changes the agreed behavior.
- Define explicit error classifications for invalid mappings, cyclic widths, infeasible constraints and overflow reporting without adding certification-only modules to runtime.
- Ensure fixed-point/edge rounding and RTL remain part of Cinnamon, not toolkit-specific behavior.

## Required agent report

Return branch and HEAD SHA, changed files, RED/GREEN tests, impact routing selections, workflow run links and conclusions, census rows and receipt identifiers, uncovered/unsupported cells, regressions, exact acceptance status (CLOSED or IN PROGRESS) and the single next implementation increment. Avoid stage codes as filenames or generic commit subjects.
