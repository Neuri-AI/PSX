# F5.5 G2 — Public documentation editorial and architecture guide

**Source baseline:** `develop` SHA `e8b8e24de6937fa4875d830c8cdf442c54f69544`.
**Public root:** `docs/public/`. **Config:** `docs/public/docs.json`.
**Mint CLI pin:** npm package `mint@4.2.988`, exact version, Node 20.17–24. The pin is an editorial/tooling choice; a passing Mintlify CLI validation run is still required before declaring G2 technically certified.

## Information architecture

Navigation currently exposes only substantive, non-speculative entry pages: Introduction, Getting started, Core concepts, Component catalog, Python reference and Reproducible applications. G3 adds beginner tutorials; G4 adds complete Everyday and Advanced references; G5 adds tested projects. Do not create dead navigation links for future Pydux, Qyro Engine or Velto CLI integrations. Do not add F6/M8 content.

The six reusable templates are in `docs/public/_templates/` and intentionally excluded from the public site via `.mintignore`. Copy the appropriate template to a real slug, replace every editorial instruction and then add the page to `docs.json`. Every public page requires `title` and `description` YAML frontmatter.

## Voice, accuracy and evidence

- Write in clear English for a Python beginner. Define VNode, hook, renderer, reconciliation and Cinnamon before using them.
- Use active voice and numbered steps for commands. Every advertised runnable snippet needs a complete repository example, exact commands and actual behavior tests.
- Source claims must cite a concrete immutable source SHA, file/definition and applicable behavioral test. Distinguish a test-file *candidate* from an assertion that actually exercised a behavior.
- Always show real Python import spelling (`psx`) and quote static PSX attribute literals (`gap="12"`). Do not invent `<Window>`, browser/DOM behavior or React props.
- For components list props, defaults, event payloads, child policy and backend-specific exclusions. Never infer native compatibility from registry membership.
- A native claim needs a backend-specific CI/manual receipt and OS/Python cell; Headless does not certify Qt, Tkinter or Kivy.
- Screenshot: capture from a real application and record OS, renderer, SHA, date and image alt text. No invented screenshots or outcomes.
- Diagram: use `mermaid` fenced code blocks or checked-in SVG with alt text. Include a prose text alternative, label compile-time vs runtime and distinguish Cinnamon from native measurement.
- Cross-reference pages with root-relative paths such as `[Architecture](/concepts/architecture)`. Do not link to unpublished page slugs.

## Verification

From repository root:

```bash
python scripts/docs/validate_public_site.py
python -m unittest discover -s tests -p test_docs_public_site.py -v
cd docs/public
npm install --no-package-lock --no-audit --no-fund
npm run validate
npm run links
npm run a11y
```

The Python checks verify navigation existence, metadata, local Markdown links and templates. They **do not parse MDX**. The pinned Mintlify CLI must perform strict build/schema/MDX checks and internal-link validation in CI; if unavailable, mark G2 pending, not green. GitHub Actions job logs and immutable SHAs are required.

## Page-family acceptance

1. Introduction: what Velto is, realistic limits, who it serves and next link.
2. Beginner guide: prerequisites, exact environment and commands, full project tree/files, compile/run, expected result, behavior tests, troubleshooting and independent reproduction.
3. Concept: plain-language mental model, source-backed diagram and text alternative, verified limitations and relevant example.
4. API reference: canonical import, signature, types/defaults/returns, exceptions, lifecycle/threading, examples and source/test receipts.
5. Component reference: props/defaults, events, child policy, renderer matrix, reconciliation, runnable example and receipts.
6. Reproducible example: complete files, pinned SHA and dependencies, clean install, run/test, expected outcome, screenshot provenance, native matrix, CI evidence and exclusions.

**G2 is a site architecture gate, not a claim that G3–G5 content is published or behavior-certified.**
