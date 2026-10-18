# P0.8 — Native Lifetime and Wheel Smoke Certification

**Recorded:** 2026-10-18  
**Branch:** `Neuri-AI/PSX:develop`  
**Status:** TESTS + CI CONFIGURATION COMMITTED; **RUN RESULT NOT VERIFIED**

## Scope and evidence

This is a targeted follow-on to [P0 C07 cleanup regression](P0_VERIFICATION_REPORT.md). New repository artifacts:

- [`tests/test_p0_pyside6_native_lifecycle.py`](../../tests/test_p0_pyside6_native_lifecycle.py): real PySide6 QWidget/QObject tests (not a fake renderer).
- [`.github/workflows/p0-native-lifecycle.yml`](../../.github/workflows/p0-native-lifecycle.yml): separate CI triggered on changes to relevant source/tests and manual dispatch. Jobs include **PySide6 native lifetime on Python 3.10 and 3.13** and **fresh-venv wheel smoke**.

### Native PySide6 tests

1. **Throwing hook disposer:** mount a PSX component that owns a QPushButton; allow `use_effect` to register a cleanup throwing `RuntimeError`; require `unmount` to propagate the exception, clear root, and release the `QWidget` after `QCoreApplication.sendPostedEvents(..., DeferredDelete)`. Actual deletion is checked with `shiboken6.isValid`.
2. **Repeated mount/unmount:** 50 Text/QLabel mount/dispose cycles in one QApplication; require every previous wrapper to become invalid after Qt deferred-deletion drain. Counts are **not** RSS measurements.
3. **Event connection retirement:** bind Button click, observe one invocation, unmount, assert the stable callback slot is inert and underlying widget invalid.

The CI additionally executes existing `tests/test_pyside6_renderer.py` to cover current renderer behavior. `QT_QPA_PLATFORM=offscreen` is set before Qt startup and minimal Qt host libraries are installed.

**Expected meaning of future green:** these cases passed in Qt offscreen Python 3.10/3.13 on the exact workflow commit. It does not prove Tkinter/Kivy parity, all Qt bindings, production-scale image lifetime, 1000-cycle RSS plateau, or cross-machine memory boundedness.

### Wheel smoke tests

The second job builds a wheel from the **current PSX source checkout**, creates a fresh `venv`, installs that exact artifact with `--no-index --no-deps`, executes `pip check`, and imports `psx` while querying distribution `velto-core`. This only verifies the local `velto-core` wheel; it does **not** validate the Velto facade and Pydux/Qyro cross-repository dependency graph or online resolver behavior.

### Run-status verification

The available GitHub connector fetches commit-attached **pull-request** workflow runs; it did not return a run for the new **push** commit. The Actions webpage was not retrievable in this session. Thus there is **no claimed executed pass or failure** for P0.8. Check [GitHub Actions: P0 native lifecycle verification](https://github.com/Neuri-AI/PSX/actions/workflows/p0-native-lifecycle.yml), inspect both PySide6 matrix cells and wheel-smoke job, and attach run ID, SHA, exact test counts and logs.

### Remaining gates

| Area | Current status |
| --- | --- |
| C07 headless core regression | Screenshot-confirmed success on previous P0 matrix |
| C07 PySide6 native teardown | Committed test/workflow; **run unverified** |
| C07 Tkinter/Kivy ownership | **NOT CERTIFIED** |
| C07 memory pressure / RSS plateau | **NOT CERTIFIED** |
| C05 isolated `velto-core` wheel | CI job configured; **run unverified** |
| C05 Velto + PSX + Pydux + Qyro clean install | **NOT CERTIFIED**, H-PKG-01 remains |
| AD-05 / AD-07 normative approval | **PENDING owner** |

**Architecture Gate: BLOCKED.** A configured job is not a run receipt.
