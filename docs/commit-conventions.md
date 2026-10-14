# Commit message conventions

Commits must be understandable to a new developer without opening the phase or gate roadmap. The subject describes the **change**, not the project-management milestone.

## Format

```text
<type>(<scope>): <imperative, behavior-specific subject>

<optional explanation of behavior and rationale>

Phase: F3
Gate: G2
Block: C3
```

The final metadata is **optional**; omit it if the PR already supplies sufficient traceability. The body and metadata are not required for small, obvious changes.

- Use English, imperative mood, and one technical change per subject.
- Conventional types: `feat`, `fix`, `test`, `refactor`, `perf`, `docs`, `ci`, `chore`.
- Scope identifies the changed subsystem, **not** its roadmap location. Common scopes: `sfle` (neutral mathematical engine only), `layout` (layout integration/viewport), `renderers` (native backends), `components`, `measurement`, `reconciler`, `events`, `ci`, `docs`.
- Tell the reader **what** changed. Add why/how in a body when necessary.
- If an API breaks, use `!` and a `BREAKING CHANGE:` footer as appropriate.
- Never rely on `F3`, `G2`, `C2`, or similar milestone identifiers to explain a change. They are allowed as contextual identifiers in a descriptive subject if useful, but must never be the main information.
- Do not retroactively amend, squash or force-push historical commits for this convention.

## Examples

| Avoid | Prefer |
| --- | --- |
| `docs(layout): certify C2 evidence matrix` | `docs(layout): explain per-component evidence and unverified lifecycle operations` |
| `feat(renderers): implement F3-G2-C1` | `feat(renderers): apply shared layout rectangles to native widgets` |
| `test(layout): complete G2 lifecycle tests` | `test(reconciler): preserve widget identity during keyed reordering` |
| `fix(sfle): resolve F2 geometry issue` | `fix(sfle): prevent cumulative rounding drift in nested flex layouts` |
| `ci: complete C2 certification` | `ci: reject missing per-component execution receipts` |
| `feat(layout): implement G3 Scroll` | `feat(layout): synchronize scroll content geometry with viewport offsets` |

## Automated check

The lightweight PR commit-subject check in `.github/workflows/commit-subject.yml` checks **the PR head commit only**. It refuses invalid Conventional Commit headers, milestone-only subjects, and generic completion labels. It does not reject historical commits already in the branch, parse commit bodies, or run product tests. It is a guardrail, not a substitute for human review of clarity.
