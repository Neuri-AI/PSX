# F5.5 — Public Developer Documentation Progress and Handoff Ledger

**Status:** CONTRACT APPROVED / G1 NOT STARTED (2026-10-14).  
**Canonical target branch:** `develop`. **Documentation root:** `docs/public/`.  
**Normative contract:** [F5.5 Public Developer Documentation Contract](f5-5-public-documentation-contract.md).  
**Owner's decisions:** canonical English beginner-first Mintlify MDX; exhaustively grounded in `develop`; real reproducible tested examples; exhaustive current public API; future ecosystem integrations deferred; progress tracked under `docs/`.

## Gate scoreboard

| Gate | Deliverable | Status | Immutable implementation SHA / CI evidence |
| --- | --- | --- | --- |
| G1 | Develop API census / verified support matrix | NOT STARTED | — |
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
