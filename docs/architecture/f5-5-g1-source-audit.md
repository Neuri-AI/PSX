# F5.5 G1 — Source audit, preliminary findings

**Status:** IN PROGRESS; this is a root-export snapshot, **not** a complete G1 census or certified API reference.
**Canonical audit input:** [develop at `83d30afc68de5e21b736b1299185d5efaf86bf9b`](https://github.com/Neuri-AI/PSX/commit/83d30afc68de5e21b736b1299185d5efaf86bf9b).
**Mechanical inventory:** [f5-5-api-exports.json](f5-5-api-exports.json).
**Reproduce from repo root:** `python scripts/docs/api_census.py --check docs/architecture/f5-5-api-exports.json`;
`python -m pytest tests/test_docs_api_census.py -q`.

## Verified from source at the input SHA

- `psx/__init__.py` exposes **57 distinct names** in its explicit `__all__`. Historical 56/59 counts are superseded for this snapshot; do not treat the count as evidence of completeness of **other** public submodules.
- Distribution metadata in `pyproject.toml` names the package `velto` (Python `>=3.10,<3.14`); import spelling in the actual source is `psx`. Optional dependency groups include `pyside6`, `pyside2`, `pyqt6`, `pyqt5`, and `kivy`. Exact tested backend OS/Python cells have not been audited.
- `psx/core/hooks.py`: `use_state(initial)` returns current state and a setter; a setter called during rendering raises `ThreadViolationError`; `use_ref(initial=None)` returns stable `Ref.current` within the mounted hook slot; `use_effect(callback, dependencies=None)` supports optional cleanup and dependency equality semantics. All require a component render context and have hook order constraints. `use_memo` is **not** in the audited root exports.
- `psx/plugins.py`: `PLUGIN_ENTRY_POINT_GROUP = "psx.plugins"`; `load_plugins(..., plugins=(), discover=False, ...)` registers explicit plugins, and discovers installed entry points **only** when asked. Installing a plugin distribution is therefore not by itself evidence of automatic registration. `PluginAPI` is scoped to its component registry and renderer map.
- `psx/app.py`: `App(root, *, renderer=None, providers=(), settings=None)` supports the identifiers `headless`, `pyside2`, `pyside6`, `pyqt5`, `pyqt6`, `tkinter`, `kivy`. Its `settings` mapping accepts only `grid.breakpoints`; window/title settings must not be fabricated as `App(settings={...})` keys. `renderer=None` tries Qyro settings and can raise `RendererConfigurationError` without a configured Qyro dependency.
- `psx/core/vnode.py`: `create_element` validates key types and native-child restrictions; `Grid` only permits direct `GridItem` host nodes or component nodes, and `GridItem` requires exactly one root; `Box` exists internally and is not listed in root `__all__`.
- `docs/architecture/f5-expressive-markup-contract.md`: static numeric attributes use quoted strings (e.g. `gap="12"`); M4B authored expression lowering is distinct from the restricted runtime interpreter. Do not publish unverified executable snippets.

## Outstanding before G1 may close

1. Inspect **all** public submodules, aliases, registries, component contracts, events, child policies, exceptions, signatures/defaults and renderer implementations. The JSON snapshot only describes the root `__all__`.
2. Attach behavior-specific **test paths** and full native capability/OS/Python matrices to every supported API; reconcile contradictions with old docs and identify unsupported cells.
3. Execute the checked-in audit tool and its tests in a complete checkout, integrate it into CI, and capture immutable SHA plus Github Actions jobs. Neither source audit nor native verification is certified by creating this file.

## Scope boundary

No new framework behavior is authorized by this audit. F6/M8, Pydux, Qyro Engine and Velto CLI integrations remain deferred.
