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
| CSS §9.7 resolved flex grow/shrink | `flex_math.py`, resolved pipelines | `lib.rs`, resolved pipelines | `test_resolved_pipeline.py`, Rust unit tests | PARTIAL: resolved-input kernels only |
| Definite nested geometry | `resolved_tree.py`, `margin_tree.py` | corresponding Rust modules | `test_resolved_tree.py`, `test_margin_tree.py` | PARTIAL: pre-resolved inputs |
| Orthogonal nested auto sizing | `auto_cross_tree.py` explicitly rejects axis mismatch | `auto_cross_tree.rs` rejects mismatch | `test_auto_cross_tree.py` limited nowrap cases | FAIL: target case unsupported |
| Width-dependent measurement after grow | `recursive_pipeline.py` | No equivalent integrated pipeline identified | `test_recursive_pipeline.py::test_intrinsic_leaf_growth_remeasures_at_allocated_width` | PARTIAL |
| Width-dependent measurement after shrink | No accepted end-to-end test identified | No accepted end-to-end test identified | Acceptance test missing | NO ACCEPTANCE TEST |
| Deferred percent/intrinsic tags | `lengths.py`, `sizing.py` | `sizing.rs` | `test_sizing.py`, percent resolver tests | PARTIAL: not CSS tree solver |
| Stale-generation commit rejection | `native_lifecycle.py` | Native scheduling not in pure Rust boundary | `test_native_lifecycle.py::test_stale_generation_blocks_commit_after_measurement` | PARTIAL: Python callback bridge |
| Bounded convergence and oscillation | `convergence.py`, `recursive_pipeline.py` | `convergence.rs` | `test_convergence.py` | PARTIAL: guard, not CSS fixed-point proof |
| Full versioned compute/fallback | `engine.py::PythonLayoutEngine.compute` always raises | `Cargo.toml` no PyO3/maturin dependency; `lib.rs` pure crate | No Rust loader/fallback test | FAIL |
| Shared Python/Rust differential result fixtures | Separate source/tests | Separate source/tests | No shared integrated differential runner identified | FAIL |
| Chromium 0.01 px + error decomposition | Resolved border-box browser comparisons at 0.05 px in current tests | No Rust browser pipeline | `tests/browser/test_sfle_chromium.py` | PARTIAL: insufficient tolerance/coverage |
| Native measurements and geometry | `native_measurement.py`, toolkit ports, lifecycle bridge | Pure computation only | `test_native_lifecycle.py`, toolkit tests | PARTIAL: production renderer integration not established |

### CI audit

- `.github/workflows/sfle-core.yml`: `compileall psx/sfle`, `pytest tests/sfle` on Python 3.10–3.13 and `cargo test --all-targets`; **does not cross-call the Rust and Python engines on shared fixtures**.
- `.github/workflows/sfle-chromium.yml`: `pytest tests/browser/test_sfle_chromium.py` with Playwright Chromium; current fixtures cover selected resolved geometry, not the acceptance trees below, and assert 0.05 px in inspected cases rather than normative 0.01.
- CI passing means only the tests configured there passed. Historical run links and the PR description are not substitutes for acceptance evidence.

## Acceptance table — proposed F2 alpha scope (awaiting confirmation)

A named case is **PASS** only after (a) a test first fails on the baseline, (b) it passes in Python, (c) equivalent Rust result or equivalent explicit error is proven using a common fixture, (d) Chromium reference is compared where CSS geometry applies and (e) the prescribed tolerance and exact line/ID/order invariants pass. An existing narrow test is not itself acceptance.

