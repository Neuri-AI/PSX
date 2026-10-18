# P0.6 — Architecture Gate and Approval Record

**Date:** 2026-10-18  
**Status:** **BLOCKED — NO OWNER APPROVAL RECORDED**  
**Gate:** P0 → P1 (Web-like + CSS-like implementation)  
**Target branch:** `Neuri-AI/PSX:develop`

> This is a gate **checklist and proposed decision record**, not a claim of approval, certification, or authorization. Only a recorded owner decision plus executable evidence can change the status.

## 1. Mandatory context for all implementing agents

1. [Velto master execution plan](velto-master-execution-plan.md)
2. [P0 source audit](velto-p0-baseline-audit.md)
3. [P0 verification report](P0_VERIFICATION_REPORT.md)
4. [Existing-contract index](CONTRACTS_INDEX.md)
5. [Proposed C01–C12 deltas](P0_CONTRACT_DELTAS.md)

Read F1/F2/F3/F4/F5.5 original normative sources from the index. The proposed contracts are NOT replacements for frozen decisions.

## 2. Gate status (read-only audit)

| Gate | Status | Required evidence / reviewer action |
| --- | --- | --- |
| G-P0-01 PSX exact-commit source inspection | PARTIAL | Pin full tracked tree, map every changed contract clause, verify Rust code and test coverage at source SHA |
| G-P0-02 Cross-repository provenance | PARTIAL | Pin Velto, Pydux, Qyro Engine and CLI branch heads/manifest metadata; resolve naming/versions |
| G-P0-03 Package graph, H-PKG-01 | **BLOCKED** | Build wheels, run fresh local/public resolver and facade import/mount tests |
| G-P0-04 Teardown safety, H-MEM-01 | **BLOCKED** | Fault injection for user cleanup/native unbind/destroy; assert post-unmount counts |
| G-P0-05 Core and native tests | **BLOCKED** | Same-SHA pytest + native Qt/Tk/Kivy CI, Rust/Python differential and clear skip list |
| G-P0-06 Style + box model C01–C03 | PROPOSED | Owner adjudicates overflow/defaults/cascade/block scope; frozen F1 remains binding |
| G-P0-07 Lifecycle C04/C06–C09 | PROPOSED | Owner approves exception policy, ownership, callbacks, measurement fallback and interface extension |
| G-P0-08 Public API + packaging C05 | PROPOSED | Owner approves lowercase alias vocabulary and a compatible distribution matrix |
| G-P0-09 F6, native parity + quality C10–C12 | PROPOSED | Scope/coverage/CI receipts and owner sign-off |
| G-P0-10 F5.5 G6 status | UNVERIFIED | Resolve owner sign-off discrepancy with current progress/CI evidence |

**No requirement row is an executed PASS.** Existing historical CI evidence remains available but is not a substitute for current same-SHA execution.

## 3. Architecture freezes preserved pending approval

- PSX **Markup** is the UI language; it must not be promoted as inherently declarative.
- Cinnamon is integrated inside PSX; no new separate user-facing layout framework.
- Existing `Button`, `Text`, `Flex`, `Grid`, etc. remain public; do not re-add retired `Row`/`Column` merely to satisfy a compatibility slogan.
- F1 typed lengths, `layout_width`/`layout_height`, fixed-point 1/64px, strict property partitioning, and UI-thread native measurement continue to govern implemented scope.
- F4 12-column Grid is not full CSS Grid.
- Browser-complete styling/cascade and F2 deferred `aspect_ratio`/auto-wrap features are not automatically in scope.
- Qyro Engine, CLI and Pydux require their own explicit integration/version contracts.

## 4. Owner decision form (not yet signed)

Use this table as a ledger **only after direct owner review**. Blank fields mean unresolved; no one may fill with inferred agreement.

