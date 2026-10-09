# Refactoring progress

## REF-M0 — Architecture Audit & Baseline

Status: completed with documented baseline failures.

Created the architecture audit, dependency map, baseline record and decisions/migration plan. Added a public-API characterization test and captured the core/headless benchmark baseline.

No production runtime code was changed by REF-M0. Existing local production changes were preserved and are recorded as the state audited, not claimed as part of this milestone.

Verification: the available suite produced 85 passes, 2 expected optional-binding skips and 3 pre-existing failures; optional Pydux, PySide6/Qyro and Kivy coverage is unavailable in this environment. See `baseline.md` for commands and causes.

Compatibility decision: future milestones are blocked from replacing public APIs, requiring registration of built-ins, changing markup, or altering compatible widget/event/ref/hook behavior.

Next milestone: REF-M1 — Component Contracts & Definitions, pending review of this baseline and the three recorded failures.

## REF-M1 — Component Contracts & Definitions

Status: completed with compatibility baseline limitations.

Added `psx.core.contracts`, a backend-independent internal contract model for `Text`, `Button`, and `Input`. Each contract declares supported properties, defaults, events, child policy and validation. Legacy builders now delegate to these contracts, while `vnode.py` re-exports the prior internal validation symbols for compatibility with existing renderer code.

`Input` retains its existing builder-specific error types and messages through an explicit compatibility validator. The contracts are used by the public builders and preserve the existing renderer behavior; renderer adapter consolidation remains REF-M4. The documented Tkinter `Button.font_size` failure is intentionally retained as an observable REF-M0 baseline result.

Verification: contract, characterization, markup and hook tests pass. The REF-M0 baseline failures are retained and optional PySide6, Kivy, Qyro and Pydux coverage remains unavailable according to REF-M0's environment record.

Compatibility: no public import, signature, markup syntax, VNode shape, reconciliation rule, event slot, ref or scheduling behavior was replaced. No registry was introduced; that remains REF-M2.

Next milestone: REF-M2 — Component Registry.

## REF-M2 — Component Registry

Status: completed with documented baseline failures.

Added `psx.core.registry` with typed `ComponentDefinition` values, instance-scoped `ComponentRegistry` objects, deterministic duplicate and unknown-name diagnostics, immutable snapshots, clone isolation and a registry version counter. `builtin_component_registry()` creates a new default registry on every call and registers `Column`, `Row`, `Text`, `Button`, `Input`, `Fragment`, and `Native` automatically. No application must register built-ins.

The registry has no GUI-backend imports and is deliberately not connected to `markup.compile`; REF-M3 will perform that integration while preserving current cache and diagnostic behavior. The existing component hot-reload identity registry is untouched.

Verification: registry, contract, characterization, core, markup, static-transform and hook suites passed (77 tests). The broad available command produced 96 passed, 2 skipped and 2 failures: the established Tkinter `Button.font_size` baseline failure and the devtools transformed-child import-path failure. The atomic-save watcher issue from REF-M0 did not reproduce in this run and remains documented as intermittent; it was not changed or hidden.

Compatibility: no public imports, builders, markup compiler, reconciliation, events, hooks, scheduler or integration code was replaced. Separate registry instances and their snapshots are tested for isolation.

Next milestone: REF-M3 — Markup Resolver & Compiler Decoupling, pending review.

## REF-M3 — Markup Resolver & Compiler Decoupling

Status: completed with documented baseline failures.

Replaced the compiler's `_PRIMITIVES` table and `Text`/`Button`/layout tag-name branches with registry-backed definitions. `compile_template()` and `psx()` now accept an additive `registry=` argument. With no registry, they resolve the familiar built-ins automatically; legacy `primitives=` mappings and scope-based `ComponentType` resolution retain their current behavior.

Registry snapshots make compiled templates deterministic. Template caching keys include registry object identity and version, so registration changes cannot reuse a template resolved under an earlier registry state. Contracts now provide text-content property metadata, and definitions carry layout integer-coercion metadata; parser, AST, expression scope, source diagnostics and static transformation remain unchanged.

Verification: 81 focused markup/registry/contract/characterization tests passed. The broad available command produced 99 passed, 2 skipped and the same 3 REF-M0 baseline failures: watcher debounce, transformed devtools child import path, and Tkinter `Button.font_size`. Optional PySide6, Kivy, Qyro and Pydux coverage remains unavailable.

Compatibility: current `psx()` calls do not require a registry; existing built-ins, markup tags, lexical/static transform, scope components, event props, keys and refs continue through their existing paths. No renderer or reconciliation work was started.

Next milestone: REF-M4 — Renderer Adapter Architecture, pending review.

## REF-M4 — Renderer Adapter Architecture

Status: completed — validated in Conda `playground`.

Added the typed `ComponentAdapter` protocol, `RendererAdapterRegistry`, lifecycle subscription wrapper and renderer-local `register_adapter()` extension point. Headless, Tkinter, Kivy, PySide6 and PyQt now dispatch create, update, bind, unbind and destruction through their adapter registry. The reconciler and its VNode compatibility, refs, `EventSlot`, scheduling and cleanup ordering were not changed.

Adapter tests replace the Headless Button adapter and register a new Badge adapter. They verify mount, property update, stable callback replacement without a second native binding, deterministic unbind and destruction. Built-in adapter registrations include Text, Button, Input, layouts and Native for every renderer.

Validation used `C:\Users\luisp\.conda\envs\playground\python.exe` (Python 3.13.16), rather than the default interpreter recorded in REF-M0. The environment contains PySide6, PyQt5, Kivy, Qyro and Pydux; PyQt6 is not installed. `python -m pytest tests/ -v --basetemp .pytest-playground-m4-full` produced **137 passed, 1 skipped**. The one skip is the optional PyQt6 renderer test.

Focused native validation covers the PySide6 `Text`, `Button` and `Input` paths, including property updates, widget identity, callback replacement and cleanup. The complete suite also covers the Tkinter `Text`/`Button` lifecycle, Kivy and PyQt5 button identity, Qyro mounting/lifecycle and Pydux scheduling. Adapter registry tests cover registration conflicts, replacement, extension adapters, mounting, updating, event unbinding and destruction without reconciler changes.

The three REF-M0 failures remain documented in `baseline.md`; they were captured with the wrong default interpreter and are not hidden or changed. Under the required `playground` environment, the same suite is green after the compatibility fixes for the existing `Text` default and Tkinter `Button.font_size` behavior. No REF-M5 work has begun.

## REF-M5 — Advanced Native Interoperability

Status: completed — validated in Conda `playground`.

Preserved the existing `Native` mechanism and added the optional, additive `psx.extensions.WebView` declaration adapter for the real PySide6 `QWebEngineView` widget. It uses `NativeWidget` ownership and specialized update/bind callbacks rather than modifying the compiler, reconciler or scheduler. A caller registers `WebView` in an isolated `ComponentRegistry` and can then use `<WebView />` in existing PSX markup; no built-in registration or syntax change is required.

`WebView` supports `url` or `html`, `on_load_finished`, `on_url_changed`, refs, PSX ownership, compatible widget identity and deterministic removal. Callback replacement uses the existing `EventSlot`, preserving one native signal connection. Its real-widget test mounts from markup, updates the URL without recreation, replaces the callback and unmounts it.

Validation: `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m5-full` produced **138 passed, 1 skipped**. This is one additional passing test over REF-M4's 137-pass suite. The skipped test is PyQt6, which is not installed. PySide6 WebEngine is installed; its virtual-display Chromium process can emit non-failing GPU-context diagnostics. Kivy `Video` was not added because media-provider behavior requires separate backend-specific coverage.

See `native-interoperability.md` for the extension contract and example. No REF-M6 work has begun.

## REF-M6 — Public Extension & Plugin API

Status: completed — validated in Conda `playground`.

Added the additive, dependency-free public `psx.plugins` API and root exports for `ComponentRegistry`, `ComponentDefinition`, `ComponentAdapter` and `RendererAdapterRegistry`. `register_component()` and `register_adapter()` wrap the established instance-scoped seams; `PluginAPI` scopes a plugin to an explicit component registry and named renderer instances. `renderer_capabilities()` reports adapters on a concrete renderer without importing a GUI toolkit.

Plugins can register portable components or renderer-specific adapters explicitly. Dot namespaces create markup-safe tags such as `<acme.Badge />`; conflicts remain deterministic (`DuplicateComponentError` for components and the existing adapter registration error for adapters), and no state crosses registry or renderer-instance boundaries. Optional discovery uses the `psx.plugins` Python entry-point group only when `load_plugins(..., discover=True)` is requested, keeping normal imports and GUI dependencies lazy.

Added `examples/badge_plugin`, an external-package example that declares a `psx.plugins` entry point and registers a component usable from PSX markup. New tests cover explicit registration, namespaced markup, adapter registration, conflicts, isolation, capability queries and opt-in lazy entry-point discovery.

Validation: after installing PyQt6 in Conda `playground`, `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m6-pyqt6` produced **143 passed**. This replaces REF-M6's earlier 142 passed and 1 skipped result; the PyQt6 renderer identity test now executes and passes. See `plugin-api.md`. No REF-M7 work has begun.

## REF-M7 — Reference Component: Checkbox

Status: completed — validated in Conda `playground`.

Added the portable public `Checkbox(checked=False, enabled=True, on_change=None, *, key=None, ref=None)` builder and transparent `<Checkbox />` built-in markup tag. Its contract defines no children; validates boolean `checked`/`enabled`; and declares `on_change`, whose callbacks receive a boolean. Built-in registration uses the existing `ComponentRegistry`; renderer dispatch uses the existing `RendererAdapterRegistry` registrations and lifecycle seam.

Adapters map Checkbox to `QCheckBox` on PySide6/PyQt5/PyQt6, Kivy `CheckBox`, ttk `Checkbutton`, and Headless. They preserve compatible identity, block programmatic signal feedback, keep a stable callback connection, and remove subscriptions before destruction. Tests cover Python, markup, mounting, property updates, callback replacement, identity and cleanup across Headless, PySide6, PyQt5, PyQt6, Kivy and Tkinter.

Validation: `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m7-full` produced **147 passed, 0 skipped**. PyQt6 is installed in `playground`; both its existing renderer identity test and Checkbox path execute. Compared with the updated REF-M6 baseline (143 passed), REF-M7 adds four passing checks. The implementation created 3 files and modified 14; it did not modify the lexer, parser, compiler, reconciler or scheduler. See `checkbox.md`. No REF-M8 work has begun.

## REF-M8 — Developer Documentation & Tutorials

Status: completed — validated in Conda `playground`.

Rewrote `docs/architecture.md` and `docs/public-api.md` around the implemented contracts, component registry, markup resolution, reconciliation, adapter lifecycle, native interoperability and plugin API. Added Mermaid diagrams for resolution, compilation/rendering, stable event slots and plugin registration. Rewrote the portable-widget tutorial around Checkbox and added the native-widget tutorial around the optional WebView extension. The documents describe all supported adapters (PySide6, PyQt5, PyQt6, Kivy, Tkinter and Headless), explicit registration, namespaces, entry points, optional dependencies, troubleshooting and lifecycle practices.

Validation: ran the documented portable markup and WebView markup snippets successfully in `playground`. `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m8-full` produced **147 passed, 0 skipped**, unchanged from REF-M7. Documentation changes do not alter the public runtime API. No REF-M9 work has begun.

## REF-M9 — Regression, Performance & Stabilization

Status: completed — final validation passed in Conda `playground`.

The final rerun, `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m9-full-rerun`, produced **147 passed, 0 skipped**. It validates all installed renderers (Headless, PySide6, PyQt5, PyQt6, Kivy, Tkinter), Qyro, Pydux, hooks, identity, event slots, refs, cleanup, markup compilation/cache/static transformation, registries, plugins, Checkbox, and WebView. The three historical REF-M0 failures do not reproduce in this required environment; their original record remains preserved in `baseline.md`.

Added `component_registry_resolution` to the dependency-free benchmark suite and captured `benchmarks/ref-m9-baseline.json`. The full comparison and runtime caveat are documented in `ref-m9-stabilization.md`: REF-M0 used Python 3.12.4 while REF-M9 uses 3.13.16, so cross-runtime timing differences are evidence for investigation, not a performance gate. No known functional regressions remain in the validated environment. The refactoring is complete.

## REF-M10 — Dead Code Cleanup & Documentation Consolidation

Status: completed — audited and validated in Conda `playground`.

Recorded a pre-cleanup baseline of **147 passed, 0 skipped**. The confirmed safe cleanup removed only two versioned `.DS_Store` artifacts and a duplicate PySide6 import. Documentation consolidation repaired the README Text and native-widget links, repaired the M12 standalone-playground relative link, and ignores generated `.pytest-*` directories. The audit deliberately preserved public APIs, dynamic plugin/lifecycle surfaces, historical refactoring records, and the benchmark compatibility wrapper. `repomix-output.xml` remains unmodified because its ownership is unknown.

Post-cleanup validation used `conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m10-full` and produced **147 passed, 0 skipped**. `pip check`, bytecode compilation, and internal documentation-link verification pass. Ruff is unavailable in `playground` and is recorded as an environment limitation rather than a successful check. See `cleanup-audit.md` for candidate classification, dependencies, removals and remaining debt.
