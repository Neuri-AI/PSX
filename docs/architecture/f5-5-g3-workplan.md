# F5.5 G3 — Beginner-first learning path

**Starting source SHA:** `eb1f589a75a22a7d5a5c0cd35a7bc8f7d5b96e61` (`develop`, 2026-10-14).

## Scope and precedence

G3 develops real Python examples, tests and the beginner path. G2 PR #33's `docs/public/` is **not yet merged into develop** at this starting SHA. To avoid pretending files from that PR are in the authoritative branch, this increment uses real example sources in `examples/f5_5_beginner/` and tracks page integration as blocked until G2 is merged.

The examples import the actual `psx` namespace. The first is a deterministic headless Hello World; the second exercises `@component`, `use_state`, an `on_click` callback and reconciliation in Headless. Native GUI behavior and screenshots are **not** implied by headless success.

## Run

From the repository root with supported Python (`>=3.10,<3.14` per `pyproject.toml`):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/f5_5_beginner/hello_world.py
python examples/f5_5_beginner/counter.py
cd examples/f5_5_beginner
python -m unittest -v test_examples
```

Windows PowerShell activation: `.venv\\Scripts\\Activate.ps1`. If Python cannot create a venv, install an OS Python distribution including `venv` and `pip`.

Expected Hello World output: `Hello, Velto!`. Expected Counter output: `Count: 0` followed by `Count: 1`. Both require execution evidence; prior to CI they are specified expected values, not certified observations.

## G3 remaining work before closure

1. Wait for canonical G2 Mintlify architecture on `develop`, then add and link pages for installation, first native app, project structure, markup, state, events, keyed lists, conditionals, effects and layout.
2. Add **native** Qt/Tkinter/Kivy running projects and environment-specific command recipes; independently reproduce their developer instructions.
3. Attach real GUI screenshots/outputs, renderer/OS/Python matrix, independent review and immutable GitHub Actions receipts. Never pass Headless-only evidence off as native coverage.

**Current status:** G3 IN PROGRESS. This initial increment does not satisfy full G3 acceptance.