| ID | Concrete input/tree and expected observable result | Proposed phase | Scope | Current status / required evidence |
| --- | --- | --- | --- | --- |
| A01 | `Flex(row,width:120px)` containing a fixed `40px` sibling and `Flex(column, flex-grow:1, min-width:0, height:auto)` with a `Text(width:100%,height:auto)` leaf whose deterministic intrinsic metric at allocated 80px width is three 20px lines: text content height **60px**, nested column used height **60px**, and when root height is auto with no other taller child, root used content height **60px**. Assert final parent height, not merely leaf width. Chromium fixture must control font metrics/line breaks. | F2.2 implementation + F2.3 verification | IN | FAIL: orthogonal auto tree unsupported |
| A02 | `Flex(row,width:auto)` with direct child `flex-basis:auto;width:auto` and measured min/max/preferred contributions; resolve the parent's content-based main size using CSS intrinsic rules, not zero or an invented definite width. Assert used parent/child widths against Chromium. | F2.2 + F2.3 | IN, semantics to approve | NO ACCEPTANCE TEST |
| A03 | `Flex(column,height:auto)` with descendant `height:50%`: preserve unresolved percentage until the CSS-specific containing-block rule applies; do not substitute 0 or auto universally. Assert Chromium-equivalent used height or identical explicit unsupported diagnosis for a genuinely out-of-scope combination. Include width percentage against definite inline-size ancestor as positive control. | F2.1/2.2 + F2.3 | IN, concrete cyclic behavior to approve | PARTIAL resolver; NO integrated fixture |
| A04 | `Flex(row,width:150px)` with measured text item `flex-grow:1`: initial intrinsic width differs from final 150px; remeasure at allocated width and use resulting multiline height in parent auto cross-size. | F2.2 + F2.3 | IN | PARTIAL Python test, missing integrated parity/browser |
| A05 | `Flex(row,width:70px)` with two `flex-shrink:1` measured text items of 50px basis each, `min-width:0`: each receives 35px before width-dependent remeasurement; parent auto height must reflect the measured post-shrink line count. | F2.2 + F2.3 | IN | NO ACCEPTANCE TEST |
| A06 | Generation G starts measurement, generation G+1 is published before commit: **zero rectangles** from G may be applied; stable node identities remain associated with G+1 only. | F2.2 coordinator / F2 exit | IN | PARTIAL lifecycle guard, add actual port/commit assertion |
| A07 | Stable fully definite fixed point returns converged within explicit iteration bound; `A→B→A` oscillation raises explicit diagnostic and never commits. At bound N, no N+1 measurement pass and no partial native commit. | F2.2 coordinator / F2 exit | IN | PARTIAL guards, end-to-end missing |
| A08 | Same immutable normalized input on Rust/Python yields same node IDs, lines, order, feature decisions, diagnostic codes and geometry within 0.01 CSS px. Missing/unloadable Rust selects Python **before** compute; Rust runtime failure aborts transaction without retry. PSX imports without extension. | F2.2 + F2 exit | IN | FAIL: no PyO3 compute/loader |
| A09 | LTR/RTL row, row-reverse, column and column-reverse (with supported wrapping/alignment combinations): physical rectangles agree with Chromium at 0.01 px, structural identities exact. Unsupported combos error identically. | F2.2 + F2.3 | IN | PARTIAL resolved fixtures |
| A10 | Separate `measurement_error`, `engine_error`, `geometry_commit_error`; headless reference error <=0.01 px, toolkit applied geometry <=1.0 px where available. | F2 exit, native integration completes F3 | IN for reporting/headless; native integration F3 | NOT CERTIFIED |
| A11 | Existing Row/Column/Scroll registrations/algorithms/uses inventoried, replacement and adapter plan prepared; no API modifications during F2. | F2.4 planning; implementation F3 | IN planning only | NO ACCEPTANCE INVENTORY |
| A12 | Full renderer migration, removal of Row/Column and redundant algorithms; Scroll native viewport remains independent. | F3, per F1 final §6 F2.4 and §5 | OUT of F2 implementation | NOT STARTED |
| A13 | Vertical writing modes and unsupported replaced-element/aspect-ratio semantics | Subsequent feature phase must be explicitly approved; not licensed as working in F2 alpha by D-F1.8 | OUT of first alpha slice | Explicit unsupported diagnostic required |

### Hold point — phase/semantic scope decision

Before implementing A01–A10, confirm that the proposed F2 alpha slice includes **automatic intrinsic main sizing** in A02 and **CSS-specific handling of indefinite/cyclic percentages** in A03 rather than a blanket rejection. The F1 final architecture requires complete F2 exit evidence but allows incremental capability gates; it does not authorize silently dropping these cases or relegating required F2 work to F3.

## Required red-green and release protocol

1. Freeze this acceptance table after scope confirmation; fixture IDs do not change without explicit review.
2. Create Python, Rust and browser fixtures for each supported case and record the exact failing baseline assertion (red) before modifying algorithms.
3. Implement coherent cases across the normalized input → measurement → pure computation → generation-checked commit path; reject unsupported combinations identically.
4. Run `pytest tests/sfle`, `cargo test --all-targets`, shared Rust/Python differential fixtures, `pytest tests/browser/test_sfle_chromium.py` and missing-Rust import/loader fixtures. Identify CI job coverage for each case.
5. Report only case status: PASS, FAIL or NO TEST. A subblock closes only when every in-scope case assigned to it passes. Keep Row/Column/Scroll and the public capability manifest unchanged.

**Current acceptance summary:** No A01–A10 case is certified PASS at this audit point. Existing unit tests give partial evidence for individual cases, not the complete acceptance contract. No test run or branch write is asserted by this baseline audit except the present documentation update.
