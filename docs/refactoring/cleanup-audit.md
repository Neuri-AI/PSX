# REF-M10 cleanup audit

## Baseline and method

Before cleanup, the Conda `playground` suite passed with 147 tests and no skips. The audit used repository inventory, public-export review, import/reference searches, existing characterization tests, dependency checks, documentation link review, and compilation checks. Static “unused” reports were treated as leads only; public exports, entry points, renderer dispatch, markup resolution, and framework lifecycle hooks were preserved unless runtime evidence proved otherwise.

## Candidate classification

| Candidate | Classification | Decision |
| --- | --- | --- |
| Root and `psx/` `.DS_Store` | Safe to remove | Removed: generated macOS metadata, already ignored. |
| Duplicate `RendererCapabilityError` import in PySide6 renderer | Safe to remove | Removed one duplicate import. |
| README `docs/text.md` link | Safe to consolidate | Changed to `docs/components/text.md`. |
| README legacy native-interoperability link | Safe to consolidate | Changed to the maintained native-widget tutorial. |
| `benchmarks/reconcile.py` | Must preserve | A compatibility command wrapper; reference searches cannot prove external command-line use absent. |
| `docs/m10-native-interoperability.md`, old milestone documents, and `docs/refactoring/*` history | Must preserve | Useful implementation/historical decisions; no deletion solely for duplicated explanation. |
| `repomix-output.xml` | Requires further investigation | Untracked generated artifact with unknown user ownership; not deleted. |
| Public builders, `Native`, registry/adapter APIs, plugin entry points, devtools, integrations, and renderer methods | Must preserve | Public, dynamically resolved, or lifecycle-dispatched surfaces. |

## Consolidation and documentation

The maintained architecture/tutorial documents already describe contracts, registries, adapters, plugins, Checkbox, and WebView. The README now targets those maintained paths. Historical docs remain deliberately separated from current API documentation. `.pytest-*` was added to `.gitignore` to avoid generated local test directories polluting repository inspection.

The audit also corrected the M12 playground relative link so it resolves from `docs/` to the standalone project at the workspace root. Internal Markdown link verification then completed without broken links.

## Dependencies and hygiene

`python -m pip check` reports no broken requirements in `playground`. Project extras match runtime-tested optional backends: PySide6, PyQt5, PyQt6, Kivy, Qyro, and Pydux. No dependency was removed because every optional extra is exercised by a supported renderer or integration. Ruff is not installed in this environment, so it was not represented as a successful check; compilation and the full test suite are the recorded static/runtime validation.

## Remaining technical debt

- Benchmark timing comparisons should continue to use the same Python version and host.
- `repomix-output.xml` needs ownership confirmation before removal.
- Native extensions remain backend-specific and need their own lifecycle tests, by design.

No confirmed dead internal production code remains in the audited scope.
