# P0.9 — Tkinter and Kivy Native Lifecycle Certification

**Date:** 2026-10-18  
**Status:** TEST SOURCE + CI MATRIX COMMITTED; **NATIVE RUN RESULTS NOT VERIFIED**  
**Branch:** `Neuri-AI/PSX:develop`  
**Scope:** targeted C07 lifecycle verification before P1 Web-like/CSS-like work.

## Artifacts

- [Tkinter native lifetime regressions](../../tests/test_p0_tkinter_native_lifecycle.py) — three tests using actual Tcl/Tk widgets, not fake renderer handles.
- [Kivy native lifetime regressions](../../tests/test_p0_kivy_native_lifecycle.py) — one isolated subprocess with multiple native lifecycle assertions.
- [P0 Tkinter/Kivy matrix](../../.github/workflows/p0-tk-kivy-lifecycle.yml) — GitHub Actions, Linux/Xvfb, Tk Python 3.10/3.13 and Kivy Python 3.11/3.13.
- Existing [Tk renderer tests](../../tests/test_tkinter_renderer.py) and [Kivy renderer tests](../../tests/test_kivy_renderer.py) run alongside new probes.

## C07 acceptance cases

| ID | Backend | Actual assertion | Limitation |
| --- | --- | --- | --- |
| TK-01 | Tkinter | A throwing `use_effect` cleanup propagates error yet its owned label is destroyed and root cleared | Tests one child/root, not every adapter |
| TK-02 | Tkinter | 100 mount/unmount cycles leave each old native widget with `winfo_exists() == False` | Does not measure RSS or Python heap plateau |
| TK-03 | Tkinter | Native Button callback can fire when mounted, event slot inert after unmount, native widget destroyed; `close()` marks renderer closed/cancels polling | No multithreaded callback storm |
| KV-01 | Kivy | Throwing effect cleanup still removes owned layout child and clears mounted root | Native detachment, not Python GC evidence |
| KV-02 | Kivy | 100 cycles detach previously mounted Text widgets | Does not measure weakrefs or RSS |
| KV-03 | Kivy | Borrowed Label restores its original parent, `size_hint`, and `pos_hint` | Only one native class and layout scenario |
| KV-04 | Kivy | Button callback is inert after unmount, widget detached | No Clock observer-count assertions |

Kivy probes run in a **single short-lived subprocess** to avoid global native app/window state contaminating other tests. Unlike the existing Kivy test module, this new certification probe does **not skip** when a display provider is unavailable: CI must expose the environment failure rather than report false portability success. Tk uses one interpreter in each job and explicitly closes each borrowed-root renderer.

## CI behavior and interpretation

Workflow: [P0 Tkinter Kivy native lifecycle](https://github.com/Neuri-AI/PSX/actions/workflows/p0-tk-kivy-lifecycle.yml).

| Job | Runner | Evidence required |
| --- | --- | --- |
| Tkinter Python 3.10 | Ubuntu, Xvfb | successful test logs and exact SHA |
| Tkinter Python 3.13 | Ubuntu, Xvfb | successful test logs and exact SHA |
| Kivy Python 3.11 | Ubuntu, Xvfb | successful test logs and exact SHA |
| Kivy Python 3.13 | Ubuntu, Xvfb | successful test logs and exact SHA |

CI uses real native Tk and Kivy widgets under Xvfb; it does not replace those renderers with mocks. Environment/library failures must be distinguished from framework regressions from the failing step logs. **No CI run outcome is claimed at publication.**

Run locally from repo root:

```bash
xvfb-run -a python -m pytest -q tests/test_p0_tkinter_native_lifecycle.py tests/test_tkinter_renderer.py
xvfb-run -a python -m pytest -q tests/test_p0_kivy_native_lifecycle.py tests/test_kivy_renderer.py
```

**Python versions/OS scope:** This initial Linux matrix is not evidence of Windows/macOS or the full Python support grid. Expand only after green same-SHA receipts, not by marking untested combinations supported.

## Still needed before P1

1. Inspect four current CI jobs, fix any verified issues and attach immutable source SHA, test counts, skip counts and logs.
2. Run long-lived memory/weakref/retained-subscription soak across PySide6, Tkinter and Kivy (1000–10000 iterations with quiescence, not just a short subprocess).
3. Resolve C05 public distribution names and versions and execute a **single-environment** clean installation of Velto, PSX/velto-core, Pydux and Qyro.
4. Preserve explicit owner acceptance for AD-05 cleanup error semantics and AD-07 package graph.

**Architecture Gate is still BLOCKED; merely committing tests or CI config does not certify a backend.**
