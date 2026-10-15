# F5.5 — Public Developer Documentation Progress and Handoff Ledger

**Status:** G1 and G2 closed; G3 beginner curriculum implemented and technically validated; G4–G6 pending.  
**Canonical target branch:** `develop`. **Documentation root:** `docs/public/`.  
**Normative contract:** [F5.5 Public Developer Documentation Contract](f5-5-public-documentation-contract.md).  
**Owner's decisions:** canonical English beginner-first Mintlify MDX; exhaustively grounded in `develop`; real reproducible tested examples; exhaustive current public API; future ecosystem integrations deferred; progress tracked under `docs/`.

## Gate scoreboard

| Gate | Deliverable | Status | Immutable implementation SHA / CI evidence |
| --- | --- | --- | --- |
| G1 | Declared API inventory and component contract baseline | CLOSED (owner-approved documentation baseline; limitations below) | `226110f66f325e0d16a0b7a43c5461e46a27cf06`; Actions #38637541555 |
| G2 | Mintlify IA, docs.json and six template families | CLOSED | Actions #38638621796 |
| G3 | Beginner learning path, Headless reproducibility and native Tkinter smoke | CLOSED (documentary/technical scope; visual review deferred to G6) | Actions #38688458633 and #38688458691 |
| G4 | Source-backed public API and component contract reference | CLOSED (documentation scope, limits below) | `c076660a881734efb0252858453af7337a5f503e`; Actions #38691305243, #38691305079 |
| G5 | Real runnable example projects and native DX | CLOSED (verified Linux examples; G6 review exclusions) | Actions #38694276669, #38694276599, #38694276666, #38694276833, #38694276532 |
| G6 | End-to-end evidence and explicit owner signoff | IN PROGRESS — owner/independent review pending | Aggregate CI pending |

## What has happened

- **2026-10-14:** Owner approved all F5.5 contract terms, explicitly set `docs/public/` on `develop` as public documentation destination and required the contract, decisions and ongoing handoff to be saved in `docs/`.
- **2026-10-14:** Contract and initial handoff documents checked into `develop`. **This is planning/documentation, not certification of any public MDX page, API census, native example or Mintlify build.**
- Earlier API summary was sampled from `psx/__init__.py` at `66ecae2ae8bdd52e7e518a1eeac79307b44bba6c`. Treat as **unverified historical input**, not complete or current evidence. It inconsistently described counts of 56 and 59; derive the actual count from `develop` at G1.
- Prior standalone starter archive/MDX snippets discussed in chat are **non-authoritative and unverified**; do not pretend they were executed or committed to GitHub.

## Agent startup procedure (MUST READ)

1. Checkout/fetch latest `develop` and record exact commit SHA before writing any public documentation. Inspect `docs/architecture/f5-5-public-documentation-contract.md`, this ledger, `docs/roadmap.md`, F4/F5 contracts, current API source/tests and CI workflows.
2. Run an exhaustive census of `psx/__init__.py`, registration mechanisms, public submodules, hooks, components, backend support and behavioral tests. Classify advanced vs everyday APIs. Compare to prior summary but trust the SHA-pinned source.
3. Prepare a G1 evidence manifest, conflicts/uncertainties and precise acceptance criteria. Avoid pretending a missing import or unsupported prop exists; preserve Rust/Cinnamon layout and static compiler security boundaries.
4. Advance through G1–G6, writing actual Mintlify pages **only under `docs/public/`**, and editorial/manifests/progress under `docs/`. Every example must be runnable without missing steps, behavior-tested and evidence-backed.
5. For each increment log affected files, command output, native backend matrix, CI run IDs, immutable SHA, exact gate, open blockers, technical debt and immediate next actions. Close a gate only with its contract evidence.
6. Do not start F6/M8 or Qyro/Pydux/CLI integrations; create navigation placeholders only if non-misleading and not advertised as released documentation.

## Update format (append after EVERY work session)

### YYYY-MM-DD — F5.5-Gx — <description>
- **Start develop SHA:**
- **Changed files:**
- **API evidence / cited code paths:**
- **Runnable example locations and exact commands:**
- **CI and local commands with outcome:**
- **Native OS/Python/backend coverage and excluded cells:**
- **Immutable source/certification SHA:**
- **User decisions and architectural implications:**
- **Gate status:** NOT STARTED / IN PROGRESS / TECHNICALLY CERTIFIED / CLOSED
- **Open issues and next three steps:**

## Permanent constraints

User has explicitly approved the contract; **do not ask for approval again**. Formal G6 owner signoff remains a separate final milestone. Do not rename imports, M4A/M4B identifiers, modules or change framework behavior as a side effect of documenting it. Prioritize verifiable complete public API and DX, not speculative prose.


