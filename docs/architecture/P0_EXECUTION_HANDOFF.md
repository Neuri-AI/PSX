# P0.7 — Executable Verification Handoff (H-MEM-01 / H-PKG-01)

**Date:** 2026-10-18 · **Status:** TEST SOURCE COMMITTED; RUN RESULTS NOT YET AVAILABLE  
**Target:** `Neuri-AI/PSX:develop` · **Scope:** no production modifications, no contract ratification.

## H-MEM-01 — Native lifetime on throwing effect cleanup

**Committed regression probe:** [`tests/test_p0_teardown_diagnostics.py`](../../tests/test_p0_teardown_diagnostics.py).

**Exact invocation** (Python 3.10–3.13, repository root, installed project dependencies):

```bash
python -m unittest discover -s tests -p test_p0_teardown_diagnostics.py -v
```

The suite has two checks:

1. **Normal path:** a renderer-free mounted tree with one effect cleanup, parent and child handles. The test requires cleanup once, destruction order child → parent, and root cleared.
2. **Fault injection:** a hook cleanup throws. The **desired C07 contract** requires all independent native handles to be destroyed despite the exception. The case is decorated with `@unittest.expectedFailure` to avoid blocking existing CI before owner approves C07 changes. The current `_unmount` and `dispose_hooks` source strongly predicts the assertion cannot be reached without a cleanup-safe rewrite.

**Important:** `expected failure` is not a PASS for the desired contract. A green suite with an expected failure confirms a known gap was tracked; an `unexpected success` should trigger re-review and conversion to a normal assertion. The test uses a fake renderer and **cannot certify Qt deleteLater, Tk destroy, Kivy borrowed native handles or RSS**.

**Additional native tests needed:**
- PySide6/PyQt6/PyQt5/PySide2: native QWidget lifetime, Qt event-loop drain, signal unbind and stale closures.
- Tkinter: real widget destruction, after callback cancellation and repeated mount/unmount.
- Kivy: parent/hint restoration for borrowed widgets and Clock watcher disposal.
- 100–1000 churn cycles, weakrefs/native handle counts, settled allocations and same-process idle plateau.
- Fault injection for `unbind_event`, child `destroy`, partial `create` rollback and pending `Scheduler` callbacks.

**Recording receipt:** immutable commit SHA; exact command; Python/OS; stdout/stderr; exit code; test names and counts; screenshot or artifact where relevant. Do not replace this with an assertion that tests 'should pass'.

## H-PKG-01 — Actual wheelhouse resolution

**Evidence already present:** [P0 verification report](P0_VERIFICATION_REPORT.md#7-offline-pep-440-specifier-intersection-check-2026-10-18) contains a narrow PEP 440 specifier mismatch check. It does **not** prove pip install failure against the current published index.

**Required reproducible run** after pinning exact SHAs of `Neuri-AI/PSX`, `Neuri-AI/Velto`, `Neuri-AI/Pydux` and Qyro Engine/CLI:

```bash
python -m venv .venv-p0
. .venv-p0/bin/activate  # Windows: .venv-p0\\Scripts\\activate
python -m pip install --upgrade pip build
python -m build --wheel --outdir dist-p0  # run separately in EACH checked-out repo
python -m pip install --dry-run --report pip-p0-report.json 'velto[pyside6]'
python -m pip check
```

**Caveat:** `pip check` is meaningful only after an actual installation; dry-run alone is insufficient. For wheelhouse-only verification, aggregate built wheels from each repo into a common directory and install into a **new clean environment** with `--no-index --find-links <wheelhouse>`. Do not run against arbitrary mutable local source without recording SHAs.

**Required matrix:** 3.10–3.13, selected Qt family extras, Tk default, Kivy 2.3.x supported cells, PySide2 3.10 only. Record failed package names and exact resolver trace, not only exit status. Smoke test `from velto import VeltoContext`, `from velto.ui import psx`, and a mounted PySide6 app where display access is available.

## Architecture Gate effect

- **H-MEM-01:** test source available; actual runtime/native evidence pending; proposed C07 exception policy owner approval pending.
- **H-PKG-01:** source metadata/specifier incompatibility supported; wheelhouse and public-index resolver execution pending.
- **Architecture Gate:** BLOCKED. Do not declare P1 ready or edit production code based on this handoff alone.


## P0.7 interim execution receipt (2026-10-18)

An **isolated non-GUI Python harness actually reproduced** the H-MEM-01 teardown failure using the method bodies of `Reconciler._unmount`, `Reconciler.unmount` and `dispose_hooks` from current fetched `develop` source. Normal teardown destroyed `['child', 'parent']`; injected throwing effect cleanup destroyed `[]`, left the child marked not disposed and left reconciler root attached. **It was not an in-repository test run and did not measure a real native memory leak.** Full evidence and source blob SHAs are recorded in [P0 verification §8](P0_VERIFICATION_REPORT.md#8-p07--isolated-fault-path-execution-and-current-manifests-2026-10-18).

Current PSX `velto-core`, facade `velto`, Pydux and Qyro Engine project manifest version/range pairs were checked with an **actually executed** `packaging.specifiers` comparison and found incompatible for the three listed source-version pairs. Public availability and actual pip resolution remain untested. Direct GitHub checkout failed because the container could not resolve `github.com`. This handoff therefore preserves the missing **real project test, wheel-build and native** gates explicitly.

**Do not convert isolated-harness evidence into a native memory-leak claim or an install-failure claim.** Keep the gate BLOCKED pending full execution, owner-approved error policy and release version alignment.
