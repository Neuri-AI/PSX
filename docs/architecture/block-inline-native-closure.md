# Block/Inline native integration and HTML-like vocabulary — closure record

> Status: **CLOSED** (scoped implementation/certification increment, historically tracked as P1.3 and AD-06).
> Certified source commit: `468ca632d6d5fdd7b1c99745d19c8df138615819`.
> Integration branch: `feature/universal-box-model-and-styling`.
> Recorded: 2026-10-19.

## Accepted scope

- Implement the approved **21 HTML-like markup tags** using the existing component aliases or explicit formatting hosts. Native generic Block/Inline hosts are **not** silently converted to Flex.
- Native Block/Inline measurement, layout projection and lifecycle via Cinnamon and the existing Qt, Tkinter and Kivy adapters.
- Complete the last four vocabulary entries: `form` (native control submission gesture dispatch), `label` (implicit nested input activation/focus), `ul` (Block list container) and `li` (measured bullet/text item).
- Preserve existing public components and Grid/Flex behavior, keyed reconciliation, mount/unmount and event lifecycle.

## Evidence and closure decision

The above behavior was implemented in the integration branch by the certified source commit. GitHub Actions reported **nine completed/successful workflow families on that exact SHA**:

1. Native layout selective validation.
2. Canonical box geometry certification.
3. Flex layout contract certification.
4. Grid integral certification.
5. Runtime package boundaries.
6. Declared surface audit.
7. Beginner example behavior.
8. Lexical component Python runtime.
9. Commit subject clarity.

Source: https://github.com/Neuri-AI/PSX/commit/468ca632d6d5fdd7b1c99745d19c8df138615819

The final source change fixed Tkinter input focus on implicit `label` activation. The final workflow conclusions were all successful; selected sub-jobs that did not run must **not** be described as executed.

The approved, bounded Block/Inline/HTML-like increment **meets its implementation and exact-SHA CI acceptance criteria and is closed**. This record documents closure of that increment only; **P1 as a whole remains OPEN**, and PR #48 must remain open/draft until its full architecture exit criteria are met and the owner approves integration.

## Explicit non-goals / not certified

- Explicit `label html_for` linkage.
- Full browser HTML form constraint validation or native HTML submission semantics.
- General CSS list styling, complete browser CSS, and full CSS Grid tracks.
- Whole-phase P1 CSS Core, general stylesheet cascade or arbitrary computed-style/native painting.
- Unsupported backend combinations not actually executed in CI.

## Next bounded increment

Start internal CSS Core foundations **under `psx/css/`**, with unit tests **under `tests/css/`**. First re-check the approved CSS architectural contract and resolve any public precedence/value decisions before implementing affected semantics. Keep Cinnamon as the only layout authority and preserve existing PascalCase widget APIs and the certified 21-tag vocabulary.

For every introduced capability follow `AGENTS.md` and `docs/architecture/capability-certification-policy.md`: behavior-specific tests, selective CI impact routing and selector tests, applicable public census receipts, and exact-SHA CI evidence. Documentation-only changes must select zero product tests.
