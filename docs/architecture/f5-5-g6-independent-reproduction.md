# F5.5-G6 Independent Beginner Reproduction and Owner Signoff

**Canonical baseline:** `develop` at `99309877c05dcfc743d287464407342c5e346d3a`.
**Working branch:** `docs/f5-5-integral-certification` — one branch/PR for all G6 corrections.

## Scope and pass criteria

A reviewer **who did not write the documentation or projects** must work from a fresh checkout of the exact reviewed commit, read only the public Mintlify pages, and execute the prerequisites, installation, example commands and tests without relying on unstated knowledge. A CI job run by the author is not an independent reviewer.

For each of the following public pages, record the reviewer identity or review handle, date, immutable SHA, OS, Python, environment prerequisites, exact commands, observed native UI/terminal output, deviations, reproducibility verdict and supporting screenshots or logs:

- `getting-started/installation` and `getting-started/first-app`;
- `getting-started/native-tkinter`;
- `examples/task-board`;
- `examples/native-gallery`, `examples/qt-gallery`, `examples/kivy-gallery`.

Use `docs/architecture/f5-5-g6-example-manifest.json` as the executable source and coverage map. The Python static preflight only verifies declared coverage and repository files; it does not emulate this review.

## Native coverage / exclusions

The existing G5 jobs establish Ubuntu Linux Headless and bounded native mounting of Tkinter, PySide6 and Kivy for the versions enumerated in the manifest. They **do not** establish user-visible geometry, native screenshots, manual click behavior, accessibility of widget focus/navigation, or Windows/macOS execution. These must be explicitly reproduced or documented as unsupported/excluded with justification; do not turn untested cells into PASS.

## Review receipt template

| Field | Required value |
| --- | --- |
| Reviewer (independent of author) | PENDING |
| Checkout SHA | PENDING |
| Documentation URL/page and test case | PENDING |
| OS/Python/renderer | PENDING |
| Exact steps and commands | PENDING |
| Native screenshot/log reference (when applicable) | PENDING |
| Expected versus actual behavior | PENDING |
| Bugs or missing steps | PENDING |
| Verdict | **NOT REVIEWED** |

## Release/owner gate

The owner must explicitly accept the final F5.5 documentation release *after* the independent review and all required CI are green at an immutable SHA. No assistant or agent may infer, fabricate or grant this approval.

**Owner signoff: PENDING. Overall F5.5: OPEN.**

## Additional clean-room automation (not an independent human review)

The workflow `.github/workflows/f5-5-clean-room-reproduction.yml` now provisions a **new Python virtual environment** on GitHub-hosted Ubuntu, macOS and Windows. It follows the beginner import, Hello World, Counter and Task Board terminal commands and executes their behavioral tests on Python 3.11 and 3.12. It specifically expands **cross-OS Headless reproducibility**, not native Qt/Tkinter/Kivy interactivity.

**Review classification:** even six green clean-room jobs are automated author-configured checks. They do not meet the contract's separate reviewer criterion. The human/independent-agent receipt above remains NOT REVIEWED until that distinct reviewer supplies actual observed evidence. Similarly native GUI screenshots and owner approval remain pending.

### Reviewer execution order (do not use implementation notes as instructions)

1. Check out the SHA to be certified using only the linked public guide.
2. Execute `getting-started/installation`, `first-app`, and `state-and-events`; capture exact terminal output and any missing steps.
3. Execute each public project from its guide, including native GUI controls on a physical or graphical desktop session. Capture genuine window screenshots and manual event observations.
4. Compare any errors with the pages' troubleshooting instructions. File issues when instructions need unstated steps.
5. Record results in the receipt template and sign explicitly as an independent reviewer. Only then request owner acceptance.
