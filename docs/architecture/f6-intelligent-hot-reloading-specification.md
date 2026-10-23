# F6 — Intelligent Hot Reloading: approved architectural requirements

**Decision date:** 2026-10-17. **Status:** P3 functional exit gate satisfied with executed backend-qualified native and supervisor evidence on 2026-10-23; broader platform/Python matrix, long-duration resource soaks and release validation belong to P4. **Milestone:** M8. This file is the canonical cross-repository architecture specification and records separately sourced execution evidence.

## 1. Core contract

Hot Reloading MUST choose the least disruptive **safe** update based on actual impact, not merely changed filename. Priority: **Level 1 → Level 2 → Level 3**. A failed update MUST NOT leave a partially rebound, inconsistent native runtime. The supervisor SHOULD preserve the last working UI when safely possible, with diagnostics and recovery.

- **Level 1 — Fast Refresh:** rebind compatible changed code; selectively re-evaluate affected component boundaries, reconcile affected VNodes, update only changed native widgets/props and invalidate only affected Cinnamon layout/style regions. Preserve compatible hook state and component identities. Examples: markup/text, CSS-like styles/theme values, callbacks, compatible component logic, local module functions, new safely loadable imports.
- **Level 2 — Component Remount:** when in-process code is loadable but hook signature, component identity or native widget lifecycle is incompatible with state reuse, clean up effects/resources and remount the smallest safe affected component boundary/subtree. Keep the application process, native window and unaffected component state alive. Adding, removing, reordering or changing hook kinds MUST NOT, by itself, force process restart. A remounted boundary may reset its own local state.
- **Level 3 — Process Restart:** last resort for changes that cannot safely be incorporated into the existing interpreter/runtime, e.g. changing the Qt/Kivy backend or fundamental native event-loop bootstrap, replacing already loaded incompatible binary extensions, changing interpreter, or non-reinitializable global resources. Attempt safe registered snapshot restore when configured. Report the specific restart reason. Changing `main.py` or adding an import is NOT, by itself, sufficient reason to restart.

A changed parent may invalidate descendants; a globally used style variable may invalidate many nodes. **Selective** means update all actually affected boundaries, not necessarily a small fixed number. Distinguish Python module reload, component re-evaluation, VNode reconciliation, native widget patching and incremental Cinnamon layout invalidation.

## 2. Dependency/import handling

New imports of already installed third-party libraries (e.g. `import pandas as pd`) SHOULD be loadable within the current process when safe, including a first import of a library with native extensions. This is different from hot-reloading a third-party module or replacing an already-loaded native binary. Track project-local import dependencies, including `from module import symbol` rebinding, and propagate invalidation selectively. Do not blindly reload third-party modules, native extensions or stateful global singletons. Unsafe global initialization or bootstrap changes escalate only when needed.

## 3. Configuration and CLI

Canonical project-specific development configuration: `settings/development.json`, applied only when running from source in development mode. Existing `hot_reload` settings in `settings/base.json` remain valid for backwards compatibility. When implementing the configuration loader, merge configuration in the order **base → platform → development**, recursively within `hot_reload`; then apply command-line disabling and the unconditional frozen-mode prohibition. The Engine's existing shallow merge and the CLI's existing deep merge must be reconciled before activation. This precedence and profile are design targets, not current supported behavior.

Minimal recommended configuration:

```json
{
  "hot_reload": {
    "enabled": true
  }
}
```

Proposed extended schema (new fields are F6 targets, not currently certified):

```json
{
  "hot_reload": {
    "enabled": true,
    "strategy": "auto",
    "granularity": "component",
    "preserve_state": true,
    "fallback": "restart",
    "debounce_ms": 150,
    "watch": ["components/", "views/", "styles/", "resources/"],
    "ignore": [".venv/", "__pycache__/", "build/", "dist/"],
    "module_reload": {
      "include": ["app.*", "components.*", "services.*"],
      "exclude": ["PySide6.*", "numpy.*"],
      "third_party": "safe_import"
    },
    "state": {
      "remount_on_hook_change": true,
      "snapshot_on_restart": true,
      "restore_on_restart": true
    },
    "diagnostics": {
      "enabled": true,
      "log_level": "info",
      "show_errors": true
    }
  }
}
```

`strategy: "auto"` MUST select the least disruptive safe level. `granularity: "component"` prioritizes affected component boundaries, not a guarantee of constant-size invalidation. `preserve_state` applies only to compatible state; incompatible hooks remount. `module_reload.third_party: "safe_import"` permits safe first imports, NOT arbitrary third-party reload. `fallback: "restart"` is a safety policy, not a preference to restart for every change. `watch` adds/scopes observed project paths, while the application entry point remains monitored. Existing M8 `third_party: "restart"` and other current configuration values must be handled compatibly; a migration/default policy requires explicit validation. `ignore` must not allow watching virtual environments or generated output accidentally. Snapshot restore is opt-in, versioned, bounded, JSON-safe and limited to explicitly registered application state; never serialize widgets, closures, credentials, sockets, threads or native handles.

Target developer workflow: `velto start` enables hot reload in development when configured; `velto start --no-hot-reload` disables it for that invocation. Exact CLI implementation and flag names must be reconciled with Velto/Qyro CLI before certification. No manual watcher import in application code.

## 4. Cross-repository ownership and coordination

- **Velto CLI** owns the developer command, workspace watching, change coalescing, child-process supervision and restart requests; it must not mutate native widgets.
- **Qyro Engine** owns runtime mode and frozen detection, application lifecycle and coordination with the running `VeltoContext` instance; it must not duplicate the supervisor.
- **PSX** owns component identity/hook-compatibility decisions, reconciliation, selective Cinnamon invalidation, native UI-thread mutations and clean remounts.
- **Pydux** owns store/subscription lifetime and explicitly registered compatible state snapshots, not process or native-widget management.
- **Velto facade** needs no new coordinator at this stage.

Coordination should exchange versioned, correlated change notifications, classification decisions and outcomes, with semantic outcomes such as `fast_refresh`, `component_remount`, `process_restart`, and `no_action`. Record a concrete reason for escalation and refuse stale/out-of-order updates. Serialization must remain restricted to bounded JSON-safe state. Transport selection, handshake implementation and executable validation belong to the implementation stages.

