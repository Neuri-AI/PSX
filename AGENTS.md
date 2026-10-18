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

## Semantic names: roadmap identifiers are not code vocabulary

**Mandatory for humans and coding agents, including fresh agent sessions.** Internal planning and certification identifiers (for example `P0`, `P0.9`, `P1`, `P2`, `F1`, `F4`, `G2`, `C07`, `IM-01`, `AD-03`) are **tracking metadata only**, not descriptive names. Never introduce these identifiers into:

- Production or test **function, class, method, variable, constant, type, package, or module names**.
- Source filenames, test filenames, CI job/workflow filenames or workflow display names.
- Source-code docstrings, inline comments, exception messages, log entries or user-facing text **as substitutes for explaining the behavior**.
- Public API names, imports, example snippets or documentation code blocks.

Name things by **what they do or guarantee**, not by the milestone that paid for them. For example:

| Avoid | Prefer |
| --- | --- |
| `test_p0_kivy_heap_ownership.py` | `test_kivy_heap_ownership.py` |
| `p0_memory_soak.py` | `native_widget_memory_soak.py` |
| `test_f1_box_model()` | `test_box_padding_excludes_content_area()` |
| `prepare_f3_snapshot()` | `prepare_native_layout_snapshot()` |
| `# F4 G3 fix` | `# Release native bindings before the widget is discarded.` |
| `P1 canonical box style CI` | `Canonical box style tests` |

**Permitted traceability:** phase/gate IDs may appear in planning documents, issue IDs, ADRs, historical evidence paths, release checklists, and commit/PR **bodies** when they serve as cross-references **alongside a descriptive explanation**. A technical document may keep an existing roadmap ID in its title for navigation, but its code samples and implementation names must remain semantic. Do not rename historical artifacts merely to erase valid audit trails.

**Before every commit:** review changed identifiers, filenames, comments and workflow names for phase/gate tokens. If any new occurrence is not essential tracking metadata, replace it with a behavioral description. When touching existing legacy code, prefer descriptive naming for the new work; plan backwards-compatible migrations for existing public or cross-referenced symbols rather than breaking them opportunistically. Never use a phase label as a stand-in for an explanation.

## Validation

Retain selective CI and exact-SHA certification requirements. A docs-only update must not trigger product tests. Do not claim a workflow's skipped tests are executed evidence. Do not mark a gate CLOSED without its full evidence.

## New capability acceptance: functional tests + CI routing + public census

**Mandatory from F4 onward:** every newly implemented capability must include
(1) behavior-specific functional tests, (2) correct impacted-backend and
dependency routing in `scripts/ci/impact.py` with selector tests in
`tests/test_ci_impact.py`, and (3) executed public-behavior census cases and
receipts whenever public props, events, methods or interactions are added.

No capability is complete if one applicable part is missing. Do not treat
skipped tests, documentation references or unrelated tests as executed evidence.
Explicitly justify census N/A for changes with no new public behavior.
Documentation-only diffs continue to select ZERO product tests.

**Read and follow**
[Capability certification policy](docs/architecture/capability-certification-policy.md)
before implementing or reviewing any new F4+ capability.

## Runtime versus certification code

Read [Runtime and certification module boundaries](docs/architecture/runtime-certification-boundaries.md) before adding or moving modules. Keep test-only contracts, evidence matrices, oracles and JUnit validators under `tests/certification/`, not `psx/`. Preserve actual runtime adapters. Never add new `f*_g*_...receipts`, `...matrix`, `...evidence` or `...contracts` modules to production. CI enforces a finite legacy exception list; do not extend it.

## Approved responsive Grid development (F4)

Before any F4 planning, implementation, review, or certification, read
[Responsive 12-column Grid contract](docs/architecture/responsive-grid-contract.md)
and [Capability certification policy](docs/architecture/capability-certification-policy.md).
The owner approved the contract on 2026-10-14. Six planning gates (G1–G6) are
approved; **approval does not mean shipped or certified**. Determine gate status
from current source, executed tests, same-SHA CI and census receipts.

Preserve the approved semantics: Grid/GridItem, exactly 12 columns,
distributive `auto` sharing residual row width, automatic wrapping (a full
12-column item is followed by a new row for auto items), logical offsets,
explicit intrinsic overflow rather than silent span mutation, container-local
breakpoints and independent nested Grids. Keep strict unsupported diagnostics,
Cinnamon's sole layout authority, Rust primary/Python parity, existing native
Qt/Kivy/Tkinter/Headless adapters, Flex/Scroll and reconciler identity guarantees.
Do not implement CSS Grid tracks or deferred SFLE-CSS-01/02 implicitly.

Implement in approved order: G1 public contract/normalization; G2 Cinnamon
math; G3 native renderers; G4 responsive composition; G5 robustness; G6
immutable-SHA certification. At every increment implement exactly the needed
functional tests, `scripts/ci/impact.py` coverage plus
`tests/test_ci_impact.py` routing tests, and executed public census cases/receipts
under `tests/certification/` when a public operation is introduced. Verify
selected workflow jobs actually run those tests. No skipped, borrowed or
unexecuted evidence passes. Docs-only changes must run ZERO product tests.

For audits, use [F4 audit and continuity prompt](docs/architecture/responsive-grid-agent-audit-prompt.md).
For the first coding increment, use
[Grid public contract implementation handoff](docs/architecture/responsive-grid-implementation-handoff.md).
