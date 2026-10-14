# F5.5 — Public Developer Documentation Contract (Velto / PSX)

**Status:** APPROVED BY PROJECT OWNER — 2026-10-14. Implementation NOT STARTED.  
**Canonical repository and branch:** [Neuri-AI/PSX — develop](https://github.com/Neuri-AI/PSX/tree/develop).  
**Public documentation root:** `docs/public/` **on develop**.  
**Normative contract location:** `docs/architecture/f5-5-public-documentation-contract.md`.  
**Implementation continuity ledger:** `docs/architecture/f5-5-public-documentation-progress.md`.  
**Phase boundary:** F5 CLOSED; F5.5 documentation; F6 (M8 hot reloading) postponed.

## 1. Mission

Build **detailed, beginner-first, real, verifiable public developer documentation** for Velto/PSX. Assume readers know basic Python but have never seen Velto, PSX markup, Cinnamon, hooks, reconciliation, VNodes, Qt, Kivy or Tkinter. Teach concepts before introducing jargon. A reader must be able to go from a clean machine to a running native application with no missing steps or inferred configuration.

Initial scope: actual, exported Velto/PSX APIs, PSX markup/compiler and restricted runtime-template behavior, hooks, component catalog including supported F4 components, layouts/Cinnamon, native renderers, native interoperability, extensibility/plugins, public exceptions, lifecycle and tested behavior. Prepare a scalable structure for **later** Pydux, Qyro Engine and Velto CLI integration; do not document unfinished integration as released behavior.

**This is a documentation phase, not a mandate to implement new framework APIs.** Report missing or broken APIs as gaps; obtain authorization before changing their semantics.

## 2. Binding authority and source discipline

1. **Every technical statement MUST be grounded in the current code, tests and current architectural contracts in `develop`**, checked directly in GitHub at the start of work, not in remembered context, old uploads, feature branches or merged-but-stale notes.
2. Pin an exact immutable commit SHA from `develop` for each inventory snapshot and published/tested example. Link relevant production definitions and behavioral tests. `develop` is the branch of publication, SHA is the reproduction anchor.
3. Inspect `psx/__init__.py` and any actual public re-export modules. Enumerate symbols, signatures, defaults, errors, lifecycle, child policies, native backend/OS/Python support and existing tests. Cross-check registries and F4/F5 implementations. Do NOT treat earlier '56' or '59' export counts as authoritative.
4. Resolve contradictions between source, tests and docs explicitly. Mark unverified, experimental and unsupported behaviors accurately. Do not fabricate public features or copy React, HTML, or Qt semantics as if Velto implements them.
5. Preserve historical certification records accurately, even when modernizing terminology. Clearly distinguish the static, developer-authored PSX compilation path from restricted, dynamic/explicit-scope template interpretation; renaming M4A/M4B is **not** authorized by F5.5.
6. Do not silently assume `from velto import ...` or `from vento import ...` works: the verified import path in the target SHA takes precedence; describe future rebranding separately.

## 3. Audience and pedagogy — required on every beginner guide

Write canonical public pages in **clear English**, with concrete explanations, accurate terminology and no unexplained jargon. Each beginner tutorial MUST contain:
- What readers will build; actual verified screenshot/output and expected interaction.
- Prerequisites with supported Python, OS, renderer and tools.
- Full commands for installing and activating a clean environment, including platform differences.
- A complete file tree and the **full contents of every required file**, including settings, entry points and compiler/build configuration.
- Exact install, transformation (when needed), run and test commands that work from the stated working directory.
- Explanation of how each relevant API works and *why* it is used.
- Observable expected outcome; troubleshooting steps for tested common failure modes.
- Executable assertions/tests and a link to passing CI/manual native evidence.
- Next steps, related references and one or more realistic variations.
- Accessible descriptions accompanying diagrams and media.
- Review by a person or independent agent who did not author the example, following **only the page**.

No unexplained placeholders, ellipses, pseudo-imports, invented configurations, or code that requires unstated prerequisite steps. Illustrative fragments must be clearly labeled **non-standalone** and never presented as reproducible applications.

## 4. Reproducibility and evidence

Every runnable example MUST be an actual runnable project saved in the repository and linked from its MDX page; provide lock/constraints where appropriate, exact dependency versions, entry point, settings, and instructions to reproduce against the target SHA. Exercise observable behavior through pytest (or documented equivalent), not merely import tests. Where a native renderer is promised, native checks must run for that backend, or the coverage limitation must be explicitly called out; Headless-only evidence is not native coverage.

For each public example record: slug, doc page, example directory, SHA, entry command, tests, selected renderer/OS/Python matrix, CI run URLs, skipped cells and justified exclusions. CI failure or unverifiable behavior blocks certification. New documentation examples should be integrated into intelligent CI selection (`scripts/ci/impact.py` where applicable), workflow commands and router tests. Do not weaken test expectations or hide real failures.

## 5. Mintlify requirements and file organization

All public pages are **`.mdx` compatible with the pinned Mintlify version**. Mintlify navigation/configuration lives at `docs/public/docs.json` (not repository root); validate the actual Mintlify schema and commands before announcing publishing/deployment readiness.

Recommended directory map (adjust after G1 audit; document changes):

```text
docs/
  architecture/
    f5-5-public-documentation-contract.md
    f5-5-public-documentation-progress.md
  public/
    docs.json
    introduction.mdx
    getting-started/
      installation.mdx
      first-app.mdx
      project-structure.mdx
      how-velto-works.mdx
    learn/
      components.mdx
      psx-markup.mdx
      state.mdx
      events.mdx
      conditional-rendering.mdx
      lists-and-keys.mdx
      effects.mdx
      native-layout.mdx
    components/
    api/
      hooks/
      markup/
      application/
      native/
      plugins/
      exceptions/
    guides/
    concepts/
    examples/
```

The following page families MUST have reusable MDX templates with consistent metadata, structure and acceptance checks:

1. **Introduction:** use cases, capabilities, constraints, beginner orientation.
2. **Beginner Guide:** prerequisites, full project, step-by-step execution, plain-English teaching, troubleshooting.
3. **Concept:** mental model, verified architecture/sequence diagram, limits, relevant real sample.
4. **API Reference:** canonical import, exact signature, types/defaults/return, errors, lifecycle/threading, sample, evidence.
5. **Component Reference:** role, props/defaults, events, child policy, supported backends, state/reconciliation, samples, known limitations.
6. **Reproducible Example:** clone/install/run/test, full source, expected result, platform matrix, immutable SHA/CI receipts.

Frontmatter MUST include `title` and `description`. Use Mintlify-supported features (e.g. Steps/Tabs/Notes) only after confirming their documented syntax. Ensure meaningful headings, descriptive links, alt text, relevant examples, linted MDX, valid local navigation and links.

Mermaid/SVG architectural diagrams MUST reflect the actual code flow and identify which stages are compile-time vs runtime. Real UI screenshots MUST derive from real applications, not imagined results.

## 6. Required public inventory and content areas

The G1 audit MUST derive, classify and trace every real public symbol: component/function/class/exception/constant, exported path, signature and defaults, type and allowed children, events, backend-specific implementation, exceptions, lifecycle, relevant code/test paths, caveats, doc path, CI evidence. Organize audience-visible content by learning progression, not solely by Python module layout.

Initial candidate subjects from prior review (verify each on `develop`; NOT a claim of current coverage): `App`, `component`, `psx`, `create_element`, `VNode`, `use_state`, `use_effect`, `use_ref`, `Ref`, `Text`, `Button`, `Input`, `TextArea`, `Checkbox`, `Switch`, `Radio`, `RadioGroup`, `Select`, `Slider`, `SpinBox`, `ProgressBar`, `Image`, `Link`, `Badge`, `Row`, `Column`, `Scroll`, `Spacer`, `Divider`, `Fragment`, `Flex`, `Grid`, `GridItem`, native widget interop, registries, plugins, adapters and exported errors. Every candidate must be verified (possibly renamed, removed or unsupported) before publication.

Maintain clear **Everyday API** versus **Advanced / Extension API** navigation. Do not omit advanced exports even if they are hidden from beginner navigation.

## 7. Architectural invariants to explain, never contradict

- Python-authored PSX has a static lexical/expressive compilation path; restricted dynamic templates do not gain arbitrary code execution. No production `eval`, `exec` or frame-introspection name lookup.
- Curly braces represent approved references/expressions. Quote static attribute literals (`gap="12"`); do not teach `gap={12}` as valid.
- Static expressive markup includes approved conditional operators, keyed `.map()`, lexical arrow callbacks; compilation generates Python AST and operates through existing VNode/reconciler and native renderers.
- **Cinnamon** alone owns geometry computation, distinct from backend-specific measurement/rendering.
- Window title/size/configuration reside in settings, **not** in a nonexistent `<Window>` component.
- Hook order, reconciliation keys and native lifecycle must follow verified contracts.
- Different Qt bindings, Tkinter, Kivy and Headless coverage must not be conflated. Avoid claiming `disabled` or other props until current public component contracts prove them.
- No browser is inserted between Velto and its native UI runtime. Defer M8/Hot Reloading to F6.

## 8. Gates and closure rules

- **G1 — Source audit and API census:** pin develop SHA, enumerate all real public exports/registries, code/tests/compatibility, issues and authoritative inventory. No missing or imaginary API.
- **G2 — Mintlify architecture and standards:** approved IA, Mintlify config validated, six page templates, editorial guide, internal link and diagram patterns, source/evidence metadata.
- **G3 — Beginner learning path:** complete installation, Hello World / first native app, fundamentals, hooks, conditional/list/event/layout learning; all tutorial steps independently reproduced.
- **G4 — Exhaustive API references:** every in-scope public symbol documented with actual signature/defaults/props/events/child policies/errors/backend support and tested examples.
- **G5 — Real-world runnable projects and DX:** beginner-to-advanced applications, native interop, error guides, valid full project trees and cross-platform test receipts.
- **G6 — Integral documentation certification:** Mintlify build/schema/navigation/link tests, API census-to-pages completeness, example execution, native matrix and exceptions, source SHA, passing CI, independent beginner review, **explicit owner signoff**.

**No gate is CLOSED just because files exist, prose is written, or one job is green.** Track applicable GitHub Actions on immutable code SHAs; report skipped/unavailable suites honestly. Update the continuity ledger after *each* increment with changed files, coverage, tests/commands, CI run IDs, immutable SHA, blockers, decisions, gate status and next step. Follow existing Conventional Commits rules and preserve existing F5 certificates.

## 9. Definition of Done

F5.5 is CLOSED only when:
- `docs/public/` contains correctly configured, navigable Mintlify MDX.
- API inventory based on `develop` is exhaustive, and public API reference coverage is complete.
- Every executable published example is complete, actually reproducible, behavior-tested and linked to evidence.
- Guides pass beginner-first independent reproduction, including errors and expected UI outcomes.
- Layout/compilation/native/runtime diagrams are consistent with code; unsupported behavior is flagged.
- Build, links, imports, exact API signatures, intelligent CI routing and applicable native suites pass.
- Progress and decisions are recorded under `docs/architecture/` with immutable SHAs.
- The project owner explicitly accepts G6.

**Owner-approved decisions (2026-10-14):** documentation must live on the `develop` branch under `docs/public/`; normative contract and full continuity records live in `docs/`; Mintlify-compatible MDX; beginner-proof, highly detailed educational writing; real reproducible examples; 100% code/documentation/test-grounded from `develop`; eventual integration with Qyro Engine, Pydux and Velto CLI.
