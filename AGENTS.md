# PSX contributor and agent instructions

These rules apply to every change in this repository. Consult [Commit message conventions](docs/commit-conventions.md) before committing.

## Commit messages

Use Conventional Commits in English:

```text
<type>(<subsystem>): <imperative description of the actual change>
```

Write a self-contained subject understandable without consulting the roadmap. Name the observable behavior, invariant, API, test or documentation that changed. Do not use milestones (`F3`, `G2`, `C2`, `F3-G2-C3`, etc.) as substitutes for the description or as generic scopes. Avoid subjects like `complete G2`, `certify C2`, `implement F3`, `finish milestone`, or `update docs`. A documentary change should say which contract or behavior it documents.

Choose a real subsystem scope: `sfle` (only the renderer-neutral math engine), `layout`, `renderers`, `components`, `measurement`, `reconciler`, `events`, `ci`, or `docs`. Use another specific subsystem only when appropriate. The conventional types include `feat`, `fix`, `test`, `refactor`, `perf`, `docs`, `ci`, and `chore`.

Put optional traceability labels (`Phase: F3`, `Gate: G2`, `Block: C3`) in the commit body or PR, never in place of a meaningful subject. Explain why a non-obvious change was made in the body; mark breaking changes using Conventional Commits. Do not rewrite old commits just to conform to this policy.

## Validation

Retain selective CI and exact-SHA certification requirements. A docs-only update must not trigger product tests. Do not claim a workflow's skipped tests are executed evidence. Do not mark a gate CLOSED without its full evidence.

## Runtime versus certification code

Read [Runtime and certification module boundaries](docs/architecture/runtime-certification-boundaries.md) before adding or moving modules. Keep test-only contracts, evidence matrices, oracles and JUnit validators under `tests/certification/`, not `psx/`. Preserve actual runtime adapters. Never add new `f*_g*_...receipts`, `...matrix`, `...evidence` or `...contracts` modules to production. CI enforces a finite legacy exception list; do not extend it.
