# Velto public documentation

Canonical developer-facing Mintlify documentation for Velto. Start with [the introduction](introduction.mdx), [installation](getting-started/installation.mdx), and [the first application](getting-started/first-app.mdx).

**Current scope:** first-party packages `0.1.0`, Python `>=3.10,<3.13.20`. Velto is a native Python framework using **PSX Markup**, not a browser DOM. The documentation explains Qyro Engine, PSX (including Cinnamon), Pydux, the CLI, and the public facade from inspected source.

## Page map

- Getting started: overview, GitHub installation, first application, project structure, execution with Tkinter and an architecture walkthrough.
- Language and UI: PSX Markup, conditions, lists and keys, components, hooks, state and native layout.
- Practical guides: box-model styling, identity, native integration, hot reload, performance, distribution, compatibility, advanced APIs and release limitations.
- Existing component, API and gallery references remain accessible. Their source-specific signatures and examples should be checked against their original API contract before reusing them in other projects.

## Evidence and limitations

See [compatibility](guide/compatibility.mdx), [distribution](guide/distribution.mdx), and [release readiness](guide/release-readiness.mdx). Supported package installations, native integration, resource checks and frozen releases have different platform evidence; **no single CI receipt certifies all of them**. A rendered documentation page or import smoke test is not an executable sample application.

Developer examples are expected to use Python, PSX Markup and native toolkits, not browser HTML; no `<Window>` tag or `psx.markup.transform` command is required.

## Validate

From the PSX root:

```bash
python scripts/docs/validate_public_site.py
python -m unittest discover -s tests -p test_docs_public_site.py -v
cd docs/public
npm install --no-package-lock --no-audit --no-fund
npm run validate
npm run links
npm run a11y
```

The docs workflow runs those checks, and its success must be read from the exact head commit. Documentation-only changes do not introduce runtime capabilities and should route **zero** product tests. See [documentation verification handoff](../architecture/public-documentation-verification.md) for review status and unresolved reproduction coverage.