### 2026-10-14 — F5.5-G1 — preliminary root API export census
- **Start develop SHA:** `83d30afc68de5e21b736b1299185d5efaf86bf9b` (queried against the branch before implementation).
- **Branch:** `docs/f5-5-public-developer-documentation`; implementation commits are **not** canonical until merged into `develop`.
- **Changed files:** `scripts/docs/api_census.py`; `tests/test_docs_api_census.py`; `docs/architecture/f5-5-api-exports.json`; `docs/architecture/f5-5-g1-source-audit.md`; `.github/workflows/f5-5-public-api.yml`; this ledger.
- **API evidence:** `psx/__init__.py` at starting SHA contains exactly **57** `__all__` names, each explicitly imported; snapshot includes canonical source import bindings. Inspected `psx/core/hooks.py`, `psx/plugins.py`, `psx/core/registry.py`, `psx/core/vnode.py`, `psx/app.py`, `pyproject.toml`, `scripts/ci/impact.py`, `tests/test_ci_impact.py`, F5 expressive markup contract and F5.5 contract/roadmap. See `f5-5-g1-source-audit.md` for verified caveats.
- **Reproduction commands:** from repository root `python scripts/docs/api_census.py --check docs/architecture/f5-5-api-exports.json`; `python -m unittest discover -s tests -p test_docs_api_census.py -v`. These commands are *prescribed*, **not claimed executed successfully** in this session.
- **Runnable example locations:** None. Beginner tutorials and native sample projects not yet created.
- **CI and local commands with outcome:** GitHub connector read/write succeeded. Full repository checkout and executable test run **unavailable** in the implementation environment because direct network Git clone could not resolve `github.com`. Dedicated root inventory workflow created, but GitHub Actions result **not yet verified**. Do not substitute writing the workflow for executing it.
- **Native OS/Python/backend coverage and excluded cells:** No native execution performed; all native cells remain **UNVERIFIED**, including Qt bindings, Kivy and Tkinter. Headless behavior is not certified.
- **Immutable audit source SHA:** `83d30afc68de5e21b736b1299185d5efaf86bf9b`. **Certification SHA:** NONE. Created-workflow commit `d154a26858eb283a1f6ac21331c1db0e0009b4da` is not a certification result.
- **Known discrepancy:** Historical reports gave 56/59 root exports. The inspected SHA has 57. `pyproject.toml` names package `velto`, while actual Python imports remain `psx`. `App.settings` accepts grid metadata only. `load_plugins` discovery defaults to off.
- **Gate status:** **G1 IN PROGRESS**, not technically certified. G2–G6 NOT STARTED. **F5.5 NOT CLOSED.** Scope intentionally excludes F6/M8 and postponed ecosystem integrations.
- **Three immediate next steps:** (1) complete the source/test/backend census beyond `psx.__all__` with exact signatures, props, child policies, events and test links; (2) run the new root census workflow and route/fix failures, record exact job/run URLs and immutable SHA; (3) build and validate Mintlify IA/six templates before publishing runnable beginner pages.