**Canonical documentation and design decisions remain in PSX.** Runtime changes and repository-specific tests belong to whichever repository owns the behavior; do not copy architecture documents, test contracts or certification workflows into the other repositories simply to synchronize planning.

## 5. Frozen-mode invariant — mandatory

**If the application is frozen, hot reload MUST be completely disabled, without exception**, regardless of `hot_reload.enabled`, CLI flags or programmatic requests. Frozen status takes precedence over every user configuration and is checked before constructing a watcher, supervisor, module reloader, hot-reload-only snapshot service or other hot-reload machinery. Frozen applications MUST NOT spawn watcher threads, perform code refresh or accept later attempts to enable it. `enabled: true` in frozen mode MUST NOT itself cause an application error. Use Qyro runtime frozen detection when available, with backend-independent equivalent detection for other supported packagers. Frozen-mode prohibition is unconditional; non-frozen production should also disable hot reload by default.

Effective activation invariant: `effective_enabled = configured_enabled and development_mode and not is_frozen`; frozen always wins.

## 6. Acceptance and certification targets

Implementation is planned as seven internal stages, from shared architecture through integrated native certification. Future certification MUST cover: three-level classification and minimal safe escalation; changed hooks remount without process restart; selective component/VNode/native widget updates; compatible state preservation; first import of installed `pandas` without automatic restart; entry-point edits classified by actual impact; safe module rebinding; snapshot validation and restoration; diagnostics and recovery after syntax errors; `settings/base.json` compatibility; CLI launch/disable behavior; and **frozen mode always OFF**, including when config and flags request ON. Validate across supported Qt, Tkinter and Kivy backends, with actual executed evidence. Do not claim any of these targets are already implemented solely because they are specified.

## 7. Existing baseline and scope boundary

Current M8 baseline: `psx.devtools` watcher/debounce/process restart, constrained `ComponentRefreshManager`, local import discovery, and opt-in JSON snapshot registry. Current implementation may restart for hook-structure or bootstrap edits and is more conservative about third-party imports. Those behaviors are **baseline limitations to replace in F6**, not approved target behavior. See [M8 baseline](../m8-hot-reloading.md) and [roadmap](../roadmap.md).

## 8. Verified integration inventory and migration boundaries

This inventory was checked against actual repository source before implementation. It is not a statement that cross-repository coordination already works.

| Owner | Verified current integration point | Missing work or compatibility hazard |
| --- | --- | --- |
| Velto CLI (`release`) | `velto_cli/cmdline/commands/start.py` calls `RunApplicationUseCase.execute()`; `velto_cli/application/use_cases/start.py` resolves the entry and invokes `AppRunnerPort.run_from_source`; `velto_cli/adapters/process/runners.py` executes the child with `PSX_SOURCE_ENTRY` after preparing inline PSX Markup. | No coordinated refresh transport or declared `--no-hot-reload` option at these entry points. Alter the existing use-case, runner port and CLI command, not an unrelated coordinator or duplicate launcher. |
| Velto CLI settings | `SettingsRepository` in `velto_cli/adapters/persistence/storage.py` reads `settings/base.json` and applies explicit platform/profile files via recursive `_deep_merge`. Secrets are reapplied at highest precedence. | `development.json` must be explicitly activated for source development; never rely on implicit discovery. Do not repurpose `build.json` or override release/signing behavior. |
| Qyro Engine (`release`) | `JsonSettingsAdapter.get_raw_settings()` reads `base.json`, applies a single recognized platform JSON with shallow top-level `dict.update`, and then processes secrets. `VeltoContext.app_settings` exposes those settings and `VeltoContext.is_frozen` reads boot metadata. | A shallow override currently replaces a whole `hot_reload` object. Implement a narrowly scoped recursive merge with identical source-profile precedence; ensure source-vs-frozen context is known **before** any development services are allocated. |
| Qyro Engine application lifecycle | `VeltoContext.mount()` creates the backend-specific renderer, wraps the PSX root in `StoreProvider` when a Pydux-compatible store is present, mounts `App`, then presents native Qt/Tk/Kivy widgets. `unmount()` delegates to `App.unmount()`. | Coordinate with the existing application instance. UI-thread dispatch and mount/remount boundaries cannot be implemented safely by directly mutating widgets from CLI's file-watching thread. |
| PSX (`feature/intelligent-hot-reload`) | `psx/devtools/qyro_reload.py` already has `QyroComponentReloader`, imports/project discovery, `schedule_ui` and hook-error remount; `psx/devtools/config.py` checks frozen mode. `psx/devtools/state.py` offers explicitly registered JSON snapshots with size limits. | Existing M8 watcher/process supervisor overlaps proposed CLI ownership; migrate responsibilities without running two watchers or two process supervisors. Ensure stale work cancellation, safe transactional code swap, selective boundaries and rollback. |
| Pydux (`main`) | `pydux/core/store.py` has `Store.get_state`, `dispatch`, `select` and unsubscribe closures protected by its `RLock`; the existing Qyro context discovers stores and provides them to PSX. | First preserve a compatible store object across refresh by not replacing it. Native store serialization or automatic store recreation is **not** required for in-process refresh. Restart snapshot integration must be explicit, registered, validated and defer to application-defined reducers/restorers. |

### Concrete lifecycle and protocol ownership

1. **CLI is the single workspace watcher and child-process supervisor.** It starts from the existing `velto start` code path and communicates source changes to the running development application; it alone may request a child-process restart. PSX's existing development watcher is a migration input, not a second watcher left running. The child still owns the only toolkit event loop.
2. **Qyro is the runtime boundary.** It verifies mode/frozen status, associates each request with the currently mounted `VeltoContext` generation, and delegates safe UI classifications and mutations to PSX. Signals and queues must not run native UI code on the watcher thread.
3. **PSX owns UI update decisions and application of compatible updates.** It evaluates source and dependency impact against component identity and hook signature, stages candidate changes, and applies only on the native UI thread. A rejected candidate leaves the prior committed tree and render callable intact. If safe in-process recovery fails, it returns an explicit escalation reason to the coordinator.
4. **Pydux owns store state and subscription correctness.** In-process updates retain the same Store where compatible, while unmounted component subscriptions are released. Cross-process state export is optional and must be application-registered rather than attempted by snapshotting every store.

