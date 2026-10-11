# SFLE F3 — Intelligent CI and test selection policy

> **NORMATIVE F3 HANDOFF — 2026-10-11. Implementation status: SELECTOR IMPLEMENTED, FIRST CI VERIFIED.**
> Feature branch: [`feature/f3-sfle-native-adapters`](https://github.com/Neuri-AI/PSX/tree/feature/f3-sfle-native-adapters), forked from
> `develop` at `979b6ed9e86c63b640d498439045910ed1a189aa`.
> The change selector is now implemented in `scripts/ci/impact.py`,
> verified by `tests/test_ci_impact.py`, and wired to
> `.github/workflows/f3-selective.yml`; F2 workflows are retained on
> `main` or explicit manual dispatch while F3 PRs into `develop` use
> selective routing. [Verified run #38150107662](https://github.com/Neuri-AI/PSX/actions/runs/38150107662)
> finished GREEN on SHA `41860ae5553ee9d8c398f0b28b9dc479be8a69e1`.
> This is an incremental selector certification, **not** G5 full F3 closure.
> Authority: [F3 implementation plan](sfle-f3-implementation.md),
> [F2 certified contracts](sfle-f2-final-certification.md) and
> [F2-to-F3 migration](sfle-f2-migration-plan.md).

## 1. User-approved rule and mandatory outcome

**Every CI execution must be proportional to the changed behavior and its
dependencies. Documentation-only commits/PRs must trigger ZERO unit,
integration, Chromium, native GUI, Rust, wheel, frozen or benchmark tests.**

The only permissible automated work for a docs-only PR, if branch protection
requires a named check, is a lightweight change-classifier/status job that
reports `docs_only=true` and `tests_selected=[]`; it must install no toolkits,
Rust or Python dependencies and run no tests. Otherwise use
`paths-ignore` to avoid launching a workflow at all. Markdown link/style
validation can be separately requested later, but is **not** a unit-test
dependency and must not be silently classified as product-code testing.

Changes that can alter layout, component identity, public imports, native
widget behavior, runtime selector or packaging MUST run all impacted suites,
including transitive dependency consumers. **Fast selective verification is
the default on each F3 iteration; full certification is an explicit gate,
not an automatic penalty for every commit.**

## 2. Existing F2 workflows — verified inventory and defects

As inspected on the F3 base `979b6ed9e86c63b640d498439045910ed1a189aa`
(the exact same workflow YAMLs were still present in the initial F3 commit):

| Workflow (real file) | Current useful tests | Selection problem to fix in F3 |
| --- | --- | --- |
| `.github/workflows/ci.yml` — PSX alpha validation | Core/markup, hooks, Qt offscreen lifecycle, build/benchmark | `push` on `main` ignores docs, but **`pull_request` is unrestricted**. The `changes` job emits `code` yet **`core`, `pyside6`, `package` do not use `needs: changes` / `if:`**; a docs-only PR therefore starts expensive jobs. |
| `.github/workflows/sfle-core.yml` — SFLE core checks | Python 3.10–3.13, Rust unit, Python/Rust differential, installed PyO3, historical Row/Column/Scroll inventory | Unrestricted `pull_request`; the `changes` job emits `sfle` but **no downstream job consumes it**. Core, Rust, differential, wheel and external-boilerplate inventory all run even for docs-only or unrelated code changes. |
| `.github/workflows/sfle-chromium.yml` | Playwright Chromium vs SFLE, browser holds, seeded tests | `pull_request` is unrestricted; `push` path filter is partial and currently lists only one browser test path. Expensive browser install/tests must only follow layout-affecting changes or explicit release request. |
| `.github/workflows/sfle-ui-certification.yml` | Real Qt/Tk/Kivy widget readback under Xvfb | PR paths are restricted to `psx/sfle/**`, `tests/ui/**` and its own YAML; **new F3 renderer edits in `psx/renderers/**` are not included**. Extend coverage to changed backend adapters and shared widget geometry ports. |
| `.github/workflows/sfle-native-matrix.yml` | Windows/macOS Intel/ARM64 native wheel, ABI, frozen executable and no-Rust fallback | Already path-filtered on PR/push, which is good; add relevant F3 packaging/native loader triggers. Do not run this costly matrix for pure docs, ordinary widget labels/events or a single toolkit-only adjustment absent a native/build effect. |

**Do not remove F2 tests or lower their assertions.** Reuse suites when
relevant; convert the costly `f2-migration-inventory` job into a
G4 migration audit invoked only by Row/Column/registry/export/legacy
migration changes and the G4/G5 gates. Its pinned external Qyro
repository checkout is NOT a mandatory side effect of every F3 patch.

Workflows may be **refactored or reused**, not duplicated blindly. Existing
test names with `f2` prefixes remain valid regression assets.

## 3. Mandatory change categories and test dependencies

The dispatcher must derive selected suites from the **union** of changed
paths (including rename's old and new paths), matching categories and their
transitive dependents. Run the **union** when multiple categories apply.
Concrete initial map:

| Change category and matching paths | Minimum selected validation for incremental PR | Explicit expensive-suite policy |
| --- | --- | --- |
| **Docs-only**: `docs/**`, `README.md`, `**/*.md` and approved docs-only assets | **No tests, no toolkit install, no benchmarks**. If needed, only `ci-routing` lightweight success status. | Chromium, native, Rust, wheels and full suite **OFF**. |
| **Flex/core API**: `psx/core/**`, `psx/markup/**`, `psx/__init__.py`; registry, builders, props, contracts, validators | Core component registry/contract/markup tests; F3 G1 Flex negative/positive; G2 registry-to-test census; generic Headless and affected lifecycle unit tests. | Run every backend's focused bridge tests if shared layout metadata, node identity or normalized tree mapping changed; **no wheel build solely because a prop validator changed**. |
| **Coordinator/geometry ports**: shared SFLE bridge/worker, `psx/sfle/adapter_contract.py`, `native_geometry.py`, scheduler, snapshot mapping | Focused `tests/sfle` authority/readback/worker tests, F3 coordinator + cross-backend G2 contract cases and Headless. | If layout numerical semantics changed: add **Rust/Python differential + Chromium**. If only UI commit/adapter wiring changed: add affected native UI suites; do not automatically rebuild Windows/macOS wheels. |
| **Python/Rust layout algorithms and schemas**: `psx/sfle/compute_alpha.py`, `psx/sfle/model.py`, `psx/sfle/backend.py`, `rust/sfle-core/src/**`, cross-language normalization | Python SFLE contract tests + Rust tests + Rust/Python differential, supported/unsupported diagnostic parity and applicable pure Headless fixtures. | **Chromium oracle ON** for geometry/rounding/line-placement changes. **Native wheel/ABI** ON for Rust/PyO3/schema/build/loader changes; not for an unrelated Python-only test fixture. F2's fixed CSS scope and tolerances remain unchanged. |
| **Specific native renderer**: `psx/renderers/qt/**`, `kivy/**`, `tkinter/**` and corresponding backend tests | Only the **affected toolkit's** existing regression, F3 G2 component/backend cases, widget geometry/readback/identity and relevant G3 Scroll cases. | Shared renderer base / generic adapter protocol modifications fan out to **all affected toolkits**. No Chromium unless SFLE outputs or coordinate/projection semantics change; no other toolkit just for a backend-local widget style fix. |
| **Headless**: `psx/renderers/headless.py` or Headless-specific tests | Headless renderer, G2 registry/port tests, pure SFLE geometry and snapshot parity for impacted components. | No live Xvfb, other GUIs, Playwright or native wheel by default. |
| **Scroll**: native `scroll.py`, shared `psx/renderers/components/scroll.py`, Scroll host/port code | Affected toolkit Scroll events/offset/clipping plus `tests/sfle/test_f2_point4_authority_red.py` and `test_f2_point4_cross_backend_contract.py`; verify nested Scroll and immutable SFLE content. | Shared Scroll semantics trigger all relevant Qt/Kivy/Tk/Headless Scroll contract tests and real GUI integration; browser only if SFLE content geometry/oracle changed. |
| **Third-party / Native bridge**: `psx/core/native.py`, `register_primitive`/`register_adapter` code, generic adapter contract | G2 custom-primitive and Native positive/adversarial cases, ownership/readback/disposal, relevant backends and registry census. | Cross-toolkit when generic contract changes; one toolkit when backend-local. |
| **Build/packaging**: `pyproject.toml`, `rust/sfle-core/Cargo.toml`, Rust FFI, extension selector/loading, distribution/frozen probe | Package/build check, import/source/frozen and native-vs-fallback tests; relevant Rust/ABI suites. | Windows/macOS wheels and frozen matrix ON for ABI/runtime/distribution-affecting changes; Python dependency-only changes get packaging + appropriate imports, expanding when platform semantics warrant it. |
| **CI/router config**: `.github/workflows/**`, new `scripts/ci/**` or change classifier/tests | Validate dispatcher/unit routing fixtures and affected YAML/workflow syntax/paths; run the **workflow whose semantics changed**, where executable. | Do not force all workloads for a docs/comment-only YAML edit. Fail closed for classification uncertainty or disabled required coverage. |
| **Legacy Row/Column removal**: public API, markup, adapters, migration scripts/examples | Focused G4 no-alias/unknown-tag/import rejection, registry census, legacy-geometry authority scan and affected renderer tests. | Full historical external boilerplate inventory only for the G4 release gate or when affected. Do not run external git clones on unrelated commits. |
| **Broad/shared unclassified code changes** | Conservative full **relevant** core + backend integration suites; report the reason. | Unclear shared engine/platform impact must fan out, never quietly skip required suites. |

`tests/sfle/**`, `tests/interop/**`, `tests/browser/**` and
`tests/ui/**` should select their relevant test family when changed,
even if production source is unchanged. For a test-only change execute
its test plus indispensable fixtures; do not automatically rebuild all
wheels/GUI toolkits. Distinguish `tests/interop/test_sfle_f2_native_wheel.py`
(native packaging) from `tests/interop/test_sfle_f2_differential.py`
(pure engine parity).

**Concrete currently-existing examples for router validation:**

- Core+Markup: `tests/test_component_contracts.py`,
  `tests/test_component_registry.py`, `tests/test_markup_registry.py`,
  `tests/test_markup.py`, `tests/test_markup_transform.py`.
- Hooks/reconciliation: `tests/test_core.py`,
  `tests/test_hooks_scheduler.py`, `tests/test_renderer_adapters.py`.
- Native backend regressions: `tests/test_pyqt_renderer.py`,
  `tests/test_pyside6_renderer.py`, `tests/test_kivy_renderer.py`,
  `tests/test_tkinter_renderer.py` plus toolkit-targeted F3 tests.
- F2 reusable SFLE contracts: `tests/sfle/test_f2_point4_authority_red.py`,
  `tests/sfle/test_f2_point4_cross_backend_contract.py`,
  `tests/sfle/test_qt_native_lifecycle.py`,
  `tests/ui/test_sfle_real_toolkit_geometry.py`.
- Rust/Python: `tests/interop/test_sfle_f2_differential.py`,
  `tests/interop/test_sfle_f2_point5_deferral_boundaries.py`;
  browser: `tests/browser/test_sfle_chromium.py` and F2 oracle suite.
- Packaging: `tests/interop/test_sfle_f2_native_wheel.py`,
  `tests/interop/sfle_frozen_probe.py`.

**New F3 test modules are added to these groups when created**. Avoid
coding every test path into every workflow independently; maintain
one authoritative test-to-category map and use it from selectors.

## 4. Architecture for an intelligent GitHub Actions dispatcher

1. **One fast change classifier** (e.g. `ci-routing`): outputs boolean or
   JSON flags `docs_only`, `core`, `sfle_engine`, `geometry_bridge`,
   `qt`, `kivy`, `tkinter`, `headless`, `scroll`,
   `chromium`, `native_abi`, `packaging`, `legacy_removal`,
   `g2_registry_coverage`, `full_certification`.
   Report the selected tests, workflows and **why** each was selected.
2. **On a new PR or after any failed/canceled/unknown previous CI run**,
   classify the **entire cumulative PR diff**, not just the most recent
   `synchronize.before..after` delta. Paginate `pulls.listFiles`
   and include both sides of renames; missing/unsafe/truncated data must
   fail open to tests.
   **Safe incremental exception:** for a `synchronize` update, first verify
   that the exact preceding `before` SHA has a `completed/success`
   `F3 selective validation` run **associated with the same PR**.
   Only then may the selector inspect the new `before..after` delta,
   preserving the prior green coverage as evidence. If no exact green
   predecessor exists, if compare exceeds GitHub bounds, or any API
   request fails, revert to the complete PR file list (or all tests).
   This avoids needlessly rebuilding wheels on every subsequent
   unrelated/docs-only commit without allowing incomplete checks to
   masquerade as success.
3. **On push** use the event's `before..after` where reliable; on branch
   create, missing base, force push, ambiguous changes, classifier errors
   or incomplete files, conservatively widen to relevant full testing.
   For F3 development, prefer **one PR event path** over duplicate push
   and PR pipelines on the same SHA; target `develop`, then include
   `main` after merge when applicable.
4. **All expensive jobs must consume classifier outputs** with
   `needs: [changes]` and `if: ...`, or workflows must use
   sufficient `paths`/`paths-ignore`. **A `changes` job without
   dependent jobs is not optimization** (the current F2 anti-pattern).
   A path filter alone must account for shared dependencies and test paths.
5. Use job-level categories and matrix partitioning to install only
   needed dependencies. Qt offscreen does not need Playwright; Headless
   needs no GUI; Python unit tests should not build Rust wheels unless
   Rust ABI/native loading is involved. Cache pip/Cargo/Playwright tools;
   cache invalidation must include lock/dependency/toolchain versions.
6. Preserve clear required-check semantics. If branch protection demands
   a check on docs-only PRs, run **one tiny always-reporting router/summary
   status**, with skipped suites recorded as **not required**. Do not
   create permanently Pending required checks by suppressing workflows
   without replacing their status contract. Required aggregate check
   passes only when every *selected* job succeeded and every expected
   job reported; a skipped applicable test must not count as success.
7. Use `concurrency` with cancel-in-progress for obsolete incremental
   PR updates; retain **immutable SHA-aware final certification** jobs
   (never accept a canceled run as a pass). Record workflow name, exact
   `head_sha`, conclusion, test counts and decision rationale.
8. The selector itself must have tests. At minimum: docs-only, tests-only,
   Qt-only, Kivy-only, Tk-only, Headless-only, shared SFLE compute,
   Rust ABI, Scroll shared vs specific, metadata validator, new registry
   component, renames, multiple-category change, deleted tests, missing
   diff, >300 changed files and conflicting workflow edits. Assert no
   false negatives for cross-backend dependencies.

### Example selection (illustrative, not implemented)

| PR changed files | Expected checks | Not expected |
| --- | --- | --- |
| `docs/architecture/sfle-f3-implementation.md`, `README.md` | No tests; optional tiny required-status router | Every Python/Rust/Chromium/GUI/wheel test |
| `psx/renderers/qt/button.py` | Qt button/F3 G2, related Qt lifecycle | Kivy, Tk, Chromium, macOS/Windows wheels |
| `psx/core/props.py` | Shared props/registry/markup + affected Headless and backend integration metadata cases | Native wheel/Chromium unless compute semantics affected |
| `psx/sfle/compute_alpha.py` | Python SFLE, differential, Chromium, relevant engine holdout tests | All native wheels absent ABI/source packaging change |
| `rust/sfle-core/src/compute_layout.rs` | Rust unit, Rust/Python differential, Chromium; ABI/build validation when the extension path changes | Unrelated display-only GUI tests |
| `psx/renderers/kivy/scroll.py` | Kivy Scroll widget/geometry and SFLE Scroll authority contracts | Qt-only GUI suite and frozen wheel matrix |
| `tests/ui/test_sfle_real_toolkit_geometry.py` | Native UI test family | Rust/wheels/browser unless shared engine changed |
| `pyproject.toml` changing native extension build dependencies | Build and native ABI/fallback on affected platforms | Docs-only classification |
| `psx/core/registry.py` registering a new built-in | Registry tests, G2 census and that component's supported/unsupported backend matrix | Unrelated browser oracle if engine unchanged |

## 5. F3 G1–G5 scope gates and test policy

- **G1:** builder/registry/markup positive and adversarial Flex plus
  Scroll child-policy tests. Select core+markup+Headless; focused GUI
  bridge only if edited. Complete G1 acceptance still requires all its
  mandatory declared tests, not just those touched in the last commit.
- **G2:** every built-in/backend support cell and `Native`/custom
  primitive/adapters are part of the **required complete acceptance
  matrix**. *Incremental commits* run impacted cells; **formal G2
  closeout** runs the **entire** `registry × backend × operation`
  matrix, including negative unsupported cells, identity/events,
  remeasurement and readback, on one specified SHA. No `skip`/`xfail`
  may hide an applicable supported cell.
- **G3:** targeted toolkit Scroll cases while building; complete
  horizontal/vertical/nested real-widget and Headless suite at G3
  closure. Existing F2 point-4 authority tests remain mandatory.
- **G4:** targeted deletion/API/doc migration tests while editing;
  complete no-alias/grep, package import and external boilerplate
  audit at G4 closure.
- **G5:** **EXPLICIT FULL-CERTIFICATION OVERRIDE**:
  all core/markup, SFLE Python/Rust/differential, Chromium, Qt/Kivy/Tk
  real GUI, Headless, G2 registry census, Scroll, removals,
  native wheels/frozen fallback and cross-OS evidence on **one final SHA**.
  This is the only ordinary F3 stage that unconditionally schedules the
  expensive complete matrix.

**Important exception to docs-only behavior:** an explicit, authorized
`workflow_dispatch`/**G5 release or formal phase certificate** must
run full required CI on the chosen final SHA **even if its last commit
modified only documentation**. That is a release/certification request,
not ordinary docs-change CI. Do not repeat F2's documentation-only
PR triggering all tests as the default daily development policy.

## 6. Enforceability and migration checklist for the next agent

**Historical bootstrap checklist (the selective CI is now implemented and verified).** Before claiming
"intelligent CI enabled", the next agent must:

- [ ] Introduce and unit-test a single source-of-truth change classifier
      plus one shared impact-to-test map.
- [ ] Correct `.github/workflows/ci.yml`: core/Qt/package jobs
      must be conditioned on affected categories, including PR docs-only.
- [ ] Correct `.github/workflows/sfle-core.yml`: Python SFLE, Rust,
      differential, PyO3 and historical migration inventory must be
      independently selected; eliminate unconditional unrelated work.
- [ ] Restrict `sfle-chromium.yml` to engine/oracle relevant changes
      (including F3 test/fixture paths); preserve explicit manual dispatch.
- [ ] Expand `sfle-ui-certification.yml` triggers to relevant F3
      renderer adapter changes, not only `psx/sfle/**`.
- [ ] Preserve/extend `sfle-native-matrix.yml` for ABI and packaging
      triggers; avoid cross-OS frozen work for docs/UI-only patches.
- [ ] Add a fast, consistently named required status/aggregator if
      branch protection requires status on skipped docs-only checks.
- [ ] Add F3 G2 registry/backend impact metadata and complete G2
      certification override so selectivity never conceals missing
      component coverage.
- [ ] Test routing on **docs-only PR → 0 tests** and on multi-category
      PRs. Record costs/jobs and assert no applicable job was skipped.
- [ ] Demonstrate one full manual G5 dry-run and exact SHA checks
      before formal phase closeout.

**CI optimization itself is a F3 foundational engineering task**, ideally
started before high-volume G1/G2 iteration, **not** a sixth F3 gate.
No shortcuts are allowed on phase gate closures or known safety,
geometric precision, backend parity, identity or lifecycle guarantees.

## Real certification evidence — F3 bootstrap, 2026-10-11

- **F3 selected-suite baseline:** [Actions #38150107662](https://github.com/Neuri-AI/PSX/actions/runs/38150107662)
  completed **GREEN** on source SHA `41860ae5553ee9d8c398f0b28b9dc479be8a69e1`;
  Core, SFLE, Rust/Python, Chromium, Qt, Kivy, Tkinter, all three
  Windows/macOS ABI/fallback jobs and routing regressions succeeded.
  Headless was correctly skipped because no changes required it.
- **G1 first actual implementation:** [Actions #38150865981](https://github.com/Neuri-AI/PSX/actions/runs/38150865981)
  completed **GREEN** on source SHA `3210c8b77c0bb09152968c93321f396e9f72849c`.
  This includes the 58 Core cases with the new public Flex contract,
  all selected native/platform regressions, Chromium, engine parity
  and successful aggregate. This is **G1 IN PROGRESS**, not G1 CLOSED.
- **Docs-only revalidation:** This section's commit is intentionally
  documentation-only. Its GitHub Actions outcome must demonstrate that
  no product test is repeated (either the workflow is path-skipped or
  a tiny selection/status job succeeds with `selected=[]`). Verify
  that evidence independently before considering docs routing certified.

## 7. Handoff / response contract

Each F3 change should report: change category, exact diff base and head
SHA, selected suites and selection reason, skipped irrelevant suites,
actual outcome of every selected CI run and affected F3 gate status.
For a docs-only PR, say **"documentation only; no tests required by
routing policy"**, not "all tests GREEN." For a code change, do not
claim CI success before actual applicable workflows complete. For a
G1–G5 gate closeout, name every required run on the **same SHA**.

**Current status on document creation:** F3 implementation 0/5 gates
closed. Existing F2 workflows are reused conceptually but retain the
specific routing weaknesses documented in §2 until actual YAML/classifier
implementation is committed and tested.


## G1.2 proof and continued CI rules (2026-10-11)

- The new `psx/core/layout_tree.py` and G1.2 cases in `tests/test_f3_flex_contract.py` are covered by the Core path classifier. RED case: [#38153047652](https://github.com/Neuri-AI/PSX/actions/runs/38153047652). GREEN: [#38153141925](https://github.com/Neuri-AI/PSX/actions/runs/38153141925) on source SHA `3ac035b58cc90a1f3f0f05223a881bb96ab0dc2a` (70 Core tests, aggregate successful).
- G1.2 is an incremental structural contract, not full G1 acceptance; do not count G2/G3/G4/G5 as implemented.
- The full-registry G2 census, per-backend operations matrix, all required Chromium/GUI/packaging subsets and single-SHA G5 certification are still formal future gates. The prior checklist is historical implementation guidance, not a claim that every checkbox is complete.


## F3-G1 gate closeout — 2026-10-11

The dedicated [F3-G1 contract certification](../../.github/workflows/f3-g1-certification.yml)
is scoped to public builders, PSX Markup, normalization and negative diagnostics.
It runs the same 125-test contract suite on Python 3.10–3.13 (the supported
range in `pyproject.toml`). Backend fail-closed routing tests are checked by
the impacted Qt, Kivy, Tkinter and Headless suites, *not* inferred from pure
contract tests.

**Exact source SHA:** [`df6fe1c`](https://github.com/Neuri-AI/PSX/commit/df6fe1c107c98d9506944d10ced923a45f5608d7).

- [G1 matrix run #38155096426](https://github.com/Neuri-AI/PSX/actions/runs/38155096426):
  successful across all four supported Python versions, 125 tests each,
  final G1 verdict GREEN.
- [F3 selective run #38155096518](https://github.com/Neuri-AI/PSX/actions/runs/38155096518):
  selected Core, Headless, Qt, Kivy and Tkinter suites all GREEN with the
  required aggregator GREEN. Skipped Rust, Chromium, wheel and G4 jobs are
  **not** counted as executed or certified.
- **Formal F3 progress: G1 CLOSED, 1/5 gates (20%); G2–G5 NOT STARTED.**
  The G1 geometry adapters are intentionally fail-closed until G2, and
  pre-SFLE Scroll's multi-child behavior is replaced only in its
  normalization path (explicit single Flex root); G3 retains native Scroll
  migration ownership. No CSS, grid, or F2 numerical capability expansion.


## F3-G2 started — incremental evidence (2026-10-11)

- Source SHA [`a03f300`](https://github.com/Neuri-AI/PSX/commit/a03f30056ceadc9372049b84d8133ec5ec3ba9a3): [F3 selective #38158347861](https://github.com/Neuri-AI/PSX/actions/runs/38158347861) GREEN after the new canonical mapper and mounted Headless SFLE transaction tests were added to Core and Headless selection. **151 Core tests**, **19 Headless tests** passed.
- `tests/test_f3_g2_snapshot.py` checks source-vs-native dimension separation, keyed paths, explicit measurement, real Python SFLE compute and failing Scroll/unsupported roots. `tests/test_f3_g2_headless.py` checks actual mounted geometry, keyed identity/reorder, resize, hook updates, explicit native measurements, stale-result rejection, owner thread and legacy fail-closed behavior.
- The G2 gate is **not certified**: Qt, Kivy, Tkinter still lack the production SFLE bridge, and the complete registry/native custom matrix has not been fulfilled. Formal overall phase progress is **1/5**; do not conflate green impacted CI with G2 closure.


## F3-G2 native Qt iteration — 2026-10-11

- **Source SHA [`8e4d3b5`](https://github.com/Neuri-AI/PSX/commit/8e4d3b5919a7855ae73108393d8054a69bf6dc1b):** [F3 selected impact CI #38159181324](https://github.com/Neuri-AI/PSX/actions/runs/38159181324) completed GREEN and [G1 supported-Python matrix #38159181381](https://github.com/Neuri-AI/PSX/actions/runs/38159181381) completed GREEN on the same source SHA.
- **Qt job mandatory:** `.github/workflows/f3-selective.yml` runs `tests/test_pyside6_f3_g2_renderer.py` alongside existing PySide6 tests and the Qt SFLE worker/lifecycle test; **28 Qt native tests passed**. New assertions use actual `QWidget.geometry()`, no Qt `QLayout`, identity/event preservation, nested relative coordinates, and explicit negative cases.
- **Scoped claims:** Qt path is an *opt-in G2 subset* for Flex/Text/Button, not full registry certification. Kivy/Tkinter full SFLE path, wider Qt coverage and G2 registry/Native matrix are still open. The historical Headless status above described the state at that time and must not be read as today's overall G2 state. F3 remains **1/5 officially closed (20%)**.


## F3-G2 Kivy native geometry certification — 2026-10-11

- **Exact code SHA [`2eb0fad`](https://github.com/Neuri-AI/PSX/commit/2eb0fad8f1eea2ac975f146281c6a99e0b5a9d8b):** [F3 selective CI #38162867871](https://github.com/Neuri-AI/PSX/actions/runs/38162867871) GREEN with mandatory native Kivy, Qt, Tkinter regression, Headless, SFLE, Rust/Python and platform/wheel jobs as selected. [G1 3.10–3.13 #38162867872](https://github.com/Neuri-AI/PSX/actions/runs/38162867872) GREEN on the same SHA.
- **Mandatory Kivy invocation:** `xvfb-run -a python -m pytest -q tests/test_kivy_renderer.py tests/test_kivy_f3_g2_renderer.py` (3 collected tests passed). This includes an actual SDL2 `Window.add_widget`/Clock geometry check, nested top-left→bottom-left projection with parent-local heights, keyed reflow, stable events/hooks, viewport changes and negative capability cases. Do not count successful prior pure F2 projection tests as a substitute for real native integration.
- **Current supported G2 subset:** Headless, PySide6 Qt, Kivy. Production Kivy supports `Flex`, `Text`, `Button` in the opt-in SFLE path with explicit constraints; other supported components remain on the mandatory open coverage matrix, as do Tkinter and other Qt family parity. Native Scroll events and offset semantics remain G3. **G2 is not CLOSED**; official F3 progress remains **1/5 gates (20%)**.


## F3-G2 Tkinter native SFLE iteration — 2026-10-11

- [Exact source `85e1758`](https://github.com/Neuri-AI/PSX/commit/85e1758c8ba7feb771c8e753d526a25c8f7cdb3a): [F3 selective #38163393093](https://github.com/Neuri-AI/PSX/actions/runs/38163393093) **COMPLETED SUCCESS**, and [G1 Python 3.10–3.13 #38163393026](https://github.com/Neuri-AI/PSX/actions/runs/38163393026) **COMPLETED SUCCESS**, matching source SHA.
- The Tkinter native job now runs `xvfb-run -a python -m pytest -q tests/test_tkinter_renderer.py tests/test_tkinter_f3_g2_renderer.py` with **18 passed** (10 new native SFLE scenarios). Exact real-world assertions: Tk `ttk.Frame` / `ttk.Label` / `ttk.Button` geometry through `place_info`, no pack/grid fallback, CSS padding and nested parent masters, hook/state and keyed reconciliation, viewport size changes, native manager contention and invalid/stale/foreign-thread rejection.
- **No premature gate closure:** Qt/Kivy/Tkinter production SFLE currently only certifies `Flex`, `Text`, `Button` where opted in; full primitive/custom adapter and Qt binding coverage, remeasurement, automatic resizing, complete host geometry lifecycle remain open. F3 is still **1/5 gates (20%)** and G2 **IN PROGRESS**, despite four backend pathways existing.

## F3-G2 native leaf capability extension — verified 2026-10-11

- [Code SHA `8e9df15`](https://github.com/Neuri-AI/PSX/commit/8e9df157b681149c8a37018fcd6dd2419838063b) **GREEN**: [F3 selective #38164507647](https://github.com/Neuri-AI/PSX/actions/runs/38164507647) and [G1 3.10–3.13 regression #38164507621](https://github.com/Neuri-AI/PSX/actions/runs/38164507621), both concluded SUCCESS on the identical code SHA.
- **Counts by impacted native/contract job:** `F3 core and registry` **167 passed**; `F3 Qt native components` **30 passed**; `F3 Tkinter native components` **20 passed**; `F3 Kivy native components` **3 passed**. The Kivy G2 subprocess drives multiple real native SDL2 child-geometry, state, and capability scenarios within its test, so 3 is the pytest function count, not total semantic checks.
- **Policy regression:** `tests/test_f3_g2_native_coverage.py` is part of the Core mandatory invocation. It checks declared backend leaf allowlists, rejecting Scroll/custom/unsupported hosts, and Kivy fixed-pixel no-synthetic-intrinsic rules. Tk and Qt native suites require real widget geometry and event/state checks for newly admitted types; backend files not touched by the change still run according to PR-diff impact routing.
- **Still missing for G2 official gate:** custom/native ports, all existing component/backend cells, Qt binding parity, width-dependent remeasure, native automatic resize and device scaling. Do not count this expansion as a second F3 closed gate: F3 remains **1/5 (20%)** with G2 **IN PROGRESS**.
