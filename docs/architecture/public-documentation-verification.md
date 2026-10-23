# Public developer documentation verification

**Audit date:** 2026-10-23  
**Tracking:** P4.4 — public educational documentation  
**Repo/branch:** PSX `feature/cross-platform-certification`  
**Public source root:** `docs/public/`

## Goal and exit boundary

Update the developer learning path in PSX to reflect the **current merged Velto 0.1.0 ecosystem** and tested architecture: Qyro Engine owns application lifecycle, PSX Markup owns UI descriptions, Cinnamon is an internal PSX layout engine, Pydux owns state, and Velto CLI owns project/build workflows. The public facade directly re-exports the original APIs. No runtime changes and no public-behavior census (N/A).

The editorial increment is distinct from the **entire project's release publication gate**: manuals, external beginner reproduction on every system, proprietary signing, and complete frozen OS/backend coverage remain release validation work, not inferred from published-looking prose.

## Primary page review ledger

Every listed page was rewritten or added from inspected public exports, Qyro/CLI command definitions, the approved PSX architecture, the owner-specified syntax conventions and immutable CI receipts. The `docs/public/docs.json` navigation was reorganized without dead-page placeholders.

| Page family | Files | Grounded scope |
| --- | --- | --- |
| Orientation | `introduction.mdx`, `concepts/overview.mdx`, `concepts/architecture.mdx`, `getting-started/how-velto-works.mdx` | Native VNodes/reconciler; Cinnamon inside PSX; Qyro/CLI/Pydux separation |
| First application | `getting-started/overview.mdx`, `installation.mdx`, `first-app.mdx`, `project-structure.mdx`, `native-tkinter.mdx` | GitHub installation rather than unpublished PyPI assumptions; exact Python range; Qyro project settings and native toolkit |
| Authoring | `learn/psx-markup.mdx`, `conditional-rendering.mdx`, `lists-and-keys.mdx`, `components.mdx`, `state-and-events.mdx`, `effects.mdx`, `native-layout.mdx` | PSX Markup, quoted literals, hooks, stable keys, live Pydux store, geometric authority |
| Workflow and reference | `guide/styling.mdx`, `keys.mdx`, `native-integration.mdx`, `hot-reload.mdx`, `performance.mdx`, `distribution.mdx`, `advanced.mdx`, `compatibility.mdx`, `release-readiness.mdx` | CSS-like layout limitations; native ownership; dev modes; frozen Qyro resources; exact backend/platform limits |
| Catalog/reference | `components/overview.mdx`, `reference/overview.mdx`, `reference/application-and-state.mdx`, `reference/extensions-and-native.mdx` | Current public facade, generated source contracts and backend ownership limitations |
| Examples entry | `examples/overview.mdx` | Separates pinned historical PSX examples from current Velto facade integration receipts |
| Navigation/editorial | `docs.json`, `README.md` | Real page slugs and reproducible documentation validation commands |

### Source authority and executable receipts

- Public facade functions: `Neuri-AI/Velto` `main` at merge `53b9fd9eda66189535e1c7284dd0e3df7519c207`; `velto/ui/__init__.py`, `velto/state/__init__.py`; preserve object identity, avoid introducing wrapper APIs.
- CLI command spelling: `Neuri-AI/Velto-CLI` `release`, `velto_cli/cmdline/commands/{init,start,build,bundle}.py`. Start uses `--no-hot-reload`; build accepts `--mode`; bundle accepts `--format` and `--no-resources`.
- Native cross-package integration (Linux PySide6/Tkinter/Kivy, both Cinnamon engines): [CI 25/25](https://github.com/Neuri-AI/Velto/actions/runs/39962860498).
- Python installation and extra/backend matrix: [CI 19/19](https://github.com/Neuri-AI/Velto/actions/runs/39957504956).
- Frozen Linux Tkinter application `onefile`/`onedir`, encrypted Qyro `.pak`: [CI 4/4](https://github.com/Neuri-AI/Velto/actions/runs/39967824985).
- Sustained (two-minute) Tkinter state/heap ownership with both Cinnamon engines: [CI 2/2](https://github.com/Neuri-AI/Velto/actions/runs/39967825020).
- Windows Kivy native lifecycle: [PSX CI](https://github.com/Neuri-AI/PSX/actions/runs/39951131528). macOS ARM64 Kivy native lifecycle was owner-run on physical Mac; keep separate from the failed GitHub-hosted macOS graphical runner.

## Editorial QA and limitations

**Automated checks:** `python scripts/docs/validate_public_site.py`, `python -m unittest discover -s tests -p test_docs_public_site.py -v`, `mint validate`, `mint broken-links --check-anchors`, and `mint a11y`; all are required to be green on the final documentation commit. The first two validate metadata, local links and navigation; Mint validates MDX and site structure/accessibility. Docs-only synchronization must not be counted as executed product tests.

**Independent reader test:** *not yet externally certified*. The authored beginner project's exact source is illustrated in the page, but the 25-job installed integration suite exercises the same APIs with a different fixture (using explicit scope). Do not present the hello-world text block as an independently executed, exact-copy test unless a separately executed public example proves it. This belongs to the reproducible-example qualification in P4.5.

**Component/reference limitations:** existing generated API tables and backend-specific component reference pages are retained rather than blindly republishing edited signatures. Not every constructor, prop, gallery fragment, mobile target or third-party native widget was independently re-executed by this editorial pass. These pages must keep their own stated source revisions and avoid unsupported compatibility guarantees. The application/extension/reference indexes and example overview have now been reviewed and revised, but each individual historical example's exact pinned SHA remains its reproduction authority.

**Release blockers retained as explicit public notes:** macOS/Windows frozen distribution and signing/notarization, frozen Qt/Kivy, broad OS/DPI/input/scroll verification, longer (multi-hour) soaks, and every-examples-on-every-OS independent reproduction. The published [compatibility guide](/guide/compatibility) is intentionally narrower than the union of public exports.

**Disposition:** authoring and structural organization of the primary docs path are complete once exact-head docs CI passes. The project-wide P4 release gate remains open and P4.5 must cover independently executable examples and release-preparation evidence. No runtime/source API implementation was performed in this increment.

## Additional editorial checks

The previous integral documentation preflight identified missing beginner troubleshooting sections; the first-app and native-Tkinter lessons now include concrete diagnosis for environment setup, unavailable Tcl/Tk, missing display and incorrect project roots. The source-derived API contracts were regenerated directly by the repository's existing introspection tool rather than changing any reference validator or suppressing failures. The short-lived generation action was subsequently removed. Mintlify, structural/links/accessibility, generated-reference and integral-example checks must run on the final feature SHA before the editorial gate may be called green.

The native integration guide now includes a **clearly marked illustrative** `Native(SineChart)` pyqtgraph example, based on the tested `Native(QLabel)` Qt constructor; it does **not** claim that pyqtgraph itself passed CI. Toolkit compatibility remains explicit.