### Correlated coordination messages (design contract, not implemented transport)

A message envelope consists of `version` (integer, initially `1`), `request_id` (unique within a running supervisor session), `kind` (`change`, `decision`, `result`), and the relevant data. `change` includes normalized project-relative changed paths and the current generation. `decision` includes an action (`fast_refresh`, `component_remount`, `process_restart`, `no_action`), a concrete reason, affected module/component identifiers where known and whether eligible state can be retained. `result` includes success/failure/rejection plus whether the previous UI was preserved. Invalid version, wrong session, stale generation, duplicate request, malformed payload, or paths escaping the project root must **fail closed** without applying to widgets.

**Reason taxonomy:** `compatible_source_change`, `style_change`, `hook_signature_changed`, `component_identity_changed`, `native_widget_incompatible`, `backend_changed`, `runtime_bootstrap_changed`, `loaded_native_extension_changed`, `unsafe_global_initialization`, `source_validation_failed`, `unavailable_dependency`, `stale_request`, `development_disabled` and `frozen_runtime`. The taxonomy is descriptive and can be extended compatibly, but unknown codes never authorize escalation or widget mutations. Exact transport encoding, acknowledgment and bounded buffering are implementation decisions for the supervision increment, not public API commitments today.

### Classification decision table

| Observed change | Lowest safe target | Preservation / handling |
| --- | --- | --- |
| Compatible markup, text, callback or component body | Fast Refresh | Reevaluate affected component boundaries; retain hook and native widget identity when valid |
| CSS stylesheet or global variable used by mounted nodes | Fast Refresh | Invalidate all affected style/layout contexts, not a fixed number of nodes; independent contexts remain intact |
| Local module function and `from module import symbol` | Fast Refresh when safely rebindable | Update dependent project-owned consumers; reject in-place update if non-reinitializable globals make it unsafe |
| First import of installed third-party dependency, including `pandas` | Fast Refresh if safe to load | Loading a previously unimported extension is not replacing an already loaded native binary |
| Add/remove/reorder/change kind of hooks | Component Remount | Unmount smallest safe boundary, clean effects and subscriptions, reset only incompatible local state |
| Component type/key/native widget contract incompatible with reuse | Component Remount | Keep unaffected parent window and independent components; close replaced handles |
| Source syntax error / invalid markup candidate | No application, report failure | Keep last committed UI, continue watching for corrected save |
| Application entry file changes compatible render logic | Fast Refresh or Component Remount | Entry filename alone is not justification for process restart |
| Backend selection, interpreter or native event-loop bootstrap changes | Process Restart | Cleanly terminate child and recreate under supervisor; restore only compatible registered state |
| Already-loaded incompatible native binary replacement | Process Restart | Do not attempt unsafe in-process reload of binary modules |
| Frozen or production execution | No action | No watcher, IPC refresh bridge or restart-on-source-change service may be started |

### Configuration merge and safety rules

- Source development: read `settings/base.json`, then the host platform profile, and finally `settings/development.json`; merge nested objects recursively, including `hot_reload`. Scalars/lists replace earlier values. CLI invocation disable has precedence over all JSON configuration. The **effective activation** additionally requires development mode and non-frozen runtime; frozen prohibition is absolute.
- Existing `base.json` values work without duplicating them in `development.json`. Project-local development settings are never treated as production overrides. `settings/release.json`, `settings/sign.json`, and `settings/secrets.json` retain their existing build, signing and protected-data responsibilities and are **not** merged into hot reload configuration merely to make the feature work.
- A missing development profile is valid; malformed or non-object explicit development settings must yield actionable development diagnostics, not silently activate a watcher. `hot_reload.enabled` must have a well-defined boolean value, with a conservative OFF default when no explicit project or developer opt-in exists.
- Watch paths are project-relative, normalized and guarded against traversal/symlink escape. Ignore `.git`, virtual environments, editor temporary files, caches, build and distribution directories. Always monitor the authored entry file, not only a temporary PSX-transformed copy.
- `strategy=auto` means minimum safe impact; `fallback=restart` applies only after a reasoned unsafe-in-process classification, never to every new import or `main.py` edit. Snapshot state is opt-in, versioned and bounded JSON; never serialize widgets, stores themselves, secrets, closures or native handles.

## 9. Implementation handoff and certification boundaries

| Internal increment | Concrete deliverable | Exit evidence required |
| --- | --- | --- |
| Architecture and shared contract | This canonical PSX specification, backed by audited entry points, configuration precedence, ownership, decision matrix and fail-closed rules | Source inspection and documentation-only diff; no new product feature implied |
| Development supervision | CLI command/options and settings adapter coordinate exactly one watcher with Engine, child-handshake and source/frozen safety | Executed tests for CLI and Engine in their own repositories; disabled/frozen and invalid settings regressions |
| Compatible refresh | PSX recompiles/rebinds safe changes, including markup, CSS and project imports, then selectively commits on UI thread | Real Qt/Tk/Kivy tests; CI routing and public census when required |
| Targeted remount | Incompatible hooks, keys and native handle changes remount only necessary boundaries | Teardown/cleanup and retained-state tests including failures |
| Shared state and recovery | Preserved Pydux instances, registered restart snapshots and source validation rollback | Pydux and Qyro integration tests, syntax recovery and malformed-state tests |
| Controlled restart | Only unsafe native/process changes restart the child; reason codes and safe optional restore | CLI/Engine/PSX end-to-end child process tests |
| Integrated certification | Edit/revert/save storms, multiple remounts, stylesheet and imports across Qt/Tk/Kivy | Per-repository exact-SHA CI plus executed cross-repo integration receipts; memory/watchers/handles do not grow unbounded |

**Scope of this architecture increment:** specification and real-source ownership mapping only. No production module, workflow, public API, watcher, settings parser or transport is added in this increment. Functional/native tests and CI routing are **not applicable to a documentation-only diff**, and public-behavior census is **N/A**. This specification is ready for implementation handoff, but the complete hot reload feature remains uncertified.

