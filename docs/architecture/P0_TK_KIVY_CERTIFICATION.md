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


## P0.9 CI #2 — Kivy comparison failure and scoped test fix (2026-10-18)

**Evidence:** owner-provided GitHub Actions run [#39134742987](https://github.com/Neuri-AI/PSX/actions/runs/39134742987) on commit `27870e5` and original failure logs for [Kivy 3.13](https://github.com/Neuri-AI/PSX/actions/runs/39134742987/job/117696952678) and [Kivy 3.11](https://github.com/Neuri-AI/PSX/actions/runs/39134742987/job/117696952452).

| Matrix cell | Result |
| --- | --- |
| Tk 3.10 and 3.13 | **SUCCESS** (owner screenshot; 2/2 jobs) |
| Kivy 3.11 and 3.13 | **FAILED**: 1 failed / 2 passed in each cell |

Both Kivy jobs initialized real SDL2 + Mesa under Xvfb. The failure was solely `assert borrowed.size_hint == original_size_hint` after unmount; earlier assertions confirmed the borrowed widget had returned to its original parent. Kivy's `ReferenceListProperty` exposes a list-like `size_hint` whereas `original_size_hint` in the test is a tuple. The renderer already captures `tuple(widget.size_hint)` and assigns that snapshot during `destroy()`; direct list-vs-tuple equality falsely rejects numerically identical values.

**Scoped correction:** [Kivy lifecycle test](../../tests/test_p0_kivy_native_lifecycle.py) now compares `tuple(borrowed.size_hint)` with the expected tuple. It additionally asserts original contents *before mount*, temporary `(None, None)` values *while mounted*, and restored contents after unmount. `pos_hint` is compared by `dict(...)`. **No Kivy renderer production code was changed.**

**Verification:** source change committed and re-fetched from `develop`; **new CI conclusion is not yet available at this writing**. Don't mark Kivy native certification green until the post-fix matrix run passes, including both Python versions.


## P0.9 Kivy CI follow-up — explicit Flex root (2026-10-18)

Owner-provided logs for both Kivy Python 3.11 and 3.13 show that the previous borrowed `size_hint` comparison no longer failed. The subprocess instead stopped at its final event-retirement scenario: `r.render(Button(...))` called native Cinnamon, whose certified contract requires exactly one explicit `Flex` root; `SFLECapabilityError: Native SFLE requires one explicit Flex root.`

**Test-only correction:** [`tests/test_p0_kivy_native_lifecycle.py`](../../tests/test_p0_kivy_native_lifecycle.py) now renders `Flex(Button(...), direction="column")` and accesses the event slot via `leaf.children[0]`, preserving the existing callback and detachment assertions. Commit `89173a3`. The renderer and layout contract are unchanged.

**Verification status:** source re-fetched after commit; new post-fix CI run still unverified. Tkinter 3.10/3.13 remained screenshot-confirmed green from the earlier matrix. Kivy 3.11/3.13 must pass the updated run to certify this stage.


## Screenshot-confirmed green native matrix — 2026-10-18

The owner supplied a screenshot of **P0 Tkinter Kivy native lifecycle run #4** on `develop`, commit prefix `89173a3`, with overall **SUCCESS** and four individually green jobs:

| Backend | Python | GitHub Actions result |
| --- | --- | --- |
| Tkinter | 3.10 | SUCCESS (owner screenshot) |
| Tkinter | 3.13 | SUCCESS (owner screenshot) |
| Kivy | 3.11 | SUCCESS (owner screenshot) |
| Kivy | 3.13 | SUCCESS (owner screenshot) |

This closes the **initial Linux/Xvfb native lifecycle test matrix** only. Individual full job logs/test totals are not included in the screenshot. This is **not** a 1,000–10,000 cycle memory-soak or GC/weakref plateau certification, nor Windows/macOS backend parity. Remaining P0.9 work is measured memory retention testing and a clean multi-repository Velto + PSX + Pydux + Qyro package installation. No global Architecture Gate or AD-05/AD-07 owner sign-off is implied.
