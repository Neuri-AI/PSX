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
