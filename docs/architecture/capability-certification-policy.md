# F4 capability certification and intelligent CI policy

**Status:** normative for F4 and subsequent PSX development. This is a development process contract, not an assertion that any F4 capability has shipped.

## Mandatory three-part acceptance rule

Whenever a change adds or extends a public capability, deliver **all applicable** items in the same development increment:

1. **Behavior-specific functional tests.** Cover the new positive behavior, boundaries, invalid inputs, state updates, lifecycle and regressions, and relevant native backend behavior. Generic smoke tests, unrelated examples and documentation are not executed functional evidence.
2. **Intelligent CI routing.** Review and extend `scripts/ci/impact.py` to map the new production/test paths to every affected backend and transitive consumer. Add or update `tests/test_ci_impact.py` cases proving positive selection, unaffected-backend exclusion, combinations of changed paths and conservative fallback for unknown changes. Update the actual workflow when new suites are needed; a selector entry without an executable required job does not provide coverage.
3. **Public-behavior census evidence.** When the capability adds public props, events, methods or meaningful interactions, update the code-derived public-behavior inventory, applicability policy and behavior-specific test cases/receipts under `tests/certification/`. A required cell must point to an actually executed relevant test for the correct backend, operation and tested SHA. Never mark documentation, indirect tests, skipped jobs or non-executed manifests as PASS.

Changes without a public surface must explicitly establish why the third item is not applicable rather than inventing receipts. Backend applicability and unsupported behavior must be explicit and fail closed. Do not blindly apply a Qt expectation to Kivy/Tkinter/Headless.

## Increment closure checklist

A capability is eligible for closure only if:
- Its specification and public contract are recorded, including negative/fail-closed behavior.
- Functional RED/GREEN tests genuinely exercise the advertised behavior on relevant supported backends.
- The selector routes implementation, tests, and shared dependencies to the correct suites, with executable router tests and no silent gaps.
- All newly applicable public census cells have reviewed, **executed** receipts; N/A has a documented rationale; there are no unsupported PASS claims.
- Required CI checks are GREEN for the exact code SHA being certified. Failed, cancelled, in-progress or skipped checks are not PASS.

Preserve existing certification evidence and cross-backend regressions; do not weaken or delete tests just to make an increment green. For docs-only changes, `scripts/ci/impact.py` must select **zero product tests**, retaining the existing lightweight routing/status behavior only.

## F4 scope and boundaries

F4 is the planned responsive **12-column Flexbox Grid** stage. Consult `docs/roadmap.md` and approved F4 design/implementation documents to determine exact components, props, grid breakpoints and official gates; **do not invent gates or claim they are implemented**. F3's native Flex/Scroll and renderer integration remain regression baselines. The separately deferred `SFLE-CSS-01` and `SFLE-CSS-02` are not silently absorbed into F4 without a separate explicit scope decision.

Use descriptive names for source files, tests, scripts, receipts and runtime contracts. Phase/gate codes are planning metadata and belong in roadmap/PRs rather than opaque implementation names. Test-only artifacts live under `tests/certification/`, never under `psx/`.
