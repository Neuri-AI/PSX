# P0 Contract Review — Batch 3: Hot Reload, Cross-backend Certification, Documentation Closure

**Date:** 2026-10-18 · **Status:** STATIC REVIEW COMPLETE; OWNER APPROVAL AND CURRENT EXECUTION EVIDENCE PENDING  
**Decisions:** AD-10, AD-11, AD-12 · **Contract scope:** C10, C11, C12  
**Scope:** Planning and normative deltas only. F6 remains postponed pending Qyro coordination.

## AD-10 — Hot reload modes and Qyro ownership

**Sources:** [M8 hot reloading](../m8-hot-reloading.md), [PSX roadmap](../roadmap.md), [reconciliation](../../psx/core/reconcile.py), [Velto facade](https://github.com/Neuri-AI/Velto), [Qyro Engine](https://github.com/Neuri-AI/qyro), [Qyro CLI repo](https://github.com/Neuri-AI/Velto-CLI).

**Technical review: COMPLETE; approval: PENDING.** Existing watcher/process restart and limited component refresh vertical slice should be reused; no claim of complete hot reload. Conservative classification remains recommended:
- `FAST_REFRESH` only for provably compatible source changes with intact component identity, hooks and native handle contracts.
- `COMPONENT_REMOUNT` for known local incompatibilities only after native cleanup is certified.
- `PROCESS_RESTART` for bootstrap, native extension, incompatible third-party dependencies and changes that cannot be soundly classified.

Unknown changes default to restart, not unsafe reload. No `pickle` snapshots and no reloading native QObject or Kivy/Tk system modules opportunistically. The Qyro CLI and Engine may own different watch/supervision boundaries; inspect explicit launch commands before defining the final cross-repository contract.

**Open:** hook-signature compatibility algorithm; source/module classifier; guaranteed scope of snapshot restore; Qt/Tk/Kivy safe disposal on local remount; exact CLI entrypoint names. **Tests:** hook-order change, invalid imports, syntax recovery, repeated edits/observers, disabled frozen/production, real user app launched through Qyro. All remain execution tasks.

## AD-11 — Real cross-backend and performance certification

**Sources:** [F3 CI strategy](sfle-f3-ci-strategy.md), [capability policy](capability-certification-policy.md), [F1 final](sfle-f1-final-architecture.md), [F2 certification](sfle-f2-final-certification.md), [F4 Grid](responsive-grid-contract.md).

**Technical review: COMPLETE; approval: PENDING.** Maintain current F1/F2 pure 0.01 logical-pixel/native 1-pixel tolerances where specified; do not imply arbitrary text/theme native parity. Distinguish `supported`, `explicitly unsupported`, `not tested`, `executed pass`, `executed fail`, `waived with owner`.

**Recommended matrix:** `Python version × operating system × renderer family × component/feature × lifecycle`, with explicit Qt binding restrictions, Tk and Kivy native graphical evidence. The version constraints MUST be derived from installed metadata and actual CI source rather than user-memory snapshots.

**Core certification:** same-SHA pure Rust/Python differential, PSX parser/VNode/hook/reconciler, native geometry readback, owned/borrowed teardown, mounted Grid, packaged Velto + Pydux/Qyro facade, image/cache churn and long-running idle/resize soak. RSS alone is not a leak indicator.

**Open:** authoritative support matrix for Python/Qt family and Kivy OS cells; owners and baselines for memory thresholds; branch-protection checks and documented waiver workflow.

## AD-12 — F5.5 documentation state and release truth

**Sources:** [F5.5 contract](f5-5-public-documentation-contract.md), [F5.5 progress ledger](f5-5-public-documentation-progress.md), [roadmap](../roadmap.md).

**Technical review: COMPLETE; approval: PENDING.** Current F5.5 living ledger includes historical opening text that understates later completed gates, while its gate scoreboard reports G1–G5 closed and G6 in progress. Those are different sections of the same document. It would be incorrect to declare G6 closed solely from conversation history.

**Recommended resolution:** separate `public docs authored`, `CI evidence`, `independent beginner review`, and `owner signoff` into distinct tracked fields; correct obsolete *status captions* only after verifying authoritative gate evidence and no contradictory unreviewed docs. This task is not license to rewrite the user's manual page-by-page editorial process.

**Open:** exact G6 owner acceptance, immutable combined CI, manual page-by-page reviewer signoff, package-install reproducibility.

## Review completion and gate

| Decision | Source-backed review | Owner sign-off | Executed acceptance |
| --- | --- | --- | --- |
| AD-10 | COMPLETE | PENDING | NOT RUN this session |
| AD-11 | COMPLETE | PENDING | NOT RUN this session |
| AD-12 | COMPLETE | PENDING | NOT RUN this session |

**Across all batches: 12/12 AD decisions have a written static technical review (Batch 1 6 items; Batch 2 3 items; Batch 3 3 items). 0/12 owner-approved.** The draft C01–C12 contracts were already authored in [P0 deltas](P0_CONTRACT_DELTAS.md); this review does **not** indicate runtime contract certification.

**Next actionable work:** execute H-PKG-01, H-MEM-01, native tests and immutable SHA matrix; review/approve or defer AD items explicitly in [Architecture Gate](ARCHITECTURE_APPROVAL.md). P1 remains blocked.
