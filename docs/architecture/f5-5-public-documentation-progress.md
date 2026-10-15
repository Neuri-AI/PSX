# F5.5 — Public Developer Documentation Progress and Handoff Ledger

**Status:** G1 DOCUMENTATION BASELINE ACCEPTED BY OWNER (2026-10-14); G2–G6 pending.  
**Canonical target branch:** `develop`. **Documentation root:** `docs/public/`.  
**Normative contract:** [F5.5 Public Developer Documentation Contract](f5-5-public-documentation-contract.md).  
**Owner's decisions:** canonical English beginner-first Mintlify MDX; exhaustively grounded in `develop`; real reproducible tested examples; exhaustive current public API; future ecosystem integrations deferred; progress tracked under `docs/`.

## Gate scoreboard

| Gate | Deliverable | Status | Immutable implementation SHA / CI evidence |
| --- | --- | --- | --- |
| G1 | Declared API inventory and component contract baseline | CLOSED (owner-approved documentation baseline; limitations below) | `226110f66f325e0d16a0b7a43c5461e46a27cf06`; Actions #38637541555 |
| G2 | Mintlify IA, docs.json and six template families | NOT STARTED | — |
| G3 | Complete independent beginner-first tutorials | NOT STARTED | — |
| G4 | Exhaustive verified API and component reference | NOT STARTED | — |
| G5 | Real runnable example projects and native DX | NOT STARTED | — |
| G6 | End-to-end evidence and explicit owner signoff | NOT STARTED | — |

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