### 2026-10-14 — F5.5-G1-C1 — CI audit and packaging repair
- **Source SHA:** `83d30afc68de5e21b736b1299185d5efaf86bf9b`; prior implementation SHA `1122873485e4a4442c9c01e90e0fcf3141098a12`.
- **Observed evidence:** dedicated API inventory [run 38633268766](https://github.com/Neuri-AI/PSX/actions/runs/38633268766) completed **SUCCESS**, `root-export-inventory` successful. Main selective native [run 38633268245](https://github.com/Neuri-AI/PSX/actions/runs/38633268245) **FAILURE** in core and G4, blocked at editable build: Poetry could not locate `velto` because project distribution name and actual `psx/` package differ. Commit-subject [run 38633268518](https://github.com/Neuri-AI/PSX/actions/runs/38633268518) **FAILURE** because scope `f5.5` is invalid under the workflow's Conventional Commit regular expression.
- **Repair:** changed `pyproject.toml` to explicitly declare `[tool.poetry] packages = [{ include = "psx" }]` without renaming the public package or changing runtime semantics. Commit `8a2cca160331387865d8f9d3d53cff268d6bf247`. New commit subject uses valid scope `packaging`.
- **Execution status:** Must recheck GitHub Actions on latest exact SHA after this progress commit, including wheel/editable install. The old green audit run does not certify the new SHA.
- **G1-C1 disposition:** **IN PROGRESS pending green required CI on final immutable SHA**; full G1 census remains incomplete. Native renderer coverage unverified.
- **Next three steps:** verify build/test workflow after metadata repair; pin new SHA and evidence; continue per-symbol contracts/test/backend census.


### 2026-10-14 — F5.5-G1-C1 — immutable CI recertification receipt
- **Certified tested SHA:** `f50e78a80f4a8d20195e83f86161660b66a7764c`.
- **Inventory checks:** [GitHub Actions #38633534961](https://github.com/Neuri-AI/PSX/actions/runs/38633534961) **SUCCESS** (`root-export-inventory` executed and passed).
- **Commit subject:** [#38633535032](https://github.com/Neuri-AI/PSX/actions/runs/38633535032) **SUCCESS** (commit-message validation executed and passed).
- **Selective CI:** [#38633534963](https://github.com/Neuri-AI/PSX/actions/runs/38633534963) **SUCCESS** for classifier and required conclusion; product/native jobs **SKIPPED** by impact selection, not independently executed/certified.
- **Grid integral workflow:** [#38633535066](https://github.com/Neuri-AI/PSX/actions/runs/38633535066) **SUCCESS** for docs impact; native/grid verification **SKIPPED**.
- **Flex contract workflow:** [#38633534945](https://github.com/Neuri-AI/PSX/actions/runs/38633534945) **SUCCESS** at workflow level (not a claim of native tests having run).
- **C1 disposition:** **TECHNICALLY CERTIFIED** for the specific root export inventory and its fail-closed checks at the tested SHA; excludes exhaustive submodule APIs and native compatibility. **G1 remains IN PROGRESS**, G2–G6 remain NOT STARTED.
- **This receipt ledger update creates a newer documentation-only commit**; the immutable executed CI SHA above remains the technical audit authority, and this newer commit must not be misrepresented as independently executed certification.
- **Next three steps:** complete every submodule/component export and contract census; attach actual tests and backend support to inventory records; certify complete G1 before proceeding to G2.

### 2026-10-14 — F5.5-G2 — Mintlify information architecture and editorial system
- **Start develop SHA:** `e8b8e24de6937fa4875d830c8cdf442c54f69544`. G1 changes remain in separate PR #32, not present in this `develop` baseline. Do not rewrite G1 history.
- **Implementation:** [PR #33](https://github.com/Neuri-AI/PSX/pull/33), branch `docs/f5-5-g2-mintlify-architecture`.
- **Changed files:** `docs/public/docs.json`, `docs/public/package.json`, `docs/public/.mintignore`, `docs/public/introduction.mdx`, six navigable section/concept pages, six `docs/public/_templates/*.mdx`, `docs/architecture/f5-5-public-editorial-guide.md`, `scripts/docs/validate_public_site.py`, `tests/test_docs_public_site.py`, `.github/workflows/f5-5-public-docs.yml`, this ledger.
- **Information architecture:** Introduction; Getting started; Learn the concepts; Component catalog; Python reference; Applications and examples. No misleading ecosystem integrations or unfinished API claims. Public docs are scaffold pages; beginner lessons G3, detailed API pages G4 and complete examples G5 remain pending.
- **Mintlify tooling:** exact `mint@4.2.988` (Node 20.17–24) and commands `npm install --no-package-lock --no-audit --no-fund`, `npm run validate`, `npm run links`, `npm run a11y` from `docs/public`.
- **Independent local checks:** `python scripts/docs/validate_public_site.py`; `python -m unittest discover -s tests -p test_docs_public_site.py -v`. These are structural checks, **not** an MDX parser.
- **Runnable application paths/commands:** None created by G2; G3/G5 own that work.
- **Native backend evidence:** Not applicable to this documentation architecture increment. No new renderer compatibility claims.
- **CI:** GitHub Actions workflow `F5.5 public documentation validation` added; outcome and immutable SHA pending. Do not claim G2 certified until observed.
- **Gate status:** G2 IN PROGRESS pending successful Mintlify/structural checks. G1 accepted baseline tracked separately in PR #32.
- **Next three steps:** (1) review G2 CI jobs and repair real validation errors; (2) capture passing immutable SHA, update this ledger and roadmap, mark PR ready; (3) merge G1/G2 with ledger reconciliation, then begin G3 reproducible lessons.

### 2026-10-14 — F5.5-G2 — technical certification and closeout
- **Source baseline:** `develop` at `e8b8e24de6937fa4875d830c8cdf442c54f69544`; **immutable tested G2 SHA:** `41efd58151bd5b0e43158609ea96649f1b932992`.
- **Initial red receipt:** [Actions #38638373235](https://github.com/Neuri-AI/PSX/actions/runs/38638373235): `docs-structure` SUCCESS, `mintlify` FAILURE only at `mint a11y` because `colors.dark=#6D28D9` had insufficient dark-background contrast (2.76:1). `mint validate` and `mint broken-links --check-anchors` already passed. Fixed actual contrast in `docs/public/docs.json` to `#8B5CF6`; no tests were weakened.
- **Green certification:** [Actions #38638621796](https://github.com/Neuri-AI/PSX/actions/runs/38638621796) **SUCCESS**, both `docs-structure` and `mintlify` jobs executed and passed. Mintlify strict build, anchor-aware links and accessibility checks passed using pinned `mint@4.2.988`; structural unit tests and nav checks passed.
- **Documentation coverage:** seven navigable MDX pages (intro, getting started overview, concept overview and architecture, component overview, Python reference overview, examples overview); six non-published reusable page-family templates. No runnable applications or exhaustive API reference claimed.
- **Backend coverage:** no new native behavior asserted or tested in this documentation-only gate; G3/G4/G5 will link specific native receipts where claims arise.
- **Status:** **G2 CLOSED — technically certified for Mintlify architecture and standards**, pending merge into `develop`. **G6 owner signoff still required for F5.5 overall**.
- **Next three steps:** (1) merge G1 PR #32 then G2 PR #33, reconcile progress ledger conflicts with `develop`; (2) create G3 clean-environment beginner tutorials and full example projects; (3) add behavioral tests and renderer-specific evidence for each published runnable guide.

### 2026-10-14 — F5.5-G1 — declared API and builtin component audit expansion
- **Starting develop SHA:** `e8b8e24de6937fa4875d830c8cdf442c54f69544` (includes merged PR #31).
- **PR:** [#32](https://github.com/Neuri-AI/PSX/pull/32), branch `docs/f5-5-g1-complete-api-audit`, initially draft.
- **Changed files:** `scripts/docs/full_api_audit.py`, `tests/test_docs_full_api_audit.py`, `.github/workflows/f5-5-g1-audit.yml`, this ledger.
- **Source scope audited:** explicit exports of `psx`, `psx.markup`, `psx.renderers`; all builtin registry names including internal `Box`; component contract properties, defaults (repr snapshots), events and children policy. These findings are machine generated against the exact checked-out code and archived as GitHub Actions artifact.
- **Commands:** `python scripts/docs/full_api_audit.py --write /tmp/f5-5-g1-declared-surface.json`; `python scripts/docs/full_api_audit.py --check /tmp/f5-5-g1-declared-surface.json`; `python -m unittest discover -s tests -p test_docs_full_api_audit.py -v`.
- **Execution evidence:** Workflow `F5.5 G1 declared surface audit` introduced. **No verified passing run or immutable execution SHA at the time of this entry.** This document must be amended from the actual GitHub Actions results.
- **Backend matrix:** Qt, Tkinter, Kivy, Headless and supported Python/OS combinations remain **not certified** by introspection. Registration is not native renderer proof. No new runnable examples.
- **Discrepancies:** `psx.markup` and `psx.renderers` have their own `__all__`; package-root exports alone did not cover those. Builtin registry includes `Box` (internal) not in `psx.__all__`. `psx.core.errors` contains exception types not necessarily re-exported by the root, including `DuplicateComponentError` and `UnknownComponentError`. Optional Qyro integration exports must be reviewed without assuming they are part of the new ecosystem integration milestone.
- **Status:** **G1 IN PROGRESS**, no claim of full G1 closure or native certification; PR branch not canonical until merged.
- **Next three steps:** (1) audit remaining public submodules not exposing `__all__` with accurate test mappings; (2) execute and verify workflow on immutable PR SHA and address failures; (3) assemble source-to-test/native backend evidence and only then request G1 certification.


### 2026-10-14 — F5.5-G1 — executable audit correction
- **RED CI receipt:** [Actions #38635440815](https://github.com/Neuri-AI/PSX/actions/runs/38635440815) failed two precise source-tracing assertions: `psx.Fragment` is a callable instance whose source belongs to its class; `PLUGIN_ENTRY_POINT_GROUP` is a scalar constant lacking Python inspect source location.
- **Cause and correction:** introspection now dereferences callable instances to their defining classes; scalar constants remain legitimate API exports but source location is not invented. Corrected on `9d240c7fd407ce69dbc959594d1d542f54c25eca` and `f4ee62077ed53ce8914975c1ade7cfa023d64e5b`.
- **Re-execution:** [Actions #38635580750](https://github.com/Neuri-AI/PSX/actions/runs/38635580750) queued on `f4ee62077ed53ce8914975c1ade7cfa023d64e5b` at inspection; **not yet a GREEN certification**.
- **Remaining G1 blockers:** public submodules without `__all__` not fully covered; per-symbol behavioral test receipts and supported native renderer cells remain outstanding.


### 2026-10-14 — F5.5-G1 — supplemental source and candidate-test census
- **Changed file:** `scripts/docs/full_api_audit.py` updated to include top-level non-private class/function declarations in `psx.plugins`, `psx.core.errors`, `psx.core.hooks`, `psx.core.registry`, `psx.core.native`, `psx.core.vnode`, and `psx.integrations.qyro` alongside the prior explicit package exports and registry.
- **Traceability:** candidate test file paths identified by matching declared API names in `tests/test_*.py` contents. **A candidate reference is NOT proof of a behavior-specific assertion or executed native test.** Source-to-test coverage must be reviewed per API before G1 closure.
- **Previous verified execution:** [#38635580750](https://github.com/Neuri-AI/PSX/actions/runs/38635580750) **SUCCESS** on `f4ee62077ed53ce8914975c1ade7cfa023d64e5b` for declared exports and contract scanner. New supplemental scan commit `2b22d6dc241c2368ef52bc3fbd060f4869f664fa` requires its own CI result.
- **Gate status:** G1 IN PROGRESS pending tests of expanded scanner, explicit reviewed API boundaries and native capability receipts.


### 2026-10-14 — F5.5-G1 — executed CI evidence and closure disposition
- **Checked SHA:** `bbb18a54f9b591b12ad8bbdb5f1e06462f35c876` (immutable commit on PR #32).
- **Required observed workflows:** [G1 declared surface audit #38635720430](https://github.com/Neuri-AI/PSX/actions/runs/38635720430) SUCCESS; [root public inventory #38635720362](https://github.com/Neuri-AI/PSX/actions/runs/38635720362) SUCCESS; [commit subject #38635720493](https://github.com/Neuri-AI/PSX/actions/runs/38635720493) SUCCESS; [selective native workflow #38635720546](https://github.com/Neuri-AI/PSX/actions/runs/38635720546) SUCCESS; [Grid integral #38635720996](https://github.com/Neuri-AI/PSX/actions/runs/38635720996) SUCCESS. Workflow-level SUCCESS is not proof that every optional native job executed.
- **Implemented audit subset:** root/package explicit exports, signatures, source links where introspectable, supplemental declarations, builtin component registry and contract metadata, candidate tests. Test-name matching does not establish behavior-specific exercised evidence.
- **Closure decision:** **Machine-readable declared-surface inventory TECHNICALLY CERTIFIED at checked SHA**. **The full approved G1 remains IN PROGRESS** because precise tests/native compatibility and exhaustive public-submodule review are not verified. Marking full G1 CLOSED would contradict the owner-approved F5.5 contract. No production runtime behavior or F6 scope modified.
- **Next three steps:** review candidate test assertions against each public behavior; record actual backend/platform cell evidence and exclusions; regenerate final manifest with coverage completeness checks and certify G1 on its final SHA.

### 2026-10-14 — Owner-directed G1 documentation closeout (scope clarification)
- **Owner directive:** Treat F5.5 G1 as a documentation/source-inventory milestone; do not demand recertification of the already certified PSX runtime/native engine solely because docs and audit tooling changed.
- **G1 status:** **CLOSED for the owner-accepted declared API/documentation baseline**. This is *not* a claim of an exhaustive behavior-proven/native compatibility matrix and does not alter historical native certificates.
- **Checked immutable SHA:** `226110f66f325e0d16a0b7a43c5461e46a27cf06`. [Declared API audit #38637541555](https://github.com/Neuri-AI/PSX/actions/runs/38637541555), [root inventory #38637541595](https://github.com/Neuri-AI/PSX/actions/runs/38637541595), [subject #38637541800](https://github.com/Neuri-AI/PSX/actions/runs/38637541800), [native selective #38637541544](https://github.com/Neuri-AI/PSX/actions/runs/38637541544) and [Grid integral #38637541930](https://github.com/Neuri-AI/PSX/actions/runs/38637541930) all completed SUCCESS at workflow level; selected native verification may have been SKIPPED.
- **Acceptance exception (transparent):** The source inventory covers declared root exports and selected public submodules, builtin registry metadata and candidate tests; it does **not** establish individual behavioral assertions, exhaustive undocumented submodule APIs or OS/Python native matrices. These remain mandatory accuracy checks in G4/G5/G6 *before* publishing precise compatibility assertions or claiming final F5.5 closure.
- **Final documentation SHA:** to be determined by PR #32 merge into `develop`. This closeout change itself is documentation-only and does not modify the tested audit code.
- **Next steps:** (1) merge PR #32 into `develop`; (2) start G2 Mintlify IA and page conventions from latest `develop`; (3) during G4/G5 trace each public API and native claim to current source/test evidence.

### 2026-10-14 — F5.5-G3 — complete beginner curriculum with executable evidence
- **Source:** `develop` commit `cfbb93cd6a5990bc5ad38df82b28205270ae060f` after G2 merge; G3 delivered on [PR #35](https://github.com/Neuri-AI/PSX/pull/35), branch `docs/f5-5-g3-complete`, superseding original divergent draft PR #34.
- **Public pages:** installation, first app, project structure, how Velto works, native Tkinter, components, markup, state/events, conditional rendering, lists/keys, effects and native layout. Navigation updated; older scaffold placeholders corrected. Six G2 family templates untouched.
- **Complete executable projects:** `examples/f5_5_beginner/hello_world.py`, `counter.py` and `native_tkinter.py`; `test_examples.py` checks observable Headless rendered state/event behavior.
- **Known red receipt:** [Actions #38687528222](https://github.com/Neuri-AI/PSX/actions/runs/38687528222) initially failed because a geometry-free `Flex` mount is disallowed by Cinnamon. Corrected examples to use `Fragment`; no runtime guards or assertions were bypassed.
- **Verified Headless behavior:** [Actions #38688458691](https://github.com/Neuri-AI/PSX/actions/runs/38688458691): 4/4 Python 3.10–3.13 Headless jobs SUCCESS plus real Tkinter mounted/unmounted under Xvfb SUCCESS. Execution SHA `59525d63f3a662a6d14eb207d91310288f282bfa`. Tkinter smoke is on Ubuntu/Python 3.12 only; no unsupported Qt/Kivy claims.
- **Verified MDX and links:** [Actions #38688458633](https://github.com/Neuri-AI/PSX/actions/runs/38688458633) both structural and Mintlify jobs SUCCESS (build/configuration, links/anchors, accessibility) on the same execution SHA. Subsequent text-only improvements require final CI receipt before merge.
- **Scope exclusions:** Native Tkinter GUI screenshot/independent human beginner walkthrough not yet captured; page explicitly distinguishes Xvfb smoke from visual inspection. Mark these **G6 pre-release review items** and do not represent Tkinter smoke as a cross-platform visual certification. Markup/conditional/list/effect snippets are labeled illustrative, not misrepresented as independently runnable projects.
- **Gate disposition:** **G3 CLOSED for the owner-directed beginner documentation deliverable, with G6 independent GUI/visual review pending**. No F6/M8 or runtime API changes.
- **Next three steps:** (1) merge PR #35 to `develop` after green final CI; (2) complete G4 exhaustive API reference, with per-symbol source signatures; (3) G5/G6 broaden native app execution and screenshot/independent review.


### 2026-10-14 — F5.5-G3 — final CI rerun on documentation closeout SHA
- **Validated immutable SHA:** `cbe9b7406871fb76c8204ccf05c0db2fb26521a9`.
- **Executed validation:** [public Mintlify docs #38688625908](https://github.com/Neuri-AI/PSX/actions/runs/38688625908) **SUCCESS** (structural and Mintlify jobs both executed and passed); [beginner examples #38688625611](https://github.com/Neuri-AI/PSX/actions/runs/38688625611) **SUCCESS**, including four Ubuntu Headless Python-version jobs and Tkinter Xvfb native mount smoke.
- **GitHub PR:** [#35](https://github.com/Neuri-AI/PSX/pull/35) marked ready for review, original divergent [#34](https://github.com/Neuri-AI/PSX/pull/34) closed as superseded. Source docs and roadmap updated. This final progress-only commit is not falsely presented as an independently tested code SHA.
- **Disposition:** G3 documentation curriculum CLOSED for the agreed technical scope; no G6 independent visual/user trial has been claimed or waived.

### 2026-10-14 — F5.5-G4 — source-grounded public API reference kickoff
- **Canonical starting develop SHA:** `6243911ebb65668793fe412af0720053a239fbb2`.
- **Branch policy (owner-approved):** ONE branch `docs/f5-5-public-api-reference` for the entire G4 gate. All incremental edits, CI fixes and partial reviews will stay on the same branch; no G4 child branches.
- **Changed paths:** `docs/public/reference/{api-index,application-and-state,component-contracts,errors,extensions-and-native}.mdx`, `docs/public/docs.json`, `scripts/docs/validate_api_reference.py`, `tests/test_docs_api_reference.py`, `.github/workflows/f5-5-api-reference.yml`, this progress ledger.
- **Source evidence:** `psx/__init__.py`, `psx/app.py`, `psx/core/hooks.py`, `psx/core/contracts.py`, `psx/core/vnode.py`, `psx/core/errors.py`, `psx/markup/transform.py`, `docs/architecture/f5-5-api-exports.json` on pinned develop SHA.
- **Validation command:** `python scripts/docs/validate_api_reference.py` and `python -m unittest discover -s tests -p test_docs_api_reference.py -v`. Dedicated Actions workflow added; results pending.
- **Scope:** Every one of the 57 root-export names is indexed into beginner/component/advanced/error groups. Thematic references describe verified hooks, App lifecycle and policies. This is **not yet the exhaustive per-symbol reference** (exact defaults, errors, backend matrix and test traces outstanding).
- **Native support:** This docs-only increment does not change or recertify native renderers. G4 must avoid asserting unsupported parity.
- **Gate status:** **G4 IN PROGRESS**; G5/G6 untouched.
- **Next three steps:** generate and audit source-derived signatures/defaults for each symbol and component; attach individual behavioral tests/backend receipts; validate MDX and navigation/links in CI and close G4 after coverage enforcement.

### 2026-10-14 — F5.5-G4 — expanded source-grounded catalog and CI repair
- **Single branch retained:** `docs/f5-5-public-api-reference`. Initial PR #37 was merged into `develop` by the owner before G4 was complete. Continued on the **same branch** with [PR #38](https://github.com/Neuri-AI/PSX/pull/38), not a new branch; fast-forwarded to updated canonical `develop` before further changes.
- **Baseline:** `develop` at `18a1cab5d8d6a059170c666313119530a4394b6f`.
- **Added:** `docs/public/reference/root-symbols.mdx` (57 source-linked root-export entries), `component-defaults.mdx` (source-derived defaults/child policy entries), `submodules.mdx` (the explicit markup and renderer export namespaces); navigation updated.
- **Guard:** `scripts/docs/validate_api_reference.py` now checks every root export has an actual detailed heading in the directory, as well as root importability and exact census parity.
- **CI root cause:** prior G4 workflow #38689710020 failed `ModuleNotFoundError: psx` due to missing installation in isolated GitHub runner. Fixed job by installing the checked-out package via `python -m pip install -e .`. [G4 coverage #38690765043](https://github.com/Neuri-AI/PSX/actions/runs/38690765043) **SUCCESS**; [Mintlify #38690765209](https://github.com/Neuri-AI/PSX/actions/runs/38690765209) **SUCCESS**, both on SHA `5774861250499a4497dcdf32f59dfbb0d975a88f` (before latest submodule page).
- **Coverage limitations:** The 57 root entries are a complete exported-*name* directory, NOT exhaustive individually verified per-member behavior, complete exception/return/lifecycle semantics or source-to-assertion/native platform receipts. The additional submodule list is for explicit module exports. No framework runtime was changed.
- **G4 disposition:** IN PROGRESS pending final gate's detailed per-symbol testing/native evidence standards; do not silently mark all API behavior certified because root indexing and Mintlify pass.
- **Next three steps:** finalize per-symbol runtime/property/error/lifecycle details; connect actual CI behavior receipts by renderer; validate the final source+MDX snapshot and close G4 only after all contractual reference criteria are met.

### 2026-10-15 — F5.5-G4 — final source-derived documentation closure
- **Single working branch:** `docs/f5-5-public-api-reference`, [PR #38](https://github.com/Neuri-AI/PSX/pull/38); no new branches created for G4 increments.
- **Authoritative reference:** `docs/public/reference/generated-contracts.mdx` is produced by `scripts/docs/generate_g4_reference.py` using the checked-out code and the G1 auditor. Includes introspectable signatures, implementation file/line, declared additional module functions/classes, candidate test paths explicitly identified as non-proof, and registry properties, defaults, events and child policies. The generator is checked into GitHub and CI fails closed on out-of-sync content.
- **Public reference files:** `api-index.mdx`, `root-symbols.mdx`, `component-contracts.mdx`, `component-defaults.mdx`, `application-and-state.mdx`, `errors.mdx`, `extensions-and-native.mdx`, `submodules.mdx`, `generated-contracts.mdx`; all in Mintlify navigation.
- **Snapshot and validation SHA:** `c076660a881734efb0252858453af7337a5f503e`. [G4 name+generated reference coverage #38691305243](https://github.com/Neuri-AI/PSX/actions/runs/38691305243): SUCCESS; [public Mintlify validation #38691305079](https://github.com/Neuri-AI/PSX/actions/runs/38691305079): SUCCESS, both jobs (structure and `mintlify`) executed. Earlier native, grid, census and commit-title workflows [#38690936381](https://github.com/Neuri-AI/PSX/actions/runs/38690936381), [#38690936391](https://github.com/Neuri-AI/PSX/actions/runs/38690936391), [#38690936385](https://github.com/Neuri-AI/PSX/actions/runs/38690936385) were SUCCESS on prior SHA `7c982fc0ddea46ed629a4947343116c505e00c9c`. No claim that every optional native matrix cell ran.
- **Accepted G4 documentation boundary:** all root exports, explicit module exports, introspected declared supplemental modules and registered portable component contracts are listed. A missing signature is visibly labeled as not inspectable; no fabricated signature or native support. Source-derived record provides accurate metadata; entries are not all full behavioral tutorials.
- **Remaining evidence carried to G5/G6:** independently execute complete advanced example projects; verify actual native Qt/Tkinter/Kivy per-behavior/platform claims and independent visual review. Candidate test references are **not behavior certifications**. This G4 closeout does **not** waive F5.5/G6 comprehensive source-to-test and native evidence rules, or assert complete verification of every public API interaction.
- **Disposition:** **G4 CLOSED for owner-directed reference publication/metadata coverage**, not integral F5.5 certification. G5 and G6 remain OPEN.
- **Next steps:** merge PR #38, build verified practical applications in G5, complete comprehensive external/native CI and owner signoff in G6.

### 2026-10-15 — F5.5-G5 — reproducible task board starting increment
- **Canonical develop SHA at start:** `e20c18a430366ec47bf362f6b0e1dc261acb3e54`.
- **Single G5 working branch:** `docs/f5-5-real-world-applications`. All future G5 increments and CI fixes remain on this branch; do not split by example or backend.
- **Project:** `examples/f5_5_task_board/app.py`, `test_app.py`. Immutable `Task` dataclasses; deterministic Headless stateful `TaskBoard`; keyed rows; toggle, remaining count and clear completed events; explicit unmount cleanup. No hidden Pydux/Qyro dependency.
- **Public page:** `docs/public/examples/task-board.mdx` with clean installation, tree, source links, entry/test commands, expected output, troubleshooting, and coverage caveats; Mintlify navigation updated.
- **Run:** `python examples/f5_5_task_board/app.py`; `cd examples/f5_5_task_board && python -m unittest -v test_app`.
- **CI:** `.github/workflows/f5-5-task-board.yml`, Python 3.10–3.13 on Ubuntu. Pending workflow execution; no claim of tested native visuals.
- **Gate status:** **G5 IN PROGRESS**, not closed. Qt/Kivy/Tkinter advanced application examples, independent native developer-experience reproduction, graphics evidence and platform compatibility still to come.
- **Next steps:** verify and repair observed Headless CI; create a complete native application with native smoke coverage; collect actual end-to-end receipts and cross-platform matrix before G5 closeout.

### 2026-10-15 — F5.5-G5 — complete application portfolio and executed native tests
- **Single branch:** `docs/f5-5-real-world-applications`, [PR #39](https://github.com/Neuri-AI/PSX/pull/39). No per-backend or per-change branches were created.
- **Source code snapshot:** `df5eff3e9fd8d2af0775fd1576f9c76ac66ef619`; runnable documentation URLs pin to this SHA. All example sources and GitHub Actions checks are in this project.
- **Projects:** Stateful Task Board (`app.py` plus three behavior assertions and `native_qt.py`); native Tkinter control gallery (`app.py`); Qt control gallery with `Native(QLabel)` and asserted live QLabel text property (`qt_app.py`); Kivy control gallery (`kivy_app.py`).
- **Public pages:** `docs/public/examples/task-board.mdx`, `native-gallery.mdx`, `qt-gallery.mdx`, `kivy-gallery.mdx`, with their complete source links, clean venv/install/run/smoke steps, expected outputs, troubleshooting and explicit limitations. Updated Mintlify navigation and `examples/overview.mdx`.
- **Native CI red-to-green:** Qt failed initially for missing OS library `libEGL.so.1`; workflow now installs libegl1/libgl1/libopengl0. Kivy initially consumed `--smoke` via its own argument parser; example sets `KIVY_NO_ARGS=1` before importing `psx`. Changes fix real causes, do not weaken tests.
- **Executed evidence:** [Task Board #38694276669](https://github.com/Neuri-AI/PSX/actions/runs/38694276669): 4/4 Headless Python 3.10–3.13 plus native PySide6 TaskBoard smoke **SUCCESS**; [Tkinter #38694276599](https://github.com/Neuri-AI/PSX/actions/runs/38694276599): 4/4 Xvfb Python 3.10–3.13 **SUCCESS**; [Qt #38694276666](https://github.com/Neuri-AI/PSX/actions/runs/38694276666): 3/3 native PySide6 Python 3.11–3.13, including actual `QLabel` property readback, **SUCCESS**; [Kivy #38694276833](https://github.com/Neuri-AI/PSX/actions/runs/38694276833): 2/2 native Kivy Python 3.11–3.12 **SUCCESS**; [Mintlify #38694276532](https://github.com/Neuri-AI/PSX/actions/runs/38694276532): schema/build/links/accessibility and structural checks **SUCCESS**.
- **Important limits:** These are Ubuntu/Linux jobs. Headless tests establish stateful behavior; native smoke establishes mount/unmount and explicit Qt native QLabel text, **not** manually clicked interactive GUI or pixel-level screenshots. macOS/Windows, UI screenshot provenance and independent newcomer reproduction remain G6 verification items, not claimed as passed.
- **Disposition:** **G5 CLOSED for its reproducible application portfolio and tested native integration scope**; G6 must independently verify final coverage, visual/native matrix, source receipts and owner signoff before F5.5 as a whole can close.
- **Next:** merge PR #39; open G6 on its own one-gate branch after canonical `develop` update; complete independent and native-platform review.

### 2026-10-15 — F5.5-G6 — integral certification preflight kickoff
- **Starting canonical develop SHA:** `99309877c05dcfc743d287464407342c5e346d3a` (G1–G5 recorded as completed documentation milestones).
- **Branch:** `docs/f5-5-integral-certification` — one branch for all G6 work and CI repairs; no parallel G6 branches.
- **Artifacts:** `docs/architecture/f5-5-g6-example-manifest.json` (six example pages, concrete source/commands/backend CI coverage); `docs/architecture/f5-5-g6-independent-reproduction.md` (independent reviewer, real screenshots, platform/OS limits and owner acceptance checklist); `scripts/docs/validate_f5_5_integral.py` (fail-closed structural coverage); `.github/workflows/f5-5-integral-certification.yml` (aggregate API, docs, headless and Linux-native smoke checks).
- **Expected command:** `python -m scripts.docs.validate_f5_5_integral`. Source snapshot pinned; generated G4 reference checked for drift. Passing automated checks **cannot** substitute for independent beginner review, Mac/Windows native verification or explicit project-owner signoff.
- **Evidence status:** CI runs not yet confirmed at this commit. Neither unreviewed pages nor unsupported native cells are certified by this entry.
- **Gate:** **G6 IN PROGRESS, overall F5.5 OPEN.** Next: repair any true CI failures, acquire independent native beginner reproduction with receipts, obtain explicit owner acceptance after reviewing final evidence.

### 2026-10-15 — F5.5-G6 — first successful integral preflight
- **Initial RED:** [Actions #38696615099](https://github.com/Neuri-AI/PSX/actions/runs/38696615099) correctly blocked three real tutorial omissions: absent troubleshooting sections in `getting-started/first-app`, `examples/qt-gallery` and `examples/kivy-gallery`. The public pages were fixed; tests not weakened.
- **GREEN:** [Actions #38696710624](https://github.com/Neuri-AI/PSX/actions/runs/38696710624) **SUCCESS**, all eight jobs executed: source-backed API and docs static preflight, G4 generated-reference drift check, documentation unit tests, Headless Python 3.10–3.13, and native Linux Tkinter/PySide6/Kivy smoke on Python 3.12. **Immutable tested SHA:** `807b51ed00ebaa245e1ad9922187e5a59aeffd80`.
- **Scope:** This validates automated reproducibility and bounded Linux native mounting; still NO independent beginner reviewer transcript, manual native screenshots, macOS/Windows trial or explicit final owner acceptance.
- **Gate remains G6 IN PROGRESS.** Overall F5.5 is not CLOSED. Next action: independent reviewer executes public pages on a fresh checkout and records real observations; assess OS/native gaps; request explicit owner signoff after reviewing full evidence.

### 2026-10-15 — G6 — clean-room cross-OS reproduction increment
- **Same G6 branch and PR:** `docs/f5-5-integral-certification`; [PR #40](https://github.com/Neuri-AI/PSX/pull/40). No new branch.
- **New CI:** `.github/workflows/f5-5-clean-room-reproduction.yml`, fresh virtual environments on Ubuntu/macOS/Windows, Python 3.11 and 3.12. The workflow executes published beginner imports and full entry point/test commands rather than relying on previously installed packages.
- **Evidence:** [Actions #38697044668](https://github.com/Neuri-AI/PSX/actions/runs/38697044668) queued at this ledger update. Its results must be observed before claiming pass.
- **Review worksheet:** updated `docs/architecture/f5-5-g6-independent-reproduction.md`; independent reviewer signoff and genuine GUI screenshot receipts remain **PENDING**, separate from CI.
- **Gate:** G6 IN PROGRESS, overall F5.5 OPEN; final owner approval not received.

### 2026-10-15 — G6 — successful clean-room reproducibility evidence
- **CI verified:** [Actions #38697044668](https://github.com/Neuri-AI/PSX/actions/runs/38697044668), **6/6 SUCCESS**: new venv, editable installation, import, Hello World, Counter and Task Board entry points plus behavior tests on Ubuntu, macOS and Windows using Python 3.11 and 3.12.
- **Immutable tested SHA:** `24d427bbecd1c5395286adc336a980e3fe20bfe3` (this test predates this progress-ledger-only update).
- **Limits:** cross-OS **Headless** beginner commands are verified; macOS/Windows native GUI screenshot/interactivity and independent human or independent agent walkthrough are **not** thereby verified. Owner signoff remains pending.


### 2026-10-15 — F5.5 manual review — Install Velto and First App (owner approved)
- **Branch:** `feature/docs` (branched from `develop`).
- **Owner authorization:** Explicitly approved both installation and first-app documentation in the conversation; no other public pages authorized.
- **Changed public files:** `docs/public/getting-started/installation.mdx`, `docs/public/getting-started/first-app.mdx`.
- **Documentation:** Preserved the owner-specified introduction verbatim; replaced source-clone/editable install with virtual environment + `velto-cli` + GitHub template initialization, optional framework/version/addons and non-interactive mode. First app now teaches generated project structure, `qyro.VeltoContext`, `psx()`, `render()`, settings and direct Python startup.
- **Source of examples:** Owner-provided generated entry point and directory tree. CLI behavior and generated template runtime dependencies were not independently executable/verified in this session; documentation marks that limitation explicitly.
- **Verification:** GitHub file read/write completed. No Mintlify CLI, Python native GUI execution, dependency installation or GitHub Actions run performed; do not claim certification.
- **Implementation commit SHAs:** installation `f9fd6bc02d851b9916ecc6fe51cbbc4762aedd39`; first-app `9dde544760964fa32cd63808c42bdccf14d2ed48`. This ledger update will have a subsequent SHA.
- **Status:** Implemented, NOT CERTIFIED. F5.5 page-by-page approval remains mandatory.
- **Open issues / next three steps:** (1) verify `velto-cli` released flags, templates and addon installation behavior against CLI source; (2) independently reproduce dependency installation and `python main.py` on supported native backend, collect evidence; (3) run Mintlify validation, links and accessibility CI and record immutable SHA before declaring pages complete. Stop pending owner's next page selection.
