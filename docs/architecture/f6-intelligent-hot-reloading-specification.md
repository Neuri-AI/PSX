# F6 — Intelligent Hot Reloading: approved architectural requirements

**Decision date:** 2026-10-17. **Status:** architecture approved; coordinated implementation authorized on 2026-10-22 but runtime changes and integral certification are not yet implemented. **Milestone:** M8. This file is the canonical cross-repository architecture specification, not evidence that the target behavior exists.

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
