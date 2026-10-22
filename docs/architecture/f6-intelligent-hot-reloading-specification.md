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
