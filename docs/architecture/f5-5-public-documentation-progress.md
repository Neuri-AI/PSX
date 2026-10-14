# F5.5 — Public Developer Documentation Progress and Handoff Ledger

**Status:** CONTRACT APPROVED / G1 NOT STARTED (2026-10-14).  
**Canonical target branch:** `develop`. **Documentation root:** `docs/public/`.  
**Normative contract:** [F5.5 Public Developer Documentation Contract](f5-5-public-documentation-contract.md).  
**Owner's decisions:** canonical English beginner-first Mintlify MDX; exhaustively grounded in `develop`; real reproducible tested examples; exhaustive current public API; future ecosystem integrations deferred; progress tracked under `docs/`.

## Gate scoreboard

| Gate | Deliverable | Status | Immutable implementation SHA / CI evidence |
| --- | --- | --- | --- |
| G1 | Develop API census / verified support matrix | NOT STARTED | — |
| G2 | Mintlify IA, docs.json and six template families | IN PROGRESS (PR #33) | pending pinned Mintlify validation CI |
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
