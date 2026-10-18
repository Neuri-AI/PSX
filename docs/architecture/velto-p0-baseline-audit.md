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
---

## 8. P0.2 — Expanded source-trace audit (2026-10-18)

**Audit reference:** PSX `develop` commit `847a08035d08d3d66c0bffd2b7df3743f938f5aa` (the previously published P0 initial report commit). PSX source files in this section were fetched using **this immutable ref**, not GitHub's default-branch code search. Related repositories were read at their default branches with per-file blob identities (cross-repository commit heads remain unpinned). No local checkout, actual execution of tests, GUI session, CI artifact download, or heap profiling was performed. Accordingly, this is a **substantial static code audit, not final runtime certification**. This distinction is binding for agents.

### 8.1 Evidence map — reconciliation and resources

| ID | Source (PSX at pinned ref) | Direct observation | Consequence |
| --- | --- | --- | --- |
| E-R01 | [`psx/core/reconcile.py` lines 151–179](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/reconcile.py#L151-L179) | Keyed children mapped by key; unkeyed by index; unmatched old children passed to `_unmount`. | Key stability/child removal implemented; mixed-list behavior and native lifetime must be tested. |
| E-R02 | [`psx/core/reconcile.py` lines 270–295](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/reconcile.py#L270-L295) | Event callbacks update via existing `EventSlot`; removal disposes slot, unbinds subscription and deletes map entry. | Explicit event-disposal machinery exists; adapters must actually disconnect. |
| E-R03 | [`psx/core/reconcile.py` lines 299–322](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/reconcile.py#L299-L322) | Unmount sets `disposed`, optionally detaches, disposes/unbinds events, clears refs, disposes hooks, recursively unmounts children in reverse order and calls renderer `destroy`. | Ownership contract should formalize ordering/error policy and test cleanup if a disposer raises. |
| E-R04 | [`psx/core/hooks.py` lines 127–133](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/hooks.py#L127-L133) | Effect cleanups run in reverse order; afterwards hooks list is cleared. | Cleanup **may raise**; neither this function nor `_unmount` uses an apparent per-disposer recovery/finally loop. This is a **risk requiring a deliberate fault-injection test**, not a demonstrated leak. |
| E-R05 | [`psx/core/scheduler.py`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/scheduler.py) | Dirty instances are coalesced in an identity dictionary, effect runners in a second dictionary; dictionaries clear during flush/effects. | Pending callbacks can temporarily retain instances; characterize shutdown/unmount behavior when the UI queue stops before draining. |
| E-R06 | [`tests/test_core.py`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/tests/test_core.py) and [`tests/test_hooks_scheduler.py`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/tests/test_hooks_scheduler.py) | Test functions cover keyed reorder/identity, duplicate keys, unbind/destroy once, batched updates, effect cleanup, ref reset, hook-order mismatch, worker scheduling and inert unmounted setter. | These are **test definitions**, not proof of a current passing run. |

**High-priority fault-injection hypothesis H-MEM-01:** if an effect cleanup or renderer event unbind raises during `Reconciler._unmount`, remaining native descendants may not be destroyed because the code continues sequentially without a finalization guard. Reproduce with a throwing disposer in Headless, then run native counterpart(s); decide and document whether failures should be aggregated, propagated after guaranteed cleanup, or treated as fatal. Never swallow exceptions silently.

### 8.2 Native renderer and layout audit

| ID | Source | Direct observation / gate |
| --- | --- | --- |
| E-N01 | [Qt renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/qt/pyqt.py#L662-L740) | `commit_layout` branches for Grid vs Flex/native bridge, retries stale semantic epochs up to 3 times; post-commit installs resize/semantic event filters; `invalidate_layout` cancels pending invalidations, clears intrinsic and image watches, and removes filters. |
| E-N02 | [Qt destroy and signal lifecycle](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/qt/pyqt.py#L892-L947) | Adapter delegates destruction; owned Qt widgets get `deleteLater()` when not released; signal callbacks are disconnected on unbind. Qt deferred delete event-loop flushing and borrowed-widget restoration still require native tests. |
| E-N03 | [Tkinter renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/tkinter/tkinter.py#L575-L660) | Layout uses corresponding native bridge and bounded epoch retries; invalidation unbinds theme/resize watchers, cancels pending `after` jobs and clears caches. |
| E-N04 | [Tkinter destroy](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/tkinter/tkinter.py#L869-L878) | Borrowed native widgets are skipped; owned existing widgets call `destroy()`. Native host state restoration is a separate proof obligation. |
| E-N05 | [Kivy renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/kivy/kivy.py#L565-L648) | Layout commit branches Grid vs Flex; watches root size and Window resize, invalidation cancels clock events, unbinds watchers and clears caches. |
| E-N06 | [Kivy widget destroy](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/kivy/kivy.py#L864-L893) | TextArea-specific binding is removed; optional spec destruction hook runs; borrowed widget is returned to original parent and previous size/pos hints are restored. |
| E-N07 | [SFLE native component capabilities](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/native_component_capabilities.py) | Native intrinsic capability lists exist for qt/tk/kivy; Kivy Slider requires explicit definite bounds. |
| E-N08 | [Qt layout bridge](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/qt_layout_bridge.py) | Bridge describes Qt sizeHint/heightForWidth measurement feeding pure SFLE computation and native rectangle projection. Full `sizeHint()` invalid-result branch test coverage has not been audited. |
| E-N09 | [Renderer adapters](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/adapters.py) and [adapter tests](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/tests/test_renderer_adapters.py) | Instance-scoped registry and lifecycle delegation with custom adapter mount/update/unmount test definitions exist. |

**Interpretation:** the earlier audit's C08 `UNVERIFIED` should now be upgraded to `PARTIAL`: concrete native invalidation state machines, cancellation and bounded retry are implemented across three major renderers. **This does not certify absence of resize loops.** All three renderers also have invalidation caches requiring retention/eviction instrumentation. Native 0-to-invalid hint policy, UI-thread measurement, and live widget counts remain unproven by execution.

### 8.3 Cinnamon computational contract

- [`psx/sfle/engine.py`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/engine.py) exposes a `PythonLayoutEngine.compute` invoking `compute_alpha.compute_snapshot`, a provisional computation method, and Grid computation. Do not describe it as a standalone public Cinnamon layer.
- [`psx/sfle/model.py`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/model.py) defines computational model types. Existing [F1 final contract](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/docs/architecture/sfle-f1-final-architecture.md) is normative for fixed-point 1/64 px and Python/Rust parity, but **actual Rust/Python parity test execution and feature-completeness remain unverified**.
- `psx/sfle/coordinator.py` does **not** exist at the inspected ref. Future agents must inventory real coordinator and bridge paths instead of inventing a module by that name.

### 8.4 Related repositories — direct package source inspection (heads not pinned)

| Repository | Files read | Concrete observations / cross-repository obligations |
| --- | --- | --- |
| [Neuri-AI/Velto](https://github.com/Neuri-AI/Velto) | `pyproject.toml`, `README.md`, `velto/__init__.py`, `velto/ui/__init__.py`, `velto/state/__init__.py`, `velto/runtime/__init__.py` | A real facade is present. It directly reexports `VeltoContext` from Qyro, PSX symbols in `velto.ui`, Pydux in `velto.state`, Qyro in `velto.runtime`. These are packages/directories, not `velto/ui.py` files. |
| [Neuri-AI/Pydux](https://github.com/Neuri-AI/Pydux) | `pyproject.toml`, `README.md` | Pydux distribution and optional PSX/Qyro integration are declared; subscription-unmount internals and live integration behavior still uninspected. |
| [Neuri-AI/qyro](https://github.com/Neuri-AI/qyro) | `pyproject.toml`, `README.md` | Qyro runtime is a separate distribution with broader Python version range; native toolkit version markers vary by backend. |
| [Neuri-AI/Velto-CLI](https://github.com/Neuri-AI/Velto-CLI) | `pyproject.toml`, `README.md` | This repository's metadata declares distribution/entry point `qyro-cli` / `qyro`; its README still describes Qyro CLI. Confirm canonical repo/branch and CLI hot-reload coordination before changing F6. |

**Cross-package blocker H-PKG-01: dependency constraints conflict in inspected metadata.**

- PSX repository `pyproject.toml` declares distribution `velto-core==0.1.0`, package `psx`.
- Velto facade `pyproject.toml` depends on **`psx>=1.0.0a1,<2.0.0`** and **`pydux[psx]>=1.0.0a1,<2.0.0`**.
- Pydux `pyproject.toml` defines extra `psx` with **`velto-core>=0.1.0,<1.0.0`**, and `qyro` extra with **`qyro-engine>=1.0.0a1,<2.0.0`**.
- Velto facade requires **`qyro-engine>=0.1.0,<0.2.0`** whereas the inspected Qyro runtime itself declares version **`1.0.0a1`**.

These manifest strings are directly observable and appear mutually incompatible **for a fresh dependency resolution using the repositories as currently inspected**. A fully reproduced resolver failure is **not asserted** (no install performed). This is a release/integration contract blocker for C05, C11, C12 and should be resolved with a compatible version strategy/CI install matrix before claims that `pip install velto` is functional across backends.

### 8.5 Snapshot of contract triage after P0.2 static pass

| Contract | Updated classification | Specific next proof |
| --- | --- | --- |
| C01 Universal Box Model | PARTIAL | Map ratified sizing semantics to executable box/overflow tests |
| C02 CSS-like Styling | PARTIAL | Verify whether cascade/inheritance/normalization exist; do not infer browser CSS |
| C03 Cinnamon Layout | PARTIAL | Rust/Python parity, fixed-point overflow, CSS geometry execution |
| C04 Renderer Adapter | PARTIAL | Lifecycle fault paths + native Qt/Tk/Kivy adapter exercise |
| C05 Component Compatibility | CONFLICTING (packaging/integration) | Align facade/runtime/distribution versions; preserve currently exported components |
| C06 Reconciliation & Identity | PARTIAL | Key churn + exception-safe cleanup + mixed keyed/unkeyed cases |
| C07 Memory Ownership | PARTIAL | Heap/widget/task/reference measurements; exception-in-disposal tests |
| C08 Layout Invalidation | PARTIAL (upgraded) | Native resize stress, event coalescing, idle/quiescence |
| C09 Native Measurement | PARTIAL | Invalid Qt hints, pre-mount, intrinsic image/text/scroll, DPI |
| C10 Hot Reload Lifecycle | PARTIAL | Supervisor/refresh/remount/restart, Qyro coordination |
| C11 Cross-backend Parity | UNVERIFIED | Native Python/OS/backend matrix + fresh install |
| C12 Testing & Certification | PARTIAL | Collect actual CI run URLs, rerun reproducible tests, soak benchmarks |

**Terminology clarification:** `CONFLICTING` on C05 applies specifically to **cross-repository dependency/distribution integration**, not evidence that `Button` or `Flex` broke.

### 8.6 Ready-to-run verification checklist for an agent with checked-out repositories

```bash
# In PSX checkout, after fetching:
git checkout develop
git pull --ff-only
git rev-parse HEAD
git ls-files > docs/architecture/p0-repository-file-inventory.txt
python -m pytest tests/test_core.py tests/test_hooks_scheduler.py tests/test_renderer_adapters.py -q
python -m pytest tests/ -q
python benchmarks/psx_benchmark.py --help

# Separate backend graphical/Qt/Kivy/Tk smoke suites MUST be selected
# from discovered existing tests/workflows and run in a suitable display environment.
# Do not publish a PASS unless the command actually ran.
```

Additional commands to execute in **isolated environments** (do not change lockfiles in the audit): install/test the `velto` facade against the explicit PSX, Pydux and Qyro distributions and compare resolver diagnostics to H-PKG-01; repeatedly mount/unmount 100–1000 component trees, pump Qt deferred-delete events, inspect QObject lifetimes, Tk widget existence, Kivy window bindings, scheduler dirty/effect queues and RSS + `tracemalloc`; stress repeated resize, font/theme/DPI changes, and intrinsic resource swaps.

### 8.7 Final P0 gate still blocked

This new evidence narrows the unknowns and identifies a concrete packaging/integration conflict, but it **does not finish the original P0.2 acceptance criteria**. Still missing: complete tracked-file tree; pinned heads for all related repos; execution of test and CI matrix; Pydux subscription teardown trace; Rust parity coverage; native stress/retention measurements; owner review of F5.5 G6 status and the F0–F8 web-like plan's actual location. Therefore **Contract Consolidation remains gated**. The next safe agent deliverable is a read-only executed-evidence addendum, followed by an existing-contract precedence index.