| ID | Decision to approve | Selected choice | Date | Owner acceptance proof / PR |
| --- | --- | --- | --- | --- |
| AD-01 | Overflow/Scroll subset | PENDING | — | — |
| AD-02 | Box-sizing default for new lowercase tags | PENDING | — | — |
| AD-03 | CSS-like style precedence and cascade | PENDING | — | — |
| AD-04 | Block formatting scope | PENDING | — | — |
| AD-05 | Exception-safe disposal policy | PENDING | — | — |
| AD-06 | Lowercase markup vocabulary/compatibility | PENDING | — | — |
| AD-07 | Package/version dependency graph | PENDING | — | — |
| AD-08 | Fragment/mixed-key evolution | PENDING | — | — |
| AD-09 | Measurement/invalidation adapter interface | PENDING | — | — |
| AD-10 | F6 refresh tier classification | PENDING | — | — |
| AD-11 | Supported backend/performance matrix | PENDING | — | — |
| AD-12 | F5.5 G6 certification status | PENDING | — | — |

## 5. Approval rule

Owner approval requires **all** of:

1. In-scope C01–C12 normative deltas fully reviewed and decisions AD-01–AD-12 dispositioned (approved, explicitly deferred with non-impact proof, or rejected).
2. Every nondeferred requirement mapped to current source symbol and behavioral test at pinned SHA.
3. H-PKG-01 and H-MEM-01 resolved to reproduced finding or explicitly falsified with logs; fixes may remain P1 tasks only if risk accepted with guardrails.
4. Backend/Python/OS test matrix and current same-SHA receipts recorded; missing access and skips explicitly identified.
5. Owner signs final gate with timestamp, reference/issue and revision. Do not auto-sign on their behalf.

**To mark approved later:** change status to `APPROVED`, add `Approved by`, `Approved on`, applicable immutable SHA range and owner evidence. Approval of document wording does not itself certify runtime implementation.

## 6. Parallelism before the gate

Allowed now: read-only source/contract mapping, repro tests **without production modifications**, dependency resolver investigation, benchmark instrumentation in isolated environments, documenting proposed ADRs, reviewing test plans.

Not allowed yet: breaking public aliases/components, changing cross-cutting renderer geometry/lifetime protocols, silently updating pinned contract semantics, claiming fresh native/CI passes or advertising full CSS support.

## 7. Immediate handoff

- **Verification agent:** execute report gates PKG-1/PKG-2 and MEM-1/MEM-2, capture source SHA and logs.
- **Cinnamon/renderer agent:** map C01/C03/C08/C09 to actual sources and run pure/native geometry tests.
- **API/docs agent:** enumerate current public exports; review C02/C05 markup compatibility and owner decision alternatives.
- **Integrator/reviewer:** review dependency graph, C06/C07 failure policy and all proposed delta acceptance criteria.

Each agent commits **evidence-only** documentation to `develop` using conventional commit messages. Do not claim a gate passed without a reproducible receipt.

**CURRENT RESULT: P0 contract drafts available to agents; ARCHITECTURE GATE BLOCKED.**


## 8. Owner decision review package

[Source-backed recommendations and alternatives for AD-01–AD-12](P0_OWNER_DECISION_PACKAGE.md) were published 2026-10-18. The recommendations are **PROPOSED** and **none are owner-approved**. An offline PEP 440 comparison was executed and recorded in [P0 verification](P0_VERIFICATION_REPORT.md#7-offline-pep-440-specifier-intersection-check-2026-10-18); actual wheel/pip/native tests remain unexecuted.

 
## P0 contract review progress — 2026-10-18

**Source-backed technical reviews completed: 12/12 decisions (AD-01–AD-12). Owner approvals: 0/12. Executed full test/CI closure: pending.** This is a review metric, **not** acceptance/certification of C01–C12 or release readiness.

- [Batch 1 — public semantics and compatibility](P0_CONTRACT_REVIEW_BATCH_1.md): AD-01/02/03/04/06/08
- [Batch 2 — safety and packaging](P0_CONTRACT_REVIEW_BATCH_2.md): AD-05/07/09
- [Batch 3 — hot reload and certification](P0_CONTRACT_REVIEW_BATCH_3.md): AD-10/11/12

**Blocking gates unchanged:** H-PKG-01 actual resolver, H-MEM-01 teardown fault-injection, native/Python/Rust same-SHA matrix, and explicit owner decisions. P1 implementation **NOT AUTHORIZED**.


## P0.7 limited executed evidence — gate remains blocked

2026-10-18: [P0 verification §8](P0_VERIFICATION_REPORT.md#8-p07--isolated-fault-path-execution-and-current-manifests-2026-10-18) adds **reproduced isolated-harness H-MEM-01 teardown interruption**, demonstrating that a throwing effect cleanup bypasses child/native destroy in copied current method bodies. An actually executed local `packaging` version-range check also confirms three version mismatches for the checked source manifests, including the PSX project distribution-name mismatch.

**Not certified:** the real GitHub checkout test suite, a live Qt/Tk/Kivy leak, clean-wheel/pip dependency resolution, same-SHA CI, or owner approval of AD-05/AD-07. No gate row should be reclassified to PASS on the strength of these limited observations. The Architecture Gate stays **BLOCKED**.


## P0.7 targeted remediation after owner instruction to continue

A scoped **defensive C07 production patch** is now present in `develop`, even though **the global P0→P1 Architecture Gate remains BLOCKED**:

- [`psx/core/hooks.py`](../../psx/core/hooks.py) and [`psx/core/reconcile.py`](../../psx/core/reconcile.py) attempt independent cleanup after hook/event/native disposer failures and surface the first error.
- [Six regression cases](../../tests/test_p0_teardown_diagnostics.py) are committed but not yet executed inside a clone; a **four-scenario isolated cleanup harness** passed locally.
- [Package metadata checker](../../scripts/verify_velto_dependency_graph.py) was committed; its local synthetic-fixture check identified three known incompatibilities, **not** a clean-wheel resolver failure.
- See [P0 verification §9](P0_VERIFICATION_REPORT.md#9-p07-c07-defensive-patch-and-executable-local-probes-2026-10-18) for exact limitations.

This is an **implemented partial risk mitigation**, not formal owner ratification of AD-05's complete error API and **not** evidence that memory leaks or package resolution are certified. The decision table remains PENDING; production stability and public release are not authorized merely by these commits. Before further P1/C07 expansion, get same-SHA core/native CI and explicit acceptance of the error propagation/aggregation policy.


## Automated execution attempt and receipts — 2026-10-18

A targeted [P0 core lifecycle workflow](../../.github/workflows/p0-core-lifecycle.yml) is committed to `develop` with Python 3.10/3.13 jobs and actual unit-test commands; the CI configuration and new four-case [manifest checker tests](../../tests/test_p0_dependency_graph.py) were verified as repository files. **No Actions run conclusion was accessible through the available connector during this session**, so G-P0-05 remains **NOT CERTIFIED**. See [P0 Verification §10](P0_VERIFICATION_REPORT.md#10-automated-p0-test-jobs-on-develop-2026-10-18).

The six [C07 cleanup regression cases](../../tests/test_p0_teardown_diagnostics.py) still need executable same-SHA CI evidence and native adapter tests; the C05 diagnostic checker cannot substitute for wheel/pip installation. **Architecture Gate stays BLOCKED.**


## Verified-by-owner screenshot: P0 core workflow four successes

On 2026-10-18 the owner provided a screenshot of four successful `develop` runs of [P0 core lifecycle verification](https://github.com/Neuri-AI/PSX/actions/workflows/p0-core-lifecycle.yml) (#1 `2dbc439`, #2 `6b866ad`, #3 `8fed3b9`, #4 `5ae8703`). The latest inspected YAML runs core lifecycle tests including six C07 regression cases and four C05 checker cases in Python 3.10/3.13. **These are screenshot-confirmed green workflow outcomes; individual job logs and detailed counts have not been inspected.** This updates the earlier entry that did not have access to push-run results.

**G-P0-05 disposition:** core headless/diagnostic subset **CI GREEN (screenshot)**; full core/native acceptance **PARTIAL, NOT CLOSED**. **G-P0-03 clean-wheel/pip installation, G-P0-04 native-memory retention and owner approval remain BLOCKED.** This note does not grant global P1 gate approval. Details: [P0 verification §11](P0_VERIFICATION_REPORT.md#11-screenshot-confirmed-p0-core-matrix-results-2026-10-18).


## P0.8 native and wheel CI work (2026-10-18)

New [P0.8 certification record](P0_NATIVE_CERTIFICATION_STATUS.md) documents an actual PySide6 native teardown regression suite and a separate [P0 native lifecycle workflow](../../.github/workflows/p0-native-lifecycle.yml) targeting PySide6 on Python 3.10/3.13 plus a clean, isolated **PSX-only** wheel smoke test. The tests and workflow are committed and fetch-verified; **no workflow result has been verified** yet. These jobs cannot close Pydux/Qyro/Velto facade resolver compatibility, Tk/Kivy retention, or the all-backend memory soak requirements.

**Global Architecture Gate continues BLOCKED until same-SHA job receipts, full package graph tests and explicit AD-05/AD-07 approval.**


## P0.8 CI failure follow-up — native handle identity

Owner supplied native CI #1 log: the wheel smoke passed, but both PySide6 matrix jobs failed due to an existing `Native(QLabel)` reuse assertion (`1 failed, 20 passed` shown for one job). Inspection confirmed a freshly constructed default `SFLEExternalPort` created new callback identities on every `Native()` call, invalidating strict native VNode equality. A bounded per-backend immutable default-port cache was added to [native.py](../../psx/core/native.py), with an explicit identity regression in [test_pyside6_renderer.py](../../tests/test_pyside6_renderer.py). See [P0 native certification record](P0_NATIVE_CERTIFICATION_STATUS.md#ci-1-failure-and-targeted-repair-2026-10-18). **No green post-fix native CI result verified yet; global gate remains blocked.**


## P0.8 native CI follow-up — owner screenshot (2026-10-18)

The project owner provided a screenshot of the [P0 native lifecycle verification workflow](https://github.com/Neuri-AI/PSX/actions/workflows/p0-native-lifecycle.yml) showing:

| Workflow | Commit prefix | UI status |
| --- | --- | --- |
| #1 | `9432cd5` | FAILED (known NativeWidget identity regression) |
| #2 | `1c19c95` | Neutral/inconclusive icon; no success asserted |
| #3 | `74d0a47` | **SUCCESS (green check)**; 50 seconds |

The #3 workflow is configured to run the PySide6 lifetime suites on Python 3.10 and 3.13 plus an isolated `velto-core` wheel build and install. **The screenshot confirms overall run success, but not individual job logs, exact test counts, native RSS stability, other backends, or the Velto/Pydux/Qyro dependency graph.**

**Gate disposition:** P0.8 PySide6 native CI and single-package wheel smoke **SCREENSHOT-CONFIRMED GREEN** on the tested revision; full C07 memory soak and C05 cross-repo resolver remain OPEN. AD-05/AD-07 owner signoff remains pending. Global P0→P1 Architecture Gate remains BLOCKED.


## P0.9 Tkinter/Kivy native lifecycle test matrix (2026-10-18)

Published [P0.9 certification protocol](P0_TK_KIVY_CERTIFICATION.md), actual native regression probes [Tkinter](../../tests/test_p0_tkinter_native_lifecycle.py) and [Kivy](../../tests/test_p0_kivy_native_lifecycle.py), and a dedicated [Tk/Kivy CI workflow](../../.github/workflows/p0-tk-kivy-lifecycle.yml) running four Linux/Xvfb jobs. **Outcome not yet verified**; do not infer native certification from a published test file. The full architecture gate remains **BLOCKED** pending actual run receipts, long-memory soak and C05 clean ecosystem installation.


## P0.9 CI #2 — Kivy comparison failure and scoped test fix (2026-10-18)

**Evidence:** owner-provided GitHub Actions run [#39134742987](https://github.com/Neuri-AI/PSX/actions/runs/39134742987) on commit `27870e5` and original failure logs for [Kivy 3.13](https://github.com/Neuri-AI/PSX/actions/runs/39134742987/job/117696952678) and [Kivy 3.11](https://github.com/Neuri-AI/PSX/actions/runs/39134742987/job/117696952452).

| Matrix cell | Result |
| --- | --- |
| Tk 3.10 and 3.13 | **SUCCESS** (owner screenshot; 2/2 jobs) |
| Kivy 3.11 and 3.13 | **FAILED**: 1 failed / 2 passed in each cell |

Both Kivy jobs initialized real SDL2 + Mesa under Xvfb. The failure was solely `assert borrowed.size_hint == original_size_hint` after unmount; earlier assertions confirmed the borrowed widget had returned to its original parent. Kivy's `ReferenceListProperty` exposes a list-like `size_hint` whereas `original_size_hint` in the test is a tuple. The renderer already captures `tuple(widget.size_hint)` and assigns that snapshot during `destroy()`; direct list-vs-tuple equality falsely rejects numerically identical values.

**Scoped correction:** [Kivy lifecycle test](../../tests/test_p0_kivy_native_lifecycle.py) now compares `tuple(borrowed.size_hint)` with the expected tuple. It additionally asserts original contents *before mount*, temporary `(None, None)` values *while mounted*, and restored contents after unmount. `pos_hint` is compared by `dict(...)`. **No Kivy renderer production code was changed.**

**Verification:** source change committed and re-fetched from `develop`; **new CI conclusion is not yet available at this writing**. Don't mark Kivy native certification green until the post-fix matrix run passes, including both Python versions.


## P0.9 Linux native matrix success (2026-10-18)

Owner screenshot establishes [Tkinter/Kivy native CI #4](https://github.com/Neuri-AI/PSX/actions/workflows/p0-tk-kivy-lifecycle.yml), commit `89173a3`, **SUCCESS** across Tk Python 3.10/3.13 and Kivy Python 3.11/3.13. See [P0 Tk/Kivy certification](P0_TK_KIVY_CERTIFICATION.md#screenshot-confirmed-green-native-matrix--2026-10-18). Initial tested Linux native teardown scenarios are now green, complementing PySide6 CI. Memory-soak (long duration, heap/weakrefs/retained resources), unsupported platform cells, clean multi-repository C05 resolver and explicit decision sign-off remain **OPEN**. Full P0→P1 Architecture Gate remains **BLOCKED**.


## P0.9 C07 memory soak instrumentation (2026-10-18)

[Long-duration soak protocol](P0_MEMORY_SOAK_PROTOCOL.md), [instrumentation script](../../scripts/p0_memory_soak.py), and [dedicated Actions matrix](../../.github/workflows/p0-memory-soak.yml) are now committed. The workflow supports 1k/5k/10k cycles per native renderer; sampling covers RSS, tracemalloc, live mounted instances, weakly tracked widget wrappers, and active event slots after pending-event/GC quiescence. **These are setup artifacts, not executed results.** Global P0→P1 Gate remains **BLOCKED** until genuine 1k/5k/10k measurements and clean full-ecosystem C05 install are reviewed.


## P0.9 1,000-cycle soak receipts (2026-10-18)

Owner supplied a green screenshot for P0 Memory Soak #8 (commit `1d6f1d4`) and actual three backend JSON artifacts; see [P0 Memory Soak Protocol — actual 1,000-cycle artifacts](P0_MEMORY_SOAK_PROTOCOL.md#p09-actual-1000-cycle-artifacts--owner-evidence-2026-10-18). All three jobs passed and all recorded PSX mounted instances, tracked native widget wrappers, and active event slots were zero at cycle 1,000. The Kivy series nevertheless showed RSS +5,885,952 B and Python-tracked memory +3,678,821 B between cycle 250 and 1,000; investigate warmed longer trend before closing memory stability. **1,000-cycle matrix GREEN; 5,000/10,000-cycle and C05 ecosystem wheel/install checks remain OPEN; full Architecture Gate BLOCKED.**


## P0.9 5,000-cycle native soak artifacts and Kivy allocation investigation

Owner uploaded three 5,000-cycle raw ZIP artifacts (run ID `39144005023`) for PySide6, Tkinter and Kivy; all contain complete 20-point series and zero tracked stale PSX instances, widget wrappers or active event slots. RSS after 250→5,000 cycles: PySide6 +1,949,696 B; Tkinter 0 B; **Kivy +49,426,432 B**, including +29,642,752 B over cycles 2,750→5,000. Kivy Python traced memory also increases +19,331,078 B over the full measured span; this needs attribution rather than premature certification. See [P0 Memory Soak Protocol](P0_MEMORY_SOAK_PROTOCOL.md#actual-5000-cycle-artifacts--owner-uploads-2026-10-18). A targeted [allocation-site trace workflow](../../.github/workflows/p0-kivy-allocation-trace.yml) is committed, but its results are **not yet verified**. Long-duration C07 still **OPEN**; the P0→P1 gate remains **BLOCKED**.


## P0.9 Kivy heap ownership and native A/B controls (2026-10-18)

Committed [Kivy heap ownership and direct-toolkit control protocol](P0_KIVY_HEAP_OWNERSHIP_PROTOCOL.md), [heap profiler](../../scripts/p0_kivy_heap_ownership.py), and [two-process GitHub Actions matrix](../../.github/workflows/p0-kivy-heap-ownership.yml). Fresh Python 3.13/Xvfb jobs compare real Velto/Cinnamon mount-update-unmount against approximate direct Kivy BoxLayout/Button event churn at 500/2,500/5,000 cycles. GC histograms and bounded referrer-type samples help identify possible retaining owners of previously measured Kivy allocations. **No new CI run or ownership result is yet verified.** No production Kivy or Cinnamon behavior changed. **C07 OPEN; Architecture Gate BLOCKED pending evidence and C05.**


## Owner decision: defer Kivy/SFLE memory; start isolated P1 groundwork (2026-10-18)

The owner explicitly elected to postpone the excessive memory growth observed during **Kivy + PSX/Cinnamon** mount/update/unmount stress testing, and to move forward with the next planned implementation phase. This is a **narrow waiver of immediate investigation**, not a claim that the issue was fixed, that native C07 passed, or that P0 was fully approved. Reproducible artifacts, measured deltas and the resumption protocol are recorded as **P2-MEM-KIVY-SFLE-01 (OPEN, HIGH)** in [P0.9 Closure Candidate](P0_9_CLOSURE_CANDIDATE.md).

The team has started **P1 IM-01 isolated, pure normalization scaffolding only** as documented in [P1 Phase 1 Canonical Box Baseline](P1_PHASE_1_CANONICAL_BOX_BASELINE.md), with no public API change or renderer/Cinnamon integration. **This does not mark the global P0→P1 approval gate as APPROVED.** AD-01–AD-12 remain without general ratification; C05 resolver evidence still required. Do not infer acceptance for an untested memory slope or use this specific deferral as a release-readiness waiver.


## Owner decision: universal box model and CSS Core (2026-10-18)

The project owner explicitly accepted the [universal box model and CSS Core architectural contract](universal-box-model-and-css-core-contract.md) in the project discussion on 2026-10-18. Accepted architectural direction: CSS Core inside PSX, Cinnamon as the sole geometry authority, legacy responsive Grid and GridItem preserved, separate future CSS Grid tracks, incremental invalidation, bounded caches and native capability certification.

This is approval of the architectural contract, **not approval of all outstanding detailed interface choices or the full global architecture gate**. Public styling syntax, exact per-tag sizing defaults, track algorithm details, native measurement ports, and remaining packaging/lifecycle/certification gates require their documented dispositions. Global gate status remains BLOCKED until its separately listed acceptance evidence is complete. No production implementation or test execution is implied by this entry.
