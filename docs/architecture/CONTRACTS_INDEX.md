# P0.4 — Existing Contracts, Precedence, and C01–C12 Delta Index

**Version:** 0.1 (agent handoff) · **Date:** 2026-10-18  
**Status:** INVENTORY / NOT ARCHITECTURE APPROVAL  
**Branch:** `Neuri-AI/PSX:develop`  
**Execution authority:** Read-only analysis only until owner sign-off.

Read in order: [Master Execution Plan](velto-master-execution-plan.md) → [P0 Baseline](velto-p0-baseline-audit.md) → [P0 Verification Report](P0_VERIFICATION_REPORT.md) → this index.

## 1. Purpose and non-goals

This is the central navigation/decision index for existing architecture and proposed contracts **C01–C12**. It does not rewrite F1–F5/F5.5 specifications, certify passing tests, authorize changes in public API, or reinterpret historic designs as current code. The purpose is to prevent multiple agents from producing contradictory contracts or duplicating already-implemented mechanisms.

**Product language:** Velto uses **PSX Markup**. Cinnamon is a layout engine integrated within PSX. Pydux owns application state, Qyro Engine runtime lifecycle, Qyro CLI workflow/packaging; these are not interchangeable layers.

## 2. Evidence and precedence policy

When resolving a contradiction:

1. Inspect actual source and tests at an **immutable commit** in each affected repository. An implementation is evidence of behavior, **not automatic authority** to override an approved contract.
2. Identify the **latest explicitly owner-approved normative decision** for that exact area, including documented supersession dates/IDs. A later accepted decision can supersede an earlier one; do not assume document modification date equals decision approval.
3. Inspect current phase closure/capability certification receipts at exact source SHAs. An old `implementation not started` header cannot override later executed certification; conversely a plan's `CLOSED` label does not prove every behavior now passes.
4. Preserve existing exported components and public semantics unless an explicit later owner decision says otherwise. Removing legacy `Row`/`Column` from a historically targeted API does **not** imply permission to remove today's `Button`, `Text`, `Flex`, `Grid`, etc.
5. Escalate irreconcilable decisions in an ADR showing alternatives, migration cost, test impacts and requested approval. **No agent may silently choose one.**

Classifications:
- `EXISTING`: fully demonstrated implementation plus same-SHA behavioral evidence for **the proposed scope**.
- `PARTIAL`: ratified architecture or actual implementation exists, but new scope or certification remains.
- `MISSING`: absence demonstrated by complete inventory at pinned SHA, **not** failed filename search.
- `CONFLICTING`: directly contradictory normative records or cross-repository contracts, with concrete evidence.
- `UNVERIFIED`: insufficient evidence. Do not interpret as broken.

## 3. Existing normative source registry

| Registry ID | Existing document | Normative scope and decisions to preserve | Status nuance |
| --- | --- | --- | --- |
| N-F1 | [F1 final architecture](sfle-f1-final-architecture.md) | D-F1.1–D-F1.13, Flex-only public Flexbox, `snake_case`, 1/64px fixed-point, UI-thread measurement, Rust/Python contract and fail-closed semantics | Header preserves October 10 historical pre-F2 state; see later F2 ledger before interpreting current implementation. |
| N-F1B | [Ratified F1 box model/percentages](sfle-f1-box-model.md) | Four box regions, `box-sizing`, deferred percentage resolution, typed lengths, `layout_width` and `layout_height`, closed component/layout prop partition | Ratified *semantic* subset, **not** an automatic complete CSS cascade implementation. |
| N-F1C | [F1 contracts](sfle-f1-contracts.md) | Original Flex/measurement architecture and cross-references | Apply later superseding decision records when inconsistent. |
| H-F1 | [F1 props/lengths exploratory document](sfle-f1-props-lengths.md) | Historical rationale/alternatives; explicitly points to frozen F1B and F1 final for authority | Historical, not independent override. |
| N-F2 | [F2 implementation/exit ledger](sfle-f2-implementation.md) and [final certification](sfle-f2-final-certification.md) | Frozen alpha CSS feature subset, parity and geometry certification | Distinguish certified F2 subset from post-F2 deferred features. |
| N-F3 | [F3 native implementation](sfle-f3-implementation.md) and [CI strategy](sfle-f3-ci-strategy.md) | Qt, Tk, Kivy bridge/capability boundaries, UI-thread native measurement and intelligent impact selection | Status snippets in long historical ledgers must be resolved against most recent gate/CI receipts. |
| N-F4 | [Responsive 12-column Grid](responsive-grid-contract.md), [progress](responsive-grid-progress.md) | F4 `Grid`/`GridItem` is a twelve-column **Flexbox-based** grid, **not full CSS Grid**; signed-off behavior/props remain binding | Contract header says not implemented at contract approval; progress ledger contains subsequent implementation receipts. |
| N-CERT | [Capability certification policy](capability-certification-policy.md) | Every public capability needs functional tests, impact routing and public-behavior census | Applies to future modifications; no `documentation-only CI` change should accidentally run heavy suites. |
| N-F5.5 | [Public developer documentation contract](f5-5-public-documentation-contract.md), [progress ledger](f5-5-public-documentation-progress.md) | Beginner-first, page-by-page verified English docs, current code evidence, immutable SHA, canonical `docs/public/` | Ledger's G6 remains marked in progress pending actual owner/independent signoff evidence; do not mark closed based only on conversation recollection. |
| N-M8 | [M8 hot reload](../m8-hot-reloading.md) | Existing dev-only supervisor and limited compatible refresh; F6 deferred; Qyro coordination required | Not a blanket live-patching guarantee. |
| N-ROAD | [PSX roadmap](../roadmap.md) | Milestone tracking, deferred `aspect_ratio` and auto-wrap CSS extensions, Conventional Commit scopes | Status register/roadmap, **not** a replacement for normative contract contents. |
| N-P0 | [Master plan](velto-master-execution-plan.md) and [P0 baseline](velto-p0-baseline-audit.md) | Execution sequencing, evidence guardrails, planned new architecture scope | Coordination documents, **not yet approved normative runtime specifications**. |

