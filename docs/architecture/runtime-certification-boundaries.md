# Runtime and certification module boundaries

This document is normative for contributors, agents and CI.

## Ownership

- `psx/` contains importable **production functionality**: the SFLE solver, model, snapshot translation, native measurement, adapters, viewport and lifecycle helpers, and policies that affect runtime behavior.
- `tests/` contains executable tests, fixture data, semantic oracles, certification contracts, coverage inventories, expectation matrices and JUnit execution-receipt validators.
- `scripts/` contains development-only CLIs and report generation. Keep any reusable certification logic under `tests/certification/`, not in `psx/`.
- `.github/workflows/` invokes the scripts and stores execution artifacts; workflows MUST fail on missing, skipped, mismatched or failed required receipts.

**Never add milestone-named audit artifacts** (for example `f3_g2_c6_matrix.py`, `f3_g2_c6_receipts.py`) under `psx/sfle/` or another production package. A phase identifier is not evidence of runtime ownership. Do not move functional modules merely because their names start with `f3_`: inspect their imports and call sites first.

## Required review for each new module

1. Identify who imports/calls it in a *packaged application*, as distinct from tests and CI. If only tests or CI use it, keep it outside `psx/`.
2. Identify the proposed directory, public API and dependency graph. Production code must never import `tests`, pytest, JUnit parsers or certification-only tools.
3. Before relocating existing code, inventory all direct imports, `python -m` invocations, test references, workflow commands, packaging configurations and docs. Preserve the runtime behavior and execution evidence.
4. A relocation is not complete until corresponding paths/imports and CLI entrypoints are updated, Python tests execute, the production wheel is inspected and CI checks are green. Never mark such work complete on documentary evidence alone.
5. Do not silently merge operation-specific certifications. Every applicable backend/component/operation remains separately accounted for; missing or skipped runs are not passes.
6. Shared receipt validation should identify a test by full suite/class/method and declared parameter cases, not method basename alone. Report schema and expected tests must be explicitly versioned.

## Existing technical debt

The F3-G2 work introduced production-package modules containing certification-only concerns: `f3_g2_c4.py`, `f3_g2_c4_receipts.py`, `f3_g2_contracts.py`, `f3_g2_evidence.py`, `f3_g2_matrix.py`, `f3_g2_oracles.py` and `f3_g2_receipts.py`. The implementation of these seven modules was relocated to `tests/certification/`. The old paths currently contain only compatibility re-export shims so existing imports and `python -m` commands continue to work. Migrate remaining callers and CLI invocations to the canonical paths, then delete the shims and reduce the guard allowlist. Their existence is **not** permission to add new peers. `f3_native_coverage.py` may be consumed by runtime adapters; inspect its actual consumers and split mixed runtime/certification responsibilities rather than relocating it wholesale.

## Architectural guard

`scripts/check_runtime_boundaries.py` rejects new certification-only modules in the production SFLE package, with an explicit, finite legacy allowlist. Shrink that allowlist as modules are migrated; never expand it for new work.
