# SFLE F2 — verified implementation audit and acceptance register

> Audit baseline: PR #11, branch `feat/sfle-f2-core`, commit `2ad3df176d8df3f48b87794b7e47aa092278991a`, 2026-10-10.
> **State: scope approval required before implementation. No test execution or CSS conformance certification is claimed in this audit.**
> This is the single current F2 status register. Earlier commit-count and 4/8 versus 5/8 progress claims are withdrawn; this register replaces the increment log.

## Normative precedence

1. [F1 final architecture](sfle-f1-final-architecture.md), especially §§2–3 and §6 (F2.0–F2.4, F2 exit criteria).
2. [Box model](sfle-f1-box-model.md).
3. [Contracts](sfle-f1-contracts.md), excluding its superseded proposed F2.A–D phases.
4. [Properties and lengths](sfle-f1-props-lengths.md).
5. [SFLE architecture and algorithm](sfle.md), §§5, 9, 10.
6. [CSS Flexbox Level 1](https://www.w3.org/TR/css-flexbox-1/) and equivalent Chromium reference fixtures.

This document reports evidence, not authority. Keep public Row/Column/Scroll and the public capability manifest unchanged during F2. F2.4 inventories migration; F3 performs removal. The approved F2 exit criteria include Rust-primary selection, equivalent Python fallback, differential geometry, headless/browser conformance and explicit unsupported errors; those requirements cannot be deferred merely by renaming them F2.2.5/F2.2.6/F2.3.

## Audited implementation inventory (not an execution report)

| Normative requirement | Python implementation | Rust implementation | Existing evidence/test | Verified state |
| --- | --- | --- | --- | --- |
| CSS §9.7 resolved flex grow/shrink | `flex_math.py`, resolved pipelines | `lib.rs`, resolved pipelines | `test_resolved_pipeline.py`, Rust unit tests | FAIL — no full acceptance test: resolved-input kernels only |
| Definite nested geometry | `resolved_tree.py`, `margin_tree.py` | corresponding Rust modules | `test_resolved_tree.py`, `test_margin_tree.py` | FAIL — no full acceptance test: pre-resolved inputs |
| Orthogonal nested auto sizing | `auto_cross_tree.py` explicitly rejects axis mismatch | `auto_cross_tree.rs` rejects mismatch | `test_auto_cross_tree.py` limited nowrap cases | FAIL: target case unsupported |
| Width-dependent measurement after grow | `recursive_pipeline.py` | No equivalent integrated pipeline identified | `test_recursive_pipeline.py::test_intrinsic_leaf_growth_remeasures_at_allocated_width` | FAIL — no full acceptance test |
| Width-dependent measurement after shrink | No accepted end-to-end test identified | No accepted end-to-end test identified | Acceptance test missing | NO TEST |
| Deferred percent/intrinsic tags | `lengths.py`, `sizing.py` | `sizing.rs` | `test_sizing.py`, percent resolver tests | FAIL — no full acceptance test: not CSS tree solver |
| Stale-generation commit rejection | `native_lifecycle.py` | Native scheduling not in pure Rust boundary | `test_native_lifecycle.py::test_stale_generation_blocks_commit_after_measurement` | FAIL — no full acceptance test: Python callback bridge |
| Bounded convergence and oscillation | `convergence.py`, `recursive_pipeline.py` | `convergence.rs` | `test_convergence.py` | FAIL — no full acceptance test: guard, not CSS fixed-point proof |
| Full versioned compute/fallback | `engine.py::PythonLayoutEngine.compute` always raises | `Cargo.toml` no PyO3/maturin dependency; `lib.rs` pure crate | No Rust loader/fallback test | FAIL |
| Shared Python/Rust differential result fixtures | Separate source/tests | Separate source/tests | No shared integrated differential runner identified | FAIL |
| Chromium 0.01 px + error decomposition | Resolved border-box browser comparisons at 0.05 px in current tests | No Rust browser pipeline | `tests/browser/test_sfle_chromium.py` | FAIL — no full acceptance test: insufficient tolerance/coverage |
| Native measurements and geometry | `native_measurement.py`, toolkit ports, lifecycle bridge | Pure computation only | `test_native_lifecycle.py`, toolkit tests | FAIL — no full acceptance test: production renderer integration not established |

### CI audit

- `.github/workflows/sfle-core.yml`: `compileall psx/sfle`, `pytest tests/sfle` on Python 3.10–3.13 and `cargo test --all-targets`; **does not cross-call the Rust and Python engines on shared fixtures**.
- `.github/workflows/sfle-chromium.yml`: `pytest tests/browser/test_sfle_chromium.py` with Playwright Chromium; current fixtures cover selected resolved geometry, not the acceptance trees below, and assert 0.05 px in inspected cases rather than normative 0.01.
- CI passing means only the tests configured there passed. Historical run links and the PR description are not substitutes for acceptance evidence.

## Acceptance table — proposed F2 alpha scope (awaiting confirmation)

A named case is **PASS** only after (a) a test first fails on the baseline, (b) it passes in Python, (c) equivalent Rust result or equivalent explicit error is proven using a common fixture, (d) Chromium reference is compared where CSS geometry applies and (e) the prescribed tolerance and exact line/ID/order invariants pass. An existing narrow test is not itself acceptance.

| ID | Concrete input/tree and expected observable result | Proposed phase | Scope | Current status / required evidence |
| --- | --- | --- | --- | --- |
| A01 | `Flex(row,width:120px)` containing a fixed `40px` sibling and `Flex(column, flex-grow:1, min-width:0, height:auto)` with a `Text(width:100%,height:auto)` leaf whose deterministic intrinsic metric at allocated 80px width is three 20px lines: text content height **60px**, nested column used height **60px**, and when root height is auto with no other taller child, root used content height **60px**. Assert final parent height, not merely leaf width. Chromium fixture must control font metrics/line breaks. | F2.2 implementation + F2.3 verification | IN | FAIL: orthogonal auto tree unsupported |
| A02 | `Flex(row,width:auto)` with direct child `flex-basis:auto;width:auto` and measured min/max/preferred contributions; resolve the parent's content-based main size using CSS intrinsic rules, not zero or an invented definite width. Assert used parent/child widths against Chromium. | F2.2 + F2.3 | IN, semantics to approve | NO TEST |
| A03 | `Flex(column,height:auto)` with descendant `height:50%`: preserve unresolved percentage until the CSS-specific containing-block rule applies; do not substitute 0 or auto universally. Assert Chromium-equivalent used height or identical explicit unsupported diagnosis for a genuinely out-of-scope combination. Include width percentage against definite inline-size ancestor as positive control. | F2.1/2.2 + F2.3 | IN, concrete cyclic behavior to approve | FAIL — no full acceptance test resolver; NO integrated fixture |
| A04 | `Flex(row,width:150px)` with measured text item `flex-grow:1`: initial intrinsic width differs from final 150px; remeasure at allocated width and use resulting multiline height in parent auto cross-size. | F2.2 + F2.3 | IN | FAIL — no full acceptance test Python test, missing integrated parity/browser |
| A05 | `Flex(row,width:70px)` with two `flex-shrink:1` measured text items of 50px basis each, `min-width:0`: each receives 35px before width-dependent remeasurement; parent auto height must reflect the measured post-shrink line count. | F2.2 + F2.3 | IN | NO TEST |
| A06 | Generation G starts measurement, generation G+1 is published before commit: **zero rectangles** from G may be applied; stable node identities remain associated with G+1 only. | F2.2 coordinator / F2 exit | IN | FAIL — no full acceptance test lifecycle guard, add actual port/commit assertion |
| A07 | Stable fully definite fixed point returns converged within explicit iteration bound; `A→B→A` oscillation raises explicit diagnostic and never commits. At bound N, no N+1 measurement pass and no partial native commit. | F2.2 coordinator / F2 exit | IN | FAIL — no full acceptance test guards, end-to-end missing |
| A08 | Same immutable normalized input on Rust/Python yields same node IDs, lines, order, feature decisions, diagnostic codes and geometry within 0.01 CSS px. Missing/unloadable Rust selects Python **before** compute; Rust runtime failure aborts transaction without retry. PSX imports without extension. | F2.2 + F2 exit | IN | FAIL: no PyO3 compute/loader |
| A09 | LTR/RTL row, row-reverse, column and column-reverse (with supported wrapping/alignment combinations): physical rectangles agree with Chromium at 0.01 px, structural identities exact. Unsupported combos error identically. | F2.2 + F2.3 | IN | FAIL — no full acceptance test resolved fixtures |
| A10 | Separate `measurement_error`, `engine_error`, `geometry_commit_error`; headless reference error <=0.01 px, toolkit applied geometry <=1.0 px where available. | F2 exit, native integration completes F3 | IN for reporting/headless; native integration F3 | NO TEST |
| A11 | Existing Row/Column/Scroll registrations/algorithms/uses inventoried, replacement and adapter plan prepared; no API modifications during F2. | F2.4 planning; implementation F3 | IN planning only | NO ACCEPTANCE INVENTORY |
| A12 | Full renderer migration, removal of Row/Column and redundant algorithms; Scroll native viewport remains independent. | F3, per F1 final §6 F2.4 and §5 | OUT of F2 implementation | NO TEST |
| A13 | Vertical writing modes and unsupported replaced-element/aspect-ratio semantics | Subsequent feature phase must be explicitly approved; not licensed as working in F2 alpha by D-F1.8 | OUT of first alpha slice | Explicit unsupported diagnostic required |

### Hold point — phase/semantic scope decision

Before implementing A01–A10, confirm that the proposed F2 alpha slice includes **automatic intrinsic main sizing** in A02 and **CSS-specific handling of indefinite/cyclic percentages** in A03 rather than a blanket rejection. The F1 final architecture requires complete F2 exit evidence but allows incremental capability gates; it does not authorize silently dropping these cases or relegating required F2 work to F3.

## Required red-green and release protocol

1. Freeze this acceptance table after scope confirmation; fixture IDs do not change without explicit review.
2. Create Python, Rust and browser fixtures for each supported case and record the exact failing baseline assertion (red) before modifying algorithms.
3. Implement coherent cases across the normalized input → measurement → pure computation → generation-checked commit path; reject unsupported combinations identically.
4. Run `pytest tests/sfle`, `cargo test --all-targets`, shared Rust/Python differential fixtures, `pytest tests/browser/test_sfle_chromium.py` and missing-Rust import/loader fixtures. Identify CI job coverage for each case.
5. Report only case status: PASS, FAIL or NO TEST. A subblock closes only when every in-scope case assigned to it passes. Keep Row/Column/Scroll and the public capability manifest unchanged.

**Current acceptance summary:** No A01–A10 case is certified PASS at this audit point. Existing unit tests give partial evidence for individual cases, not the complete acceptance contract. The baseline 2ad3df17 Python/Rust matrix did not execute in the checked workflow; the RED tests on descendant 6698dd6b are separately documented below.

## 2026-10-10 scope confirmation — accepted A01–A10

User-approved mandatory conditions:
- Orthogonal automatic flex sizing is **IN** (A01), not an allowable `UNSUPPORTED_FEATURE` escape for the named fixture.
- A08 is **IN F2**: PyO3/maturin, Rust-primary load-time negotiation, Python fallback, versioned wire contract, equivalent error codes and a differential runner executing the **same A01–A07 input trees** through both engines.
- The public manifest stays closed until the complete supported feature set passes both engines and Chromium as applicable.
- Exclusions do not override the F2 exit gates of [F1 final architecture §6](sfle-f1-final-architecture.md).

### Explicitly enumerated indefinite/cyclic percentage behaviors

This is an *allowlist of required alpha implementations*, not a statement that the current code supports them. Reference: [box model §5.1–§5.4](sfle-f1-box-model.md), [Flexbox §7.2.3, §9.8–§9.9](https://www.w3.org/TR/css-flexbox-1/), and CSS Sizing cyclic contribution rules where referenced by Flexbox.

| Cycle ID | Alpha behavior required | Test to establish (Python, Rust, Chromium when relevant) | Current acceptance |
| --- | --- | --- | --- |
| C01 | `flex-basis:N%` with indefinite flex container **main** size resolves to measured content-based used flex basis, not numeric zero; preserve original percent tag until correct stage | `test_A03_C01_indefinite_percent_flex_basis` | NO TEST (integrated) |
| C02 | `flex-basis:auto` / `width:auto` for a flex container with intrinsic main contributions uses the §9.9 content-based sizing algorithm; do not infer definite size from viewport | `test_A02_C02_auto_intrinsic_main` | NO TEST (integrated) |
| C03 | A post-flex definite flex item main size can establish a definite reference for percentage-sized descendants; re-resolve against **final allocated used size** and remeasure, rather than the pre-flex hint | `test_A03_C03_post_flex_definiteness` | NO TEST |
| C04 | Cyclic percentage `row_gap` or `column_gap` contributes **zero only in the intrinsic contribution phase**; subsequently use the resolved gap if the resulting used reference becomes definite, otherwise explicit unsupported failure | `test_A03_C04_intrinsic_gap_vs_used_gap` | NO TEST (integrated); helper tests exist |
| C05 | Percentage block-axis height under an auto-height containing ancestor remains tagged while indefinite; apply the context-specific CSS auto/intrinsic rule where defined and re-resolve if flex definiteness later arises | `test_A03_C05_auto_ancestor_percent_height` | NO TEST |
| C06 | Percentage margin/padding on all physical sides uses the containing block's **inline size**; cyclic intrinsic contributions must follow CSS Sizing rules, never universal 0 or viewport substitution | `test_A03_C06_percentage_edges_intrinsic` | NO TEST |

**Strict negative gate:** every cyclic dependency *not* in C01–C06—including multi-node mutually dependent percentage sizing and cycles involving percentage min/max whose CSS resolution is not covered by the allowlist—must raise the exact diagnostic `SFLE_UNSUPPORTED_FEATURE` on both engines, with matching node IDs and no geometry commit. Required paired test: `test_A03_C99_unlisted_percentage_cycle_rejected_by_both_engines`. This is an explicit alpha capability restriction, not a claim that the underlying CSS case is undefined.

### Other first-alpha exclusions and destinations

| Excluded case | Required behavior | Destination |
| --- | --- | --- |
| Replaced elements with intrinsic aspect-ratio transfer / `aspect-ratio` | Both engines error `SFLE_UNSUPPORTED_FEATURE`, no approximation | Post-alpha **F2.2 feature slice**, then **F2.3 browser verification**; F3 does not own CSS math |
| `flex-wrap` combined with **intrinsically auto-sized** flex containers | Both engines error `SFLE_UNSUPPORTED_FEATURE`; do not disable fixed-size wrap | Post-alpha **F2.2 sizing slice**, then **F2.3** |
| Vertical writing modes | Both engines error `SFLE_UNSUPPORTED_FEATURE` | Post-alpha extension requiring separate architecture approval (F1 D-F1.8 limits F2 to horizontal writing modes) |
| Public Row/Column removal and Scroll integration | Keep unchanged during F2 | **F3**, with inventory/adapter design in **F2.4** |

### Actual CI observation pinned to baseline 2ad3df17

Checked workflow run **38078223822**: detector succeeded, **Rust SFLE core job skipped** and **Python SFLE matrix job skipped**. Workflow **38078223945** executed its Chromium browser comparison and succeeded; it does not cover A01–A10 end-to-end. Workflow **38078223968** succeeded at the change-detection stage but **Python core, PySide6 offscreen and distribution build were skipped**. These are actual job results, not inferred successes. Full Python and Rust suite **execution on 2ad3df17 remains NOT EXECUTED** in those runs; the environment in this session lacks a checkout and a Rust compiler and cannot clone externally. No PASS is assigned to unexecuted A01–A10 tests.

### RED implementation evidence

Commit `6698dd6bae37d35f59ae85d82c8d53b02b7d1ba8` introduces `tests/sfle/test_f2_acceptance_red.py` with:
- `test_A01_orthogonal_auto_parent_height_from_descendant`: demands auto-height convergence across perpendicular axes; the inspected Python helper explicitly raises an unsupported feature.
- `test_A08_python_compute_is_a_real_fallback_not_a_placeholder`: demands a real computation; the inspected `PythonLayoutEngine.compute` unconditionally raises `UnsupportedLayoutFeature`.

These are deliberate RED gates, not accepted features. Rust/Python differential A01–A07 and browser fixtures remain **NO TEST** until implemented; do not mark any phase done.

### Executed RED results (not baseline-suite success)

GitHub Actions SFLE Core run [38078742516](https://github.com/Neuri-AI/PSX/actions/runs/38078742516) at commit `6698dd6bae37d35f59ae85d82c8d53b02b7d1ba8` **completed**:
- Python 3.10, 3.11, 3.12, 3.13: **2 failed, 304 passed, 1 skipped** on every Python matrix job.
- `tests/sfle/test_f2_acceptance_red.py::test_A01_orthogonal_auto_parent_height_from_descendant` — **FAIL**, `SFLECapabilityError` at `psx/sfle/auto_cross_tree.py:74` (orthogonal axis rejection).
- `tests/sfle/test_f2_acceptance_red.py::test_A08_python_compute_is_a_real_fallback_not_a_placeholder` — **FAIL**, `UnsupportedLayoutFeature` at `psx/sfle/engine.py:42` (no `compute()` implementation).
- Rust SFLE core job: **PASS**, but did not execute either acceptance test or Python/Rust differential geometry.
- [Chromium run 38078742518](https://github.com/Neuri-AI/PSX/actions/runs/38078742518): **PASS** on existing browser fixtures only, no A01/A08 browser parity.
- PSX alpha validation run 38078742519: **PASS** on its existing jobs, not acceptance evidence for A01/A08.

**Acceptance status after RED:** A01 FAIL (named test executed), A08 FAIL (named test executed); A02, A03, A05 and integrated A06/A07 remain NO TEST for complete target behavior; A04, A09/A10 have pre-existing scoped tests but NO full acceptance tests. No acceptance gate closed. Baseline 2ad3df17 still lacks an executed Python/Rust suite on that exact SHA in the inspected Actions runs; execution on descendant 6698dd6b establishes the observed baseline blockers without falsely asserting exact-SHA execution.

**Engineering stop condition:** Fixing A01 by merely deleting the orthogonal rejection would be incorrect: it needs a real main-axis intrinsic contribution phase and a final used-size pass with cross-axis remeasurement, in both languages. Do not turn a red fixture green by hardcoding its expected dimensions or by skipping Rust.