## 4. Cross-repository implementation boundary

| Repository | Responsibility | Verified source pointers / unresolved |
| --- | --- | --- |
| [Neuri-AI/PSX](https://github.com/Neuri-AI/PSX) | PSX Markup, VNodes/hooks/reconciliation, embedded Cinnamon math/bridges, renderers | `psx/__init__.py`, `psx/core/reconcile.py`, `psx/sfle/`, `psx/renderers/`, tests |
| [Neuri-AI/Velto](https://github.com/Neuri-AI/Velto) | Facade `velto`, `velto.ui`, `velto.state`, `velto.runtime` | Module `__init__.py` reexports inspected; packaging version mismatch flagged H-PKG-01 |
| [Neuri-AI/Pydux](https://github.com/Neuri-AI/Pydux) | Store, reducers, selectors, subscription integration | Verify `StoreProvider` and `use_selector` unmount tests and versioned Pydux extras |
| [Neuri-AI/qyro](https://github.com/Neuri-AI/qyro) | `VeltoContext`, application runtime and native host integration | Verify startup/shutdown and resource ownership at pinned SHA |
| [Neuri-AI/Velto-CLI](https://github.com/Neuri-AI/Velto-CLI) | Currently declares Qyro CLI distribution and `qyro` entrypoint | Confirm canonical naming and F6 integration; no CLI redesign without approval |

These other repositories were inspected on their default branches at file level, **not fully pinned or tested**. Branch/release reconciliation is a requirement for Architecture Gate.

## 5. Proposed C01–C12 contract consolidation matrix

| ID | Proposed contract | Status after P0 source review | Reuse / authoritative baseline | Actual normative delta required |
| --- | --- | --- | --- | --- |
| **C01** | Universal Box Model | PARTIAL | N-F1B, N-F1, N-F2 | Define supported CSS-like extension set beyond ratified dimensions; clarify overflow/clipping, box nesting, intrinsic handling and versioned capability gates. |
| **C02** | CSS-like Style Resolution | PARTIAL | N-F1B closed props/typed lengths; component validators | Decide inline styles/stylesheet presence, precedence, inheritance scope, naming and unknown-property error behavior. **Do not assume full CSS cascade.** |
| **C03** | Cinnamon Layout | PARTIAL | N-F1, N-F2, N-F3, N-F4 | Extend frozen Flex/Grid math only where new box model requires it; define constraints and identical Rust/Python accepted/rejected cases. |
| **C04** | Renderer Adapter Lifecycle | PARTIAL | `psx/renderers/protocol.py`, `adapters.py`, Qt/Tk/Kivy renderers | Explicit begin/end ownership of create/measure/mount/update/detach/destroy; borrowed widget, errors and threading. |
| **C05** | Component/API Compatibility | **CONFLICTING** (distribution metadata, not demonstrated component breakage) | Public `psx/__init__.py`, facade reexports, N-F1 D-F1.10 | Versioned alias/migration rules, PascalCase/lowercase markup mapping, public compatibility matrix, resolve H-PKG-01. |
| **C06** | Reconciliation & Identity | PARTIAL | `core/reconcile.py`, `instance.py`, `hooks.py` | Mixed keys/fragment policy, fault-tolerant removal and rollback requirements, stale callback behavior. |
| **C07** | Memory Ownership | PARTIAL | C06 teardown, renderer native handles and hooks | Lifetime table (owner and cleanup responsibility), error-path cleanup, retained-cache limits, Pydux subscriptions, async cancellation, native memory tests. |
| **C08** | Layout Invalidation | PARTIAL | Three native renderers' `commit_layout`/`invalidate_layout` implementations | Normative epochs, dirty flags, callback coalescing, retry cap, quiescence and event-loop reentry. |
| **C09** | Native Measurement | PARTIAL | N-F1 D-F1.4/D-F1.12; native capabilities and bridge | Invalid `sizeHint()` vs legitimate zero, `ensurePolished` decisions, intrinsic image/text and DPI diagnostics. |
| **C10** | Hot Reload Lifecycle | PARTIAL | N-M8, devtools runtime | Formal compatible refresh/remount/restart classification, snapshot policy, Qyro CLI/Engine and memory/observer teardown. |
| **C11** | Cross-backend Parity | UNVERIFIED | N-F3, N-F4, N-CERT | Per-backend supported/unsupported matrix and geometry/lifetime observability; no false parity from headless tests. |
| **C12** | Testing & Certification | PARTIAL | N-CERT, N-F3 CI and N-F5.5 reproducibility rules | Unified executable conformance suite, official gate receipts and release scope / waivers policy. |

A status of PARTIAL indicates **work is needed on the new target contract**, not a measure of completed code or a claim that the old feature failed.

## 6. Decisions already frozen (do not reopen casually)

| Decision | Binding outcome | Source |
| --- | --- | --- |
| D-F1.10 | `Flex` is the public Flexbox primitive; previous `Row` and `Column` are removed from the target public API | N-F1 |
| D-F1.6 | Shared, closed prop partition; contextual flex-item metadata; single-root function component in initial scope | N-F1B |
| D-F1.7 | Typed CSS-like lengths; `layout_width`/`layout_height` namespaced sizing for compatibility; `calc()` deferred | N-F1B |
| D-F1.13 | Signed 1/64px saturating geometry with Python/Rust parity | N-F1 |
| F4 Grid | Twelve-column Flexbox-style Grid with explicit `GridItem`; no claim of full browser CSS Grid | N-F4 |
| Supported existing public components | Preserve and restructure `Text`, `Button`, `Flex`, `Grid`, etc.; no deletion as shortcut | Owner direction + N-P0 |
| PSX Markup | Markup is defining authoring language; expressions/keys/hooks follow actual parser and component contracts | N-P0 + PSX code |

## 7. Conflicts and unresolved policy questions

**X-01 — Package distribution graph (high, cross-repository).** Velto facade dependency ranges use `psx>=1.0.0a1` and `qyro-engine>=0.1,<0.2`, while PSX repository declares `velto-core==0.1.0`, Pydux source version `0.1.0` with optional `velto-core`, and Qyro runtime declares `1.0.0a1`. These are concrete source-manifest mismatches, but a real resolver result is pending. See [H-PKG-01 verification](P0_VERIFICATION_REPORT.md#2-h-pkg-01--dependency-resolver-compatibility).

**X-02 — Cleanup exception semantics (high).** `_unmount` follows sequential cleanup without an apparent `finally` for remaining descendants. Choose and approve an error propagation/aggregation strategy only after fault injection; preserve strong evidence on actual native effects. See [H-MEM-01](P0_VERIFICATION_REPORT.md#3-h-mem-01--error-path-unmount).

**X-03 — F5.5 status/ledger divergence (medium).** Progress scoreboard shows G6 in progress while prior owner conversations report a closed phase. Obtain immutable CI and owner sign-off rather than retroactively fabricating closure.

**X-04 — Old pre-implementation headers (medium).** F1 design sources say F2 not started and F4 contract says not implemented; later F2 certification / F4 progress evidence supersedes those *status snapshots*, **not frozen semantics**.

**X-05 — CSS-like scope creep (high).** The proposed new Web-like system must state explicitly whether stylesheets, cascade, inheritance, selectors, pseudo-states, CSS Grid and flex intrinsic-wrap are supported or deferred. `SFLE-CSS-01` aspect-ratio and `SFLE-CSS-02` auto-wrapping intrinsic sizing are already formally deferred in [roadmap](../roadmap.md), not implicitly included in P1.

**X-06 — Lowercase markup mapping (medium).** Existing PascalCase builders are preserved. Need a deterministic lowercase tag registry, naming/validation, collision policy and migration examples; these are design decisions for owner review, not behavior inferred from HTML.

## 8. Contract authorship template and issue/ADR protocol

**Each new delta contract MUST include:**

```text
ID / title / version / owner / status / decision date
Target repositories and exact immutable SHAs
Existing normative sources and explicit supersessions (if any)
Non-goals and capability matrix
MUST / MUST NOT / SHOULD invariants
Public API and internal boundary types, with error behavior
Lifetimes / threading / cleanup / performance concerns where relevant
Positive, negative and adversarial fixtures
Backward compatibility and migration behavior
Platform, Python and backend applicability
CI selection, acceptance tests and evidence receipt
Open questions / rejected alternatives / owner sign-off
```

Agents may draft **`PROPOSED`** deltas in `docs/architecture/contracts/` after the executed baseline; do not silently introduce new normative behavior by altering old signed contracts. Maintain explicit `supersedes:` links and unique decision IDs. Ensure any change to `scripts/ci/impact.py` is tested under N-CERT before shipping code.

## 9. Parallel-agent work and hard gates

| Parallel lane | Read-only deliverable | Depends on | Gate status |
| --- | --- | --- | --- |
| Lane A: verification | Execute H-PKG-01 resolver, H-MEM-01 fault injection, core tests and native lifecycle checks | Cloned/pinned repos + test environment | BLOCKED until executable evidence |
| Lane B: contract mapping | Map each C01–C12 clause to ratified N-* paragraph and implementation symbol; inventory F0–F8 owner-approved roadmap source | This index + canonical source | OPEN for read-only analysis |
| Lane C: certification | Map test suites, CI selector, relevant workflows and historical receipts; run same-SHA current matrix | Pinned sources + CI access | BLOCKED for pass claims |
| Lane D: integration | Cross-repo pyproject/packaging contract and facade tests; propose version resolutions without editing | Lane A resolver result | BLOCKED for implementation |

**Architecture Gate remains BLOCKED.** Final sign-off needs (1) reproducible test evidence, (2) canonical version compatibility, (3) decisions on X-01/X-02/X-05/X-06, (4) approved delta specifications with conformance tests, and (5) an owner-signed `ARCHITECTURE_APPROVAL.md`. Until then, P1 changes to cross-cutting APIs are not authorized.

## 10. Next controlled artifact

After Lane A and the complete contract-to-source mapping, publish a versioned `P0_CONTRACT_DELTAS.md` or individual C01–C12 deltas with unresolved alternatives explicitly presented for owner approval. Do **not** manufacture twelve replacement contracts when existing F1–F4 agreements can be linked and extended.


## 11. P0.5/P0.6 published handoff (2026-10-18)

- [C01–C12 proposed normative deltas](P0_CONTRACT_DELTAS.md): proposed clauses, conformance vectors, open decisions AD-01–AD-12; **not owner-ratified**.
- [Architecture Gate and approval record](ARCHITECTURE_APPROVAL.md): **BLOCKED** pending executed verification and sign-off. Never treat a published gate form as its own approval.

Existing F1–F4 decisions remain binding. Continue evidence collection under [P0 Verification Report](P0_VERIFICATION_REPORT.md) before production changes.


## 12. Owner-ready decision packet

The [P0 owner decision package](P0_OWNER_DECISION_PACKAGE.md) maps AD-01–AD-12 to source evidence, recommended bounded alternatives, compatibility impacts and acceptance tests. **Recommendations are not ratification.** Dependency version arithmetic has been checked offline, but clean resolver/native gates stay open.

 
## P0 contract review progress — 2026-10-18

**Source-backed technical reviews completed: 12/12 decisions (AD-01–AD-12). Owner approvals: 0/12. Executed full test/CI closure: pending.** This is a review metric, **not** acceptance/certification of C01–C12 or release readiness.

- [Batch 1 — public semantics and compatibility](P0_CONTRACT_REVIEW_BATCH_1.md): AD-01/02/03/04/06/08
- [Batch 2 — safety and packaging](P0_CONTRACT_REVIEW_BATCH_2.md): AD-05/07/09
- [Batch 3 — hot reload and certification](P0_CONTRACT_REVIEW_BATCH_3.md): AD-10/11/12

**Blocking gates unchanged:** H-PKG-01 actual resolver, H-MEM-01 teardown fault-injection, native/Python/Rust same-SHA matrix, and explicit owner decisions. P1 implementation **NOT AUTHORIZED**.