### Source-development coordination implementation evidence

The first coordinated development path is now implemented on the feature branches for **Velto CLI** and **Qyro Engine**. This is a deliberately limited transport and configuration increment, not selective Fast Refresh certification.

- **CLI**: `velto start` resolves base, host-platform and development settings; `--no-hot-reload` disables the opt-in supervisor; the source runner passes source-mode flags and starts exactly one CLI-owned polling watcher when enabled. Changes are debounced and sent as versioned, project-relative JSON messages over an authenticated loopback child connection. The authored entry point is monitored, with generated directories excluded.
- **Engine**: development settings are recursively merged only for explicitly marked source launches, and never in frozen mode; `VeltoContext` conditionally creates a passive receiver during its live `run()` and closes it at shutdown. Incoming source notifications are validated and retained in a bounded queue pending the PSX classification/application stage. The child does **not** touch native widgets from the receiving thread.
- **Boundary**: notifications are **not yet executed as PSX component patches**; they are only delivered and validated. Applying notifications and selecting Fast Refresh/remount/restart are separate implementation increments. Restart requests/acknowledgments and recovery remain future work.

Executed GitHub Actions evidence:

| Repository | Source SHA | Workflow | Result |
| --- | --- | --- | --- |
| Velto CLI | `e21c80a256c486711c2931e2da15c77cf562677a` | [Development launch validation](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39863029883) | Success, including CLI→Qyro actual child notification |
| Qyro Engine | `f26fa7d91fed48fb5177786d60f595252098add0` | [Development settings validation](https://github.com/Neuri-AI/qyro/actions/runs/39861558699) | Success, including frozen-mode receiver prohibition |

All architecture and progress documentation remains in this PSX repository. These code/CI SHA links record only the integration slices exercised; they are **not** proof of production-ready complete Hot Reloading.


## 10. Compatible Fast Refresh: implemented integration and executed receipts

**Scope of this increment:** load compatible Python/PSX Markup source changes and local dependency edits into a mounted `VeltoContext` through the CLI→Qyro notification channel; use the existing PSX reconciler and renderer UI scheduler rather than creating a second watcher or replacing the native window. Incompatible hook changes **remain outside this increment** and are handled by the subsequent targeted-remount work.

### Implemented behavior

- Qyro's `VeltoContext` maintains a replaceable compiled render callable and stable root component identity. The existing development receiver forwards changes to the renderer's `schedule_ui`; the worker never mutates widgets.
- PSX's `psx/devtools/coordinated_refresh.py` accepts project-relative changes, validates the project boundary, preflights changed Python syntax, discovers project-local imports and evaluates compatible changes through `Reconciler.try_reevaluate`. It then commits layout, refs and scheduled effects through the existing reconciler/renderer. The mounted window and compatible component hooks survive in-place changes.
- Local imports, including `from module import symbol`, are rebound when project-owned dependencies change. Previously unimported installed third-party dependencies, including `pandas`, can be imported without an automatic process restart. Already loaded native extensions are **not** arbitrarily reloaded.
- CSS-file notifications cause a reevaluation of the mounted root and fresh stylesheet computation. CSS updates use the existing style and Cinnamon geometry pipeline; unrelated native handles survive compatible updates.
- Syntax errors detected before module replacement and incompatible hook signatures reject the candidate and retain the previous compiled render function. The guaranteed atomicity of complex native update failures and complete restoration of arbitrary side effects are **not claimed** here.

### Executed tests and boundaries

| Test domain | Exact source SHA / run | Verified behavior |
| --- | --- | --- |
| PSX direct and real native Qt, Tkinter and Kivy | `7e1674a568015c814038a7dc9d1e48f5094471b8` — [Coordinated component refresh validation](https://github.com/Neuri-AI/PSX/actions/runs/39866178324) | Mounted native widget and hook identity retained; real authored Python updates; CSS recomputation; project-module rebinding; newly loaded `pandas`; invalid-source refusal; CI impact routing |
| Qyro Engine actual `VeltoContext` + pinned PSX source | `bfd41439ac2fd50cdeb495995ef63fdb65d7eebc` — [Development settings validation](https://github.com/Neuri-AI/qyro/actions/runs/39866382244) | Live Qyro context mounts a real PSX headless tree, applies an authored file change and retains native host and hook state; notification dispatch occurs on the renderer thread; frozen guard remains tested |
| Velto CLI existing supervisor / source notification baseline | `e21c80a256c486711c2931e2da15c77cf562677a` — [Development launch validation](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39863029883) | Authenticated, debounced CLI→Qyro child notification channel and source settings |

**Architecture boundary:** direct component-root Fast Refresh and unchanged-native-widget projection are certified above. Arbitrary subcomponent-level remounts, hook signature migration, crash-restart communication, globally transactional rollback of module side effects, Pydux snapshot restore, repeated soak runs and cross-platform Windows/macOS integration remain later work. In particular, the source-change supervisor currently relays notifications, but does not yet implement the final coordinated process-restart protocol.

All source/certification code stays with its owning repository. This document is the only added canonical project-wide architecture report.

## Targeted component remount: implementation and certification

Incompatible hook sequences now replace the smallest affected mounted component boundary during coordinated source refresh, without restarting the process. Stable native descendants and independent siblings are retained. Old state setters become inert; effect teardown continues despite a cleanup exception, and component-owned refs are released. Nested replacement uses the incoming VNode identity; transparent component boundaries resolve real native parents (including Tkinter masters). Ordinary state updates do not automatically activate this remount policy.

Executed certification:
- PSX source `69430915ca87681d85f5b9c3fbc2b1f26caf93fe`: [live Qt, Tkinter, Kivy and headless regression run](https://github.com/Neuri-AI/PSX/actions/runs/39869188674), both jobs successful. Tests exercise added/removed hooks, nested siblings, stale setters, failed effect cleanup and refs.
- Qyro source `01d9580bd4eacb20d83a90149037a534a7d7e6c2`: [mounted context and PSX integration run](https://github.com/Neuri-AI/qyro/actions/runs/39869287978), successful.
- CLI source supervisor unchanged: [existing development coordination regression](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39863029883), successful.

Public census is **N/A** because no new public markup, property, event or user API is introduced. Native routing and runtime-specific functional tests are executed.

Explicitly not certified here: atomic rollback after arbitrary native commit failures, complete foreign-module side-effect recovery, Pydux cross-process snapshot restore, restart handshake and extended repeated-edit resource soaks. Those are separate downstream obligations.

## 11. Incompatible component hook remount: implemented behavior

Coordinated source edits now enable narrowly scoped remounting of mounted components whose hook **count or kind** becomes incompatible. This is internal reconciler behavior rather than a new public user-facing API. It is only enabled while applying a coordinated source edit; ordinary reconciliation retains its established hook diagnostics.

- A candidate is evaluated against a new mounted component instance before discarding the last working boundary. Invalid render candidates leave the previous live instance intact.
- An incompatible root remount replaces its hook owner and makes captured old state setters inert. Its compatible native descendants are reconciled in place, preserving the host widget where safe.
- An incompatible nested component is remounted at its existing parent position without remounting the parent or independent siblings. Hook and reference lifetime follow the replaced boundary; its descendants use ordinary key/type compatibility.
- Existing effect cleanups are attempted in reverse registration order; even if one raises, remaining cleanups execute, old hook slots and refs release and the committed replacement stays installed. The cleanup exception remains visible rather than being silently suppressed.
- Qt, Tkinter and Kivy tests exercise real mounted root and nested component updates and verify native handle/sibling retention. Tkinter native-parent resolution through transparent component boundaries was corrected rather than weakening the tests.
- No separate native widget manager or file watcher was introduced. The CLI-to-Qyro source notification and PSX UI-thread scheduling remain unchanged.

**Boundaries:** hot reload of a component that changes type/key is handled by existing reconciliation identity semantics; complete recovery of arbitrary side effects, transactional rollback of failed native mutations, cross-process snapshots and restarts are not certified here. Hook compatibility is determined by the runtime’s actual ordered slot contract rather than guessing from source-text differences.

**Public behavior census:** N/A for this increment because no new public props, events, components or user-facing methods were introduced. These tests exercise internal development-only reconciliation and the existing public hooks.

**Certification:** the final code-and-CI commit `c1754cf348a6564abd40f0914c90a2b7854eb543` passed the [coordinated refresh workflow](https://github.com/Neuri-AI/PSX/actions/runs/39871005567): functional remount, hook lifecycle, CI selector and real mounted Qt, Tkinter and Kivy jobs completed successfully. The subsequent `5f67a15c338ee26ff30d503227c2668fe9ce9f90` commit changes only this architecture document; product tests are not required for that documentation-only difference. This certifies targeted remount, not later recovery, restart or extended soak work.


## Development state recovery: implemented incremental scope

During a source refresh, Qyro retains the existing Pydux store instance instead of replacing its reducer, middleware or subscription identities. When the project explicitly sets `hot_reload.preserve_state: true`, Qyro can capture a detached, size-bounded JSON snapshot before applying a source change. If the change is rejected without committing an incompatible-component replacement, it restores the previous store data in the same instance and notifies existing subscribers using Pydux's normal selective notification path.

The Pydux snapshot helper validates an exact versioned envelope, rejects non-JSON state, NaN, oversized content and incompatible selector state before writing. It does not serialize live widgets, closures, reducers, subscriptions or middleware, and does not automatically export user data to a process supervisor. Failed effect cleanup **after** a committed remount must not restore the previous store behind an already replaced view. A previously committed remount does not mark a later invalid edit as committed.

Ownership remains split: Pydux owns data snapshot validation and subscriber notification; Qyro owns developer opt-in and recovery invocation; PSX owns reconciliation and remount commit status. CLI supervision and configuration ownership are unchanged. All feature code and behavioral tests live in the owning repositories; this PSX specification remains the canonical architectural record.

Executed same-SHA evidence:
- Pydux `d4495be4914ab38255d5871d3ade45422003015c`: [development state recovery checks](https://github.com/Neuri-AI/Pydux/actions/runs/39873460714), success (core regressions and snapshot error cases).
- Qyro `0548655b730cbc9a8b4aaa3a6275b2598ab88e12`: [development settings validation](https://github.com/Neuri-AI/qyro/actions/runs/39873867510), success (pinned Pydux and current PSX integration, state rollback, committed-remount isolation and existing context tests).
- PSX `9b1e585a7ce612451765a2f7a27e2ddccae334fe`: [component refresh validation](https://github.com/Neuri-AI/PSX/actions/runs/39873807147), success (source validation followed by corrected save, remount outcome isolation, native Qt/Tkinter/Kivy suites).

**Remaining boundaries:** process-restart handshake and cross-process snapshot exchange belong to controlled restart; source import side effects, native mutations and subscription ownership are not globally transactional. A snapshot can only be restored when its data remains compatible with the current selectors. Non-JSON store data is intentionally not preserved. Extended repeated-edit soak and Windows/macOS verification remain integrated-certification tasks. No public markup, prop, event or hook API is introduced in this increment, so new-public-operation census is N/A.


## Controlled process restart: implemented coordination and recovery handoff

Velto CLI is the sole supervisor of development child processes. The same filesystem watcher survives child replacement. The supervisor reads the effective development backend from base, active-platform and development settings; only a changed effective framework/binding identity triggers backend restart. Ordinary source, markup, stylesheet, and development-only setting edits remain on the existing refresh path. Invalid JSON is not treated as an authorized restart reason, and edits to unrelated platform profiles do not restart the current backend.

Qyro identifies a replaced project native extension by matching an edited extension file against extensions already loaded into the running interpreter. A first import of an installed third-party/native package is not an automatic restart. For loaded replacements Qyro issues an explicit restart request. The child-to-supervisor loopback protocol validates version, kind and a bounded set of reasons, using an authenticated connection and credentials rotated for each new child generation. The supervisor requests restart preparation and accepts an acknowledgment, with a bounded timeout rather than waiting indefinitely on a blocked GUI thread.

Restart preparation supports an **explicit opt-in** JSON-only Pydux state handoff, through a private session directory managed and deleted by the CLI. Qyro captures its discovered/registered compatible store on the GUI owner thread and acknowledges preparation. A newly started Qyro process can restore the versioned state into its fresh store *before* mounting the PSX provider/root. The snapshot is capped, rejected if incompatible or malformed, and consumed once. Store objects, reducers, callbacks, secrets by special serialization, subscriptions and native widgets are not themselves serialized. Cross-process state preservation is best effort, not a guarantee for arbitrary application resources.

Source-mode restart regenerates the authored PSX-prepared entry point for each child generation, rather than reusing a potentially stale transformed file. The terminated child is waited for with a graceful timeout and forced termination fallback. Existing CLI source-mode and Qyro frozen-mode guards remain in force: a frozen application never starts the coordinated watcher/receiver, even when configuration requests hot reloading.

The project may opt in with the existing development profile, e.g.:

```json
{
  "hot_reload": {
    "enabled": true,
    "preserve_state": true,
    "state": {
      "snapshot_on_restart": true,
      "restore_on_restart": true
    }
  }
}
```

**Executed evidence at exact source commits:**

- Velto CLI `286cef4cf9fd1db3a9ad2df6f4302e2068b19672`: [development supervisor validation](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39876381591), success. Exercises a real replaced child, authenticated restart requests, restart-state prepare/ack handoff, one watcher across generations, entry-source re-preparation, effective-backend classification, and existing child notifications.
- Qyro Engine `fa47de34f1d068be574542221d6bb7bca8e0ff7b`: [development settings validation](https://github.com/Neuri-AI/qyro/actions/runs/39875702188), success. Covers loaded/unloaded native-extension classification, opted-in snapshot capture/restore, malformed/oversized state rejection, frozen/disabled guards, and existing context refresh regressions.
- Pydux `d4495be4914ab38255d5871d3ade45422003015c`: [state recovery validation](https://github.com/Neuri-AI/Pydux/actions/runs/39873460714), success. Verifies detached versioned JSON snapshots and store subscription restoration rules.

**Boundaries and next certification gate:** the tested restart decisions cover changed effective backend settings and edits to already-loaded native extension files; they do not claim general automatic detection of all unsafe global initializers, interpreter changes or arbitrary foreign process resources. A rejected process launch after a restart is not yet guaranteed to retain an operational previous native window. Long-running save storms, startup-failure recovery and actual repeated Qt/Tkinter/Kivy restart tests remain for integrated certification. Snapshot restoration is restricted to JSON-safe compatible Pydux data and does not rehydrate native handles or running tasks. This increment introduces internal development orchestration, not new public PSX markup, props or events: public-behavior census N/A.


## Failed child startup recovery

Velto CLI retains its single development watcher when a child exits with a nonzero status. It does not immediately respawn failed code; it waits for another source save before launching a new child. The real-subprocess regression succeeded at commit `f9c317bcffa45b7d02eda379c7734930919af7a4` (https://github.com/Neuri-AI/Velto-CLI/actions/runs/39877137209). Bounded waits and escalation for a child that ignores termination passed at commit `49c1b6895ca299a223a82626934d02c1297d16c4` (https://github.com/Neuri-AI/Velto-CLI/actions/runs/39877278848).

Remaining limits: a failed replacement does not guarantee preservation of the old native window; automatic classification of arbitrary interpreter or global external-resource incompatibilities has not been implemented. Native cross-backend soak certification remains pending. No public PSX props, hooks, events, or markup were added; public-behavior census N/A.

The authenticated development restart protocol also recognizes explicit `interpreter_changed`, `unsafe_global_initialization`, and `external_resource_incompatible` reasons. This extends controlled escalation by an integration that knows its resource contract; it does not imply that arbitrary global side effects or every foreign resource can be discovered automatically. The connected Qyro and CLI implementations require their own latest same-SHA CI checks before these extensions are considered verified.


## Restart hardening: bounded recovery and process ownership

The development supervisor now starts a supervised child as an independent POSIX process group, with a Windows process-tree termination path. Controlled restarts, interruption and final cleanup stop the child and its descendants, applying bounded graceful waits and escalation. This limits subprocesses left alive by a replaced runtime. It does not claim ownership of independently spawned daemons, cloud resources or external services; such resources require explicit application cleanup protocols.

The CLI also fingerprints the actual child interpreter executable (resolved executable path, device/inode, modification time and size), and extracts the entry module's explicit `if __name__ == "__main__"` bootstrap AST. A replacement binary or changed bootstrap guard triggers restart; compatible edits limited to component/render bodies do not. Invalid source syntax is ignored for escalation until a valid edit is saved. Backend settings remain classified by effective merged backend, not merely by changed filename. Interpreter *installation or selection* by an external environment manager is not performed by the supervisor: it restarts its selected executable when it has changed, and cannot promise migration to an unrelated interpreter automatically.

When a backend change causes a replacement process to exit unsuccessfully **before establishing its mounted authenticated receiver**, the supervisor launches a rollback process using the last backend known to have connected successfully. This uses a development-only Qyro configuration override rather than rewriting project files. While recovery is active, the next source modification triggers a fresh attempt using the developer's requested configuration. A single failed candidate cannot cause an unbounded automatic restart loop. Source data still must be compatible: restoration of an arbitrary old Python interpreter, native ABI, widgets or external handles is impossible without application-specific integration. If the fallback process also fails, the supervisor stays alive and waits for a corrected source edit.

These additions are internal development capabilities with no public PSX operation, so public-behavior census is N/A. The final evidence gate requires exact-SHA GitHub Actions success for child-group teardown, rejected-backend recovery, entry bootstrap detection, interpreter file replacement, and frozen-mode regression checks. Repeated native Qt/Tkinter/Kivy end-to-end soak remains the following cross-backend certification stage.


**Executed implementation receipts (immutable SHAs):**

- Velto CLI `17c6c1733a47014f3f7661c4072742a4c7c743dc`: [GitHub Actions #39879897568](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39879897568), success. Covers a failed new-backend boot followed by relaunch with previous backend, worker-descendant group shutdown, changed `__main__` process bootstrap, replaced interpreter executable, invalid edit handling and prior coordinated-restart regression tests.
- Qyro Engine `00a2814d2e1e1bcbf2051ffe6a6be317d8b439f6`: [GitHub Actions #39879711959](https://github.com/Neuri-AI/qyro/actions/runs/39879711959), success. Covers development-only backend fallback without mutating application settings and the frozen-mode prohibition, plus the existing state handoff and native-extension refresh regression suite.

The implementation scope for supervised restart hardening is therefore complete **within the explicitly supported compatibility boundary**. Integrated soak and toolkit-specific repeated live native restart certification remain separate. The phrase “last working application” means relaunching a previous successfully connected backend with compatible current source and optional registered state, not retaining its original native widgets or guaranteeing rollback of arbitrary incompatible project code.


## Integrated development reload certification — executed Linux baseline (2026-10-23)

The integrated workflow `.github/workflows/development-reload-certification.yml` checks out immutable SHA versions of PSX, Qyro Engine, Pydux and Velto CLI, installs them together and executes the respective refresh, remount, snapshot, frozen-mode, source receiver, child supervision and recovery tests. The workflow uses **Pydux `d4495be4914ab38255d5871d3ade45422003015c`**, **Qyro `00a2814d2e1e1bcbf2051ffe6a6be317d8b439f6`**, and **Velto CLI `75590348b3edb25d0d004bb11e3e2d0d127e5577`**, including eight repeated authenticated subprocess restart generations and verification that the watcher thread is released.

Real mounted native test coverage was expanded for all supported CI backends: Qt via PySide6, Tkinter and Kivy, using Xvfb in Linux. The native suite exercises Fast Refresh identity/state preservation, incompatible hooks and nested component remount with unaffected siblings, plus **30 repeated compatible source updates with intermittent syntax errors and recovery** and **20 successive incompatible hook-signature remounts** per backend. It asserts reuse of appropriate native handles, disposal of replaced boundaries, state values, corrected labels and the absence of unintended remounts. Routing tests guarantee these changes select the Qt, Tkinter, Kivy, core and headless consumers. No new public markup, component props, events or hooks were introduced; public-behavior census is N/A.

**Green, executed receipts at the same PSX source SHA `bc2cc7cd0b866a042411e30165b15a713102bf90`:**

- [Native Qt/Tkinter/Kivy and pure refresh validation — Actions #39943502876](https://github.com/Neuri-AI/PSX/actions/runs/39943502876): SUCCESS, includes the repeated native refresh/remount tests and routing checks.
- [Pinned PSX/Qyro/Pydux/CLI integrated lifecycle — Actions #39943502601](https://github.com/Neuri-AI/PSX/actions/runs/39943502601): SUCCESS, includes development state recovery and subprocess supervision across the four repositories.
- [Velto CLI repeated process supervision — Actions #39943222124](https://github.com/Neuri-AI/Velto-CLI/actions/runs/39943222124): SUCCESS at `75590348b3edb25d0d004bb11e3e2d0d127e5577`.

**Certification boundary:** these are real native mounted refresh/remount tests and real subprocess restart tests, but the workflow does **not** yet launch an entire Qyro native application and restart its toolkit event loop end-to-end for each backend. It does not measure bounded heap/RSS slopes across hour-long native sessions, or certify Windows/macOS. Therefore the *Linux coordinated lifecycle and mounted-backend functional baseline* passes, while the full platform/native-process/long-duration release gate remains OPEN. No skipped or non-executed test is counted as evidence.


## Cross-platform native event-loop and resource certification — executed scope

New test-only files under `tests/` exercise full native PSX applications in separate subprocesses with real toolkit event loops (PySide6 `QApplication.exec`, Tkinter `mainloop`, Kivy `runTouchApp`). The supervised variant also connects to the actual Velto CLI authenticated development coordinator and requests two restarts from inside the active native event loop before the final generation exits. This differs from the earlier mounted-renderer-only tests.

The same-process memory regression runs **160 successive live source refreshes** per backend and samples resident memory (RSS) and Python allocations after periodic garbage collections; its reviewed bounds are 32 MiB incremental RSS and 8 MiB incremental Python allocations after warmup. These are bounded repetitive-stress checks, **not multi-hour soak measurements**. The `linux-native-refresh-memory` CI artifact contains per-backend raw samples and thresholds. The cross-platform workflow additionally archives its observations per OS/backend when the test reaches its reporting stage.

Verified successful Linux native process, supervisor and resource checks: [coordinated refresh workflow #39945400491](https://github.com/Neuri-AI/PSX/actions/runs/39945400491) (including its native-refresh job, SUCCESS). This includes actual Qt, Tkinter and Kivy event-loop generations, authenticated supervisor replacement, and same-process memory sampling.

Platform evidence from [cross-platform run #39944825171](https://github.com/Neuri-AI/PSX/actions/runs/39944825171): Linux Qt/Tkinter/Kivy successful; macOS Qt/Tkinter successful; Windows Qt successful, and Windows Tkinter has at least one executed green run using Python 3.11; a later run reported missing Tcl/Tk standard-library files on its hosted runner, so that cell still requires a stable toolchain rerun. **Do not count macOS Kivy as passing:** the hosted macOS runner cannot create a real SDL2/Kivy window (`App: Unable to get a Window`). Windows Kivy remains subject to the Windows runner's graphical execution and time-bounded workflow evidence. A native Cocoa/SDL display-capable macOS runner is required to certify that cell; a mock provider is not an acceptable substitute.

Release-level certification is explicitly **OPEN** until every required native OS/backend cell executes successfully on suitable hardware. Successful platform cells, exact tested commit SHAs and CI artifacts are necessary evidence, but cannot imply the missing Mac Kivy result or unexecuted hours-long resource soaks. No new PSX user-facing operation was added; public behavior census is N/A.


### Native restart qualification and detailed CI receipts

The Linux native-supervision checks at [#39945030892](https://github.com/Neuri-AI/PSX/actions/runs/39945030892) passed for each renderer: an actual GUI child connects to Velto CLI's authenticated supervisor from its running event loop, requests replacement twice, and the third generation exits through the corresponding toolkit event loop. No fake native toolkit or event-loop substitute is used.

[Linux mounted refresh, supervisor and resource regression #39945400491](https://github.com/Neuri-AI/PSX/actions/runs/39945400491) passed all required jobs, including 160 same-process source refreshes per toolkit. The run's `linux-native-refresh-memory` artifact records raw RSS and Python allocation samples and limits for Qt/Tkinter/Kivy. Test evidence is bounded to 160 cycles, not equivalent to an hour-long soak.

[Cross-platform GUI matrix #39944825171](https://github.com/Neuri-AI/PSX/actions/runs/39944825171) executed real native event loops. Linux passed all three toolkit cells; Windows Qt and macOS Qt/Tk passed. Windows Tk was green on an earlier hosted run and failed on a later run because the Python toolcache lacked Tcl/Tk files (`tk.tcl`, `ttk.tcl`), a runner-integrity problem that must remain visible. macOS Kivy failed to obtain the SDL2 OpenGL pixel format and therefore could not create a real GUI window on that hosted runner. Windows Kivy requires its final time-bounded execution receipt; running/queued jobs do not count as PASS.

The final OS-by-toolkit release gate remains OPEN. Where a hosted runner cannot provide a required real graphical context (notably Cocoa/SDL2 OpenGL), completion requires a GUI-capable runner instead of replacing native tests with mocks or marking skipped coverage successful. Public behavior census N/A: all added behavior here is tests, reports and CI.


### Windows native Kivy certification — PASS with a real graphics backend

On 2026-10-23, hosted Windows Kivy previously hung at `kivy.core.gl.msgbox` → `user32.MessageBoxW` while reporting an unsupported or inaccessible OpenGL context. The runner cannot dismiss interactive dialogs; the resulting timeout was **not** evidence of a hot-reload state failure.

The Windows Kivy matrix cell now installs `kivy_deps.angle` and `kivy_deps.sdl2` and sets `KIVY_GL_BACKEND=angle_sdl2`, a real Kivy OpenGL ES translation backend for Windows (not a mock). On source SHA `27c8d9e8dc86e2c24b7af42c4263e897e67e92e5`, [Actions #39951131528](https://github.com/Neuri-AI/PSX/actions/runs/39951131528), job `native-toolkit (windows-latest, kivy)`, finished **SUCCESS: 10 passed in 15.88 seconds** using CPython 3.12.10. This includes three native application/event-loop child generations, two supervised native restart requests, compatible/incompatible component changes and bounded native resource growth across 160 updates. The artifact `native-memory-windows-latest-kivy` retains the raw samples.

This is a **closed and executable Windows/Kivy cell**, not a claim that the entire nine-cell GitHub workflow passed. Hosted macOS Kivy continues to fail its OpenGL pixel-format setup; separate local Apple Silicon/macOS Kivy evidence (10/10 executed, Python 3.12.15, Kivy 2.3.1, PSX `ad350e1545f07b8e715701812b5dcac1ce1427fe`) is available independently and must retain its source SHA and platform qualification. Windows Tkinter had mixed toolcache results in the same workflow and must retain its per-run status. No workaround simulates a Kivy window.


## Final owner-supplied local macOS Kivy qualification (2026-10-23)

The owner supplied four executed certification outputs from a physical Mac rather than the GitHub-hosted macOS runner: `certification.log`, `environment.txt`, `junit.xml`, and `kivy-memory(1).json`. These are **local evidence**, not a green GitHub Actions macOS job. The evidence identifies macOS 27.0 on Apple Silicon arm64, Anaconda Python 3.12.15, Kivy 2.3.1, PSX commit `ad350e1545f07b8e715701812b5dcac1ce1427fe`, and Velto CLI commit `75590348b3edb25d0d004bb11e3e2d0d127e5577`.

The JUnit results report **10 tests, 0 failures, 0 errors, 0 skipped**, with a total execution time of 25.125 seconds. The tests exercised three actual Kivy child event-loop generations, authenticated supervised process restarts, compatible Fast Refresh, incompatible hook and nested component remount, preservation of unaffected native identities, invalid-save recovery, and resource sampling. The `kivy-memory(1).json` report records 160 refreshes with **32,768 bytes (32 KiB) net RSS growth** and **5,387 bytes net Python allocations growth**, below the respective defined 32 MiB and 8 MiB thresholds. The local execution output reports an exit status of zero.

**Certification verdict:** **macOS 27.0 arm64 + Kivy 2.3.1 + Python 3.12.15 PASS**, with explicit tested SHAs. A GitHub-hosted macOS runner's inability to create an SDL2/OpenGL window is a separate CI infrastructure constraint; it does not negate physical-Mac native certification and must not be presented as an open functional macOS/Kivy defect. Keep both source contexts visible.

## Development hot-reload gate disposition

**P3 is CLOSED for the approved functional exit criteria** in `docs/architecture/velto-master-execution-plan.md`: Level 1 compatible state preservation, Level 2 incompatible hook remount and native identity checks, Level 3 real process restarts and resource ownership, failed-edit recovery, repeated watcher/process cycles and per-backend native execution. Supporting immutable GitHub Actions receipts include [Linux integrated #39945400491](https://github.com/Neuri-AI/PSX/actions/runs/39945400491), [four-repository integrated #39943502601](https://github.com/Neuri-AI/PSX/actions/runs/39943502601), [Windows Kivy 10/10 #39951131528](https://github.com/Neuri-AI/PSX/actions/runs/39951131528), plus the owner-supplied local macOS Kivy reports above. The programmatic test-only code does not add public API or props, so public-behavior census N/A.

**Handoff to P4, not an open P3 feature defect:** exhaustive packaging/backend/Python and OS matrix, graphical-runner restrictions such as hosted macOS Kivy, intermittent hosted Windows Tcl/Tk availability, hour-scale/long-duration memory and resource observations, release readiness and public teaching documentation. P3's bounded 160-update leak regression is a functional safeguard, not evidence of multi-hour stability. An all-green single nine-cell GitHub-hosted workflow is neither claimed nor required in place of independently identified, executed, backend-qualified platform evidence.
