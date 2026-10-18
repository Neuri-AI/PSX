# Velto — P0 Baseline Repository Audit

**Date:** 2026-10-18  
**Status:** INITIAL READ-ONLY AUDIT — NOT CERTIFIED  
**Primary repository:** `Neuri-AI/PSX`  
**Branch inspected:** `develop` (file-by-file reads; branch head commit not pinned)  
**Purpose:** Evidence-led input for contract consolidation, *not* authorization to implement.

## 1. Scope and methodological limits

This pass inspected targeted source files and architectural documents using the GitHub connector, rather than cloning and executing the complete repository. File-level blob SHAs were retrieved for some files, but an immutable `develop` branch-head SHA and a complete tree inventory were not obtained. GitHub code-search results were indexed against `main` and must **not** be mistaken for evidence of `develop`. No unit tests, native integration tests, benchmarks, resource profiling, or CI workflow runs were executed. No claim of full compliance is made.

Before certification, an agent must clone/fetch `develop`, pin `git rev-parse HEAD`, obtain a full inventory, review dependencies and test logs, and repeat checks against the pinned commit.

## 2. Verified source inventory (develop)

| Subject | File / evidence | Observed |
|---|---|---|
| Public API | [`psx/__init__.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/__init__.py) | Exports Flex, Grid, GridItem, key primitives, hooks, Native, plugin APIs; no Row/Column exports in inspected file. |
| Distribution | [`pyproject.toml`](https://github.com/Neuri-AI/PSX/blob/develop/pyproject.toml) | Distribution named `velto-core`, package includes `psx`; `>=3.10,<3.14`; optional Qt/Kivy backends. |
| Reconciliation | [`psx/core/reconcile.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/core/reconcile.py) | Render/update/unmount; native handle creation; prop deltas; event synchronization; commits layout and effects. |
| Mounted identity | [`psx/core/instance.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/core/instance.py) | Parent, children, handle, hooks, event slots, attached/disposed, one-root `native_handle()` invariant. |
| Hooks | [`psx/core/hooks.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/core/hooks.py) | Hook slots and order verification; state setters ignore disposed instances. |
| Renderer boundary | [`psx/renderers/protocol.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/renderers/protocol.py) | Create/update/insert/move/remove/event bind/unbind/destroy/schedule_ui/run. Measurement and layout commits are not required by this base protocol. |
| Qt rendering | [`psx/renderers/qt/pyqt.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/renderers/qt/pyqt.py) | QtHandle and event subscriptions; layout/native integration machinery. Complete teardown needs further review. |
| Native intrinsic policy | [`psx/sfle/native_component_capabilities.py`](https://github.com/Neuri-AI/PSX/blob/develop/psx/sfle/native_component_capabilities.py) | Explicit Qt/Tk/Kivy support sets and intrinsic measurement policy; Kivy Slider requires definite pixel sizes. |
| Architecture | [`docs/architecture/sfle-f1-final-architecture.md`](https://github.com/Neuri-AI/PSX/blob/develop/docs/architecture/sfle-f1-final-architecture.md) | Approved design includes fixed-point 1/64px, UI-thread measurement, strict compatibility diagnostics and removal of Row/Column. Contains historical 'F2 not started' text. |
| Box model | [`docs/architecture/sfle-f1-box-model.md`](https://github.com/Neuri-AI/PSX/blob/develop/docs/architecture/sfle-f1-box-model.md) | Ratified typed sizes, percentages, content/padding/border/margin, `box-sizing` and namespaced `layout_width`/`layout_height`; `calc()` deferred in original design. |
| Hot reload | [`docs/m8-hot-reloading.md`](https://github.com/Neuri-AI/PSX/blob/develop/docs/m8-hot-reloading.md) | Existing supervisor and selective component reload slice; remaining F6 work postponed, contingent on Qyro work. |
| Documentation contract | [`docs/architecture/f5-5-public-documentation-contract.md`](https://github.com/Neuri-AI/PSX/blob/develop/docs/architecture/f5-5-public-documentation-contract.md) | Requires SHA-pinned sources, reproducible examples and code-grounded claims. |
| Documentation ledger | [`docs/architecture/f5-5-public-documentation-progress.md`](https://github.com/Neuri-AI/PSX/blob/develop/docs/architecture/f5-5-public-documentation-progress.md) | Internal scoreboard says G1–G5 closed, G6 in progress; requires status reconciliation. |
| README | [`README.md`](https://github.com/Neuri-AI/PSX/blob/develop/README.md) | Contains historical API examples/terminology, inconsistent with target public Velto naming; not safe to treat as canonical. |

## 3. High-impact findings and contract consequences

### P0-F01 — Pre-existing box-model contract (high)
C01 (Universal Box Model) and C02 (CSS-like styling) cannot be designed as clean-room replacements. D-F1.6 / D-F1.7 already ratify dimensional typing and percentage reference rules. **Action:** map each proposed style property to an existing normative decision or a genuine gap; record supersessions explicitly.

### P0-F02 — Public-API compatibility boundaries (critical)
F1 approved removing Row and Column from the *target* API, while the new owner instruction preserves the **existing public components** including Button, Text, Flex and Grid. The inspected `psx/__init__.py` exports Flex/Grid but not Row/Column. **Action:** distinguish historical removed APIs from currently exported supported APIs; preserving existing components does not automatically reintroduce retired Row/Column.

### P0-F03 — Ownership and teardown exist, but are not certified (critical)
`MountedInstance` stores hook slots, event slots, native handles and references. `Reconciler.unmount()` and renderer `destroy()` exist. **Action:** trace all teardown paths, signal disconnections, callback capture lifetimes, Qt `deleteLater`, Tk destroy, Kivy removal, detached widgets, caches and hot-reload closures. Instrument live/native counts and RSS. No leak or no-leak assertion is currently substantiated.

### P0-F04 — Native measurement and invalidation need an end-to-end trace (critical)
The native-leaf policy explicitly governs which widgets need intrinsic measurement. The general renderer protocol does not mandate a `measure` method. **Action:** trace the actual SFLE coordinator, Qt `sizeHint`/`minimumSizeHint`/`ensurePolished`, Tk and Kivy size ports, pre-mount behavior, invalidation queues, fixed-point conversion, feedback-loop protection and geometry readback tests.

### P0-F05 — F6 is partially implemented (high)
M8 documents an existing supervisor and component refresh mechanism, with explicit omissions such as broad module reload and snapshot restore. **Action:** audit its code and tests before specifying refresh tiers; classify each tier as already supported, limited, or unimplemented. Qyro CLI and Engine dependencies must be reviewed separately.

### P0-F06 — Documentation status contradictions (medium)
The F5.5 ledger states G6 is in progress while previous project discussions described closure. Some F1 contract headers describe implementation as not started although later code exists. **Action:** obtain owner signoff/CI artifacts and timestamped branch SHA, then revise status in one canonical register. Do not change status merely to match conversation claims.

### P0-F07 — Canonical packaging/import path requires reconciliation (high)
`pyproject.toml` declares `velto-core` and package `psx`; `psx/__init__.py` is present. The broader Velto facade (`velto`, `velto.ui`, `velto.state`, `velto.runtime`) must be inspected in the proper related repository/branch before making release claims. **Action:** verify distributions, importable modules, optional dependencies and CLI commands with install tests.

## 4. Preliminary C01–C12 baseline matrix

**Classification semantics:** `EXISTING` = demonstrated complete implementation and tests; `PARTIAL` = concrete pre-existing design/code but unverified coverage; `MISSING` = proven absent after full inventory; `CONFLICTING` = incompatible source or normative declarations; `UNVERIFIED` = insufficient inspected evidence.

| ID | Contract | Provisional state | Evidence / unresolved work |
|---|---|---|---|
| C01 | Universal Box Model | PARTIAL | Ratified F1.6/F1.7 semantics; verify implementation and CSS-like expansion. |
| C02 | CSS-like Styling | PARTIAL | Typed-length and metadata decisions; style cascade/inheritance/precedence not audited. |
| C03 | Cinnamon Layout | PARTIAL | Fixed-point math and layout integration referenced; full parity unverified. |
| C04 | Renderer Adapter | PARTIAL | Protocol and Qt implementation found; Tk/Kivy and teardown parity unverified. |
| C05 | Component Compatibility | PARTIAL | Public exports and explicit F1 removal decision; migration policy needs approval. |
| C06 | Reconciliation & Identity | PARTIAL | Concrete Reconciler/MountedInstance/hooks; keyed and failure-path tests not yet read. |
| C07 | Memory Ownership | PARTIAL | Teardown mechanisms present; no live retention profiling conducted. |
| C08 | Layout Invalidation | UNVERIFIED | Need SFLE coordinator inspection, queue tests and reentrant resize testing. |
| C09 | Native Measurement | PARTIAL | Native capabilities policy present; UI-thread measurement paths unverified. |
| C10 | Hot Reload Lifecycle | PARTIAL | Existing M8 slice, F6 outstanding. |
| C11 | Cross-backend Parity | UNVERIFIED | No cross-platform matrix/CI evidence executed or retrieved. |
| C12 | Testing & Certification | PARTIAL | Historical gates and expected checks exist; current runs not retrieved. |

**Important:** `PARTIAL` here does not mean feature completeness percentage. The matrix is a triage index for the next audit pass, not a release certification.

## 5. Remaining mandatory P0 audit work (before Contract Closure)

1. Pin exact `develop` HEAD SHA and take a complete tree inventory including docs/roadmap, test suites, GitHub Actions and all architectural specifications.
2. Inspect SFLE/Cinnamon engine and coordinator; map numerical semantics to actual tests and Rust/Python parity.
3. Trace full reconciler `_unmount`, `_reconcile_children`, scheduler/effect cleanup and native ref lifecycle; test keyed mutations and remounts.
4. Inspect Qt, Tkinter and Kivy native measure/create/update/unmount/destroy paths and test coverage.
5. Trace invalidation triggers from props/font/theme/dpi/window resize; inspect feedback protection and scheduling behavior.
6. Audit cache ownership, weak/strong references, snapshots, image resources, event bindings and application-shutdown disposal; run allocation/RSS stress benchmarks in native modes.
7. Inspect actual `velto` facade, Qyro CLI, Qyro Engine and Pydux repositories. Pin their respective SHAs and identify cross-repository contracts.
8. Resolve roadmap and G6 completion-status divergence with direct CI results and owner approvals.
9. Produce a versioned API census and existing-contract index showing precedence/supersession.
10. Only then draft C01–C12 normative delta specifications and seek Architecture Gate approval.

## 6. Agent execution guardrails

- Read-only audit until the owner approves the contract consolidation.
- Never claim all contracts closed based on architecture documents alone.
- Prefer source and behavioral tests on an immutable SHA over prior conversation and old docs.
- Preserve the existing public component API; do not revive historically removed APIs without an explicit decision.
- Treat `markup` as the product's defining authoring language; avoid relabeling Velto as primarily 'declarative'.
- Report exact evidence location, proposed change, backward-compatibility impact and test requirement per finding.
- Keep 'unverified' separate from 'missing' and 'failing'.

## 7. Next gate

**Next:** `P0-02 — Evidence Completion and Contract Inventory`. The current report is suitable to direct agents' inspection, but **not** sufficient to authorize contract closure or implementation. Once complete, produce `CONTRACTS_INDEX.md`, contract-specific delta specs C01–C12 and `ARCHITECTURE_APPROVAL.md` for owner signoff.