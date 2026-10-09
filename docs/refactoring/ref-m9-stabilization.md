# REF-M9 regression, performance, and stabilization report

## Validation result

REF-M9 ran in Conda `playground` with Python 3.13.16 and PySide6, PyQt5, PyQt6, Kivy, Tkinter, Qyro, and Pydux available. The final command was:

```powershell
conda run -n playground --no-capture-output python -m pytest tests/ -v --basetemp .pytest-ref-m9-full-rerun
```

Result: **147 passed, 0 skipped**. This covers headless reconciliation, all supported GUI renderers, Qyro, Pydux, hooks, refs, events, cleanup, markup compilation/cache/static transformation, registry isolation, plugins/entry points, Checkbox, and WebView.

The historical REF-M0 failures are not reproducible in this environment: Tkinter `Button.font_size`, devtools atomic-save debounce, and transformed-child import-path tests all pass. Their historical record remains in `baseline.md`; it was captured using the wrong default interpreter and incomplete optional dependencies.

## Benchmark comparison

`benchmarks/ref-m9-baseline.json` was captured with size 100, 30 iterations, and 3 repeats. It adds `component_registry_resolution`, which resolves eight built-ins in **0.0010 ms** mean with 80 peak traced Python bytes. It preserves all REF-M0 scenarios, including VNode creation, mount/unmount, updates, keyed reconciliation, events, scheduler, markup compile/render, static transform, and traced-memory reporting.

| Scenario | REF-M0 ms | REF-M9 ms | Change |
| --- | ---: | ---: | ---: |
| Mount/unmount | 1.7817 | 1.8270 | +2.5% |
| Full update | 1.9110 | 1.8874 | -1.2% |
| Single update | 1.4231 | 2.0115 | +41.3% |
| Keyed reorder | 1.5248 | 1.5018 | -1.5% |
| Markup render | 0.8773 | 1.0571 | +20.5% |
| Markup compile | 2.8653 | 2.7174 | -5.2% |
| Static transform | 0.2055 | 0.2341 | +13.9% |

These timings are not a strict regression verdict: REF-M0 used Python 3.12.4 and REF-M9 uses Python 3.13.16, and the samples are intentionally small. Memory values are retained in both JSON artifacts for comparable same-runtime future baselines. The functionally critical full update and keyed reorder paths are within noise or faster; the single-update and markup-render differences should be re-baselined on a fixed Python/runtime before performance gating.

## Architecture before and after

| Before REF-M0 | After REF-M9 |
| --- | --- |
| Builders, compiler tables, and renderer branches carried component knowledge. | Contracts, component definitions, registries, and adapters provide explicit extension seams. |
| Adding a component required compiler and renderer edits with implicit conventions. | Checkbox demonstrates a contract, built-in registry entry, shared prop normalizer, and adapter registrations without lexer/parser/compiler/reconciler/scheduler changes. |
| Native controls used the existing escape hatch only. | `NativeWidget` remains compatible; WebView demonstrates lazy, owned, signal-aware specialized native integration. |
| No public plugin loading boundary. | Explicit `PluginAPI`, namespaces, renderer capabilities, and opt-in entry points isolate external packages. |

## Compatibility and remaining risks

Existing public imports, builders, markup syntax, static transform, native `Native`, Qyro/Pydux integration, reconciliation identity, stable event callbacks, hooks, scheduling, and cleanup pass characterization and regression coverage. No application must register built-ins or rewrite markup.

WebEngine may emit harmless GPU diagnostics under virtual/offscreen display. Native extension behavior remains backend-specific by design, and benchmark thresholds should only compare runs with the same Python version and host. No known functional regressions remain in the validated environment.

## Migration guidance

Existing applications require no migration. New component libraries should use `ComponentRegistry`/`register_component`, `ComponentAdapter`/`register_adapter`, and an optional dot namespace. See `docs/tutorial-adding-portable-widgets.md`, `docs/tutorial-adding-native-widgets.md`, and `docs/refactoring/plugin-api.md`.
