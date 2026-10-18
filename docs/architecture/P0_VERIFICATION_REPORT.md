# P0.3 — Verification Report and Reproduction Protocol

**Date:** 2026-10-18  
**Status:** STATIC VERIFICATION COMPLETE FOR SCOPED CLAIMS; EXECUTED VERIFICATION PENDING  
**Canonical target:** `Neuri-AI/PSX` / `develop`  
**Baseline source anchor:** [PSX commit `847a08035d08d3d66c0bffd2b7df3743f938f5aa`](https://github.com/Neuri-AI/PSX/commit/847a08035d08d3d66c0bffd2b7df3743f938f5aa)  
**Read first:** [Master plan](velto-master-execution-plan.md) · [P0 baseline audit](velto-p0-baseline-audit.md) · [Contract index](CONTRACTS_INDEX.md)

> **Meaning of status:** Source-level hypotheses have been checked against the implementation and acceptance tests have been identified. **No tests, pip resolver, native GUI benchmarks, Rust differential runs or CI jobs were executed in this work session.** GitHub connector provided source reads; the execution environment could not resolve `github.com` for a checkout. Do not reinterpret this report as a green CI receipt or close the Architecture Gate from it.

## 1. Verification levels and evidence register

- **SOURCE-CONFIRMED:** exact implementation or manifest line inspected at the PSX source anchor, or per-file GitHub blob from a named related repository.
- **TEST-DEFINED:** behavioral test exists and was read or identified; does **not** mean test passed now.
- **HYPOTHESIS:** plausible failure inferred from control flow, awaiting real test execution.
- **EXECUTED-PASS / EXECUTED-FAIL:** reserved for actual output, linked run, environment and immutable SHA; **none recorded in this report**.
- **NOT-CHECKED:** no reliable evidence; not equivalent to unsupported or failing.

| ID | Target | Finding | Classification | Evidence |
| --- | --- | --- | --- | --- |
| H-PKG-01 | Fresh facade installation | Checked project manifests contain inconsistent package naming/version constraints | SOURCE-CONFIRMED metadata mismatch; resolver outcome NOT-CHECKED | [PSX pyproject](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/pyproject.toml), [Velto pyproject](https://github.com/Neuri-AI/Velto/blob/main/pyproject.toml), [Pydux pyproject](https://github.com/Neuri-AI/Pydux/blob/main/pyproject.toml), [Qyro pyproject](https://github.com/Neuri-AI/qyro/blob/main/pyproject.toml) |
| H-MEM-01 | Faulty effect disposer | Sequential teardown can be interrupted before descendant renderer destruction | HYPOTHESIS supported by source control-flow; no leak reproduced | [Reconciler `_unmount`](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/reconcile.py#L299-L322), [hook cleanup](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/hooks.py#L127-L133) |
| V-CORE-01 | Keyed diff and event cleanup | Keyed nodes are reconciled; stale nodes unmount; slots disconnected on removal | SOURCE-CONFIRMED; TEST-DEFINED | [Reconciler](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/reconcile.py), [core tests](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/tests/test_core.py) |
| V-HOOK-01 | Effect and scheduler | Reverse effect cleanup; dirty-instance coalescing; disposed setter inert | SOURCE-CONFIRMED; TEST-DEFINED | [Hooks](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/hooks.py), [scheduler](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/core/scheduler.py), [tests](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/tests/test_hooks_scheduler.py) |
| V-NAT-01 | Qt | Commit retry capped at three for stale semantic epochs; invalidation clears caches and native observers; normal Qt destroy uses deferred delete | SOURCE-CONFIRMED, native outcomes NOT-CHECKED | [Qt renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/qt/pyqt.py) |
| V-NAT-02 | Tkinter | Invalidation cancels `after` callbacks and unbinds theme/resize; owned widget destroy; borrowed widget not destroyed | SOURCE-CONFIRMED, native outcomes NOT-CHECKED | [Tk renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/tkinter/tkinter.py) |
| V-NAT-03 | Kivy | Clock-event/Window size watchers unbound on invalidation; borrowed widget restores parent/hints | SOURCE-CONFIRMED, native outcomes NOT-CHECKED | [Kivy renderer](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/renderers/kivy/kivy.py) |
| V-CIN-01 | Pure/native layout | Python engine calls `compute_snapshot`; native bridges call Cinnamon math and apply native geometry | SOURCE-CONFIRMED; parity execution NOT-CHECKED | [Engine](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/engine.py), [Qt bridge](https://github.com/Neuri-AI/PSX/blob/847a08035d08d3d66c0bffd2b7df3743f938f5aa/psx/sfle/qt_layout_bridge.py) |

## 2. H-PKG-01 — dependency resolver compatibility

### Source facts

| Manifest | Declared name/version or requirement | Implication |
| --- | --- | --- |
| PSX repo `pyproject.toml` | project `velto-core==0.1.0`; importable package `psx` | Project/install name does not match facade requirement named `psx`. |
| Velto facade `pyproject.toml` | `psx>=1.0.0a1,<2.0.0` | Must be satisfied by an actual published/discoverable distribution named `psx` or explicitly updated. |
| Velto facade `pyproject.toml` | `pydux[psx]>=1.0.0a1,<2.0.0` | Pydux's checked source declares `0.1.0`, which does not by itself satisfy facade range. |
| Velto facade `pyproject.toml` | `qyro-engine>=0.1.0,<0.2.0` | Qyro source currently declares `1.0.0a1`. |
| Pydux `pyproject.toml` | `psx` extra requires `velto-core>=0.1.0,<1.0.0`; `qyro` extra requires `qyro-engine>=1.0.0a1,<2.0.0` | The facade's Qyro requirement and the Pydux Qyro extra are two separate version strategies; confirm which extra is selected. |

**Decision:** keep H-PKG-01 an **OPEN, HIGH-PRIORITY integration blocker** until isolated install/metadata and resolver test is executed. Public index contents cannot be inferred from local pyprojects; a published `psx` distribution or other installed wheel could change actual behavior. No change to dependencies is authorized by this report.

### Exact reproduction sequence (run from checked-out repositories)

1. Pin `git rev-parse HEAD` independently for PSX, Velto, Pydux, Qyro runtime and CLI; copy each `pyproject.toml` with hash.
2. Under Python 3.10 and 3.13, create fresh venvs. Avoid reusing editable installations or developer site-packages.
3. For **repository-local compatibility**, build each wheel with its own build backend; inspect `*.dist-info/METADATA` to record `Name`, `Version`, `Requires-Dist`, `Provides-Extra`.
4. Install the locally built packages together with `python -m pip install --no-index --find-links <local_wheelhouse> velto`; capture full resolver output and installed metadata. Separately try **public-index install** in an Internet-enabled runner; do not conflate these two experiments.
5. Run import checks for `from velto import VeltoContext`, `from velto.ui import psx, component, use_state`, `from velto.state import configure_store, create_slice`, and `from velto.runtime import get_resource`. Then run one actually mounted PySide6 application.
6. Repeat for platform-specific extras and unsupported Python/backend combinations. Record failures as `resolution`, `import`, `native mount`, or `runtime`; never convert the initial metadata mismatch directly to a runtime failure claim.

**Acceptance:** a single approved distribution-name/version dependency graph, reproducible wheel builds, successful clean supported-platform resolves, explicit unsupported markers, and CI proof. Owner must authorize changes to package/version conventions.

## 3. H-MEM-01 — error-path unmount

### Exact control-flow analysis

1. `Reconciler._unmount` sets `instance.disposed = True`, detaches if requested, then iterates `event_slots` calling `slot.dispose()` and `renderer.unbind_event(subscription)`.
2. Next it clears the reference, calls `dispose_hooks(instance)`, recursively unmounts children and finally calls `renderer.destroy(instance.handle)`.
3. `dispose_hooks` calls every effect cleanup in reverse registration order, but has no exception aggregation/finally wrapping each individual cleanup.
4. A raised cleanup/unbind exception **can exit the current call before subsequent children and host handles are destroyed**. Whether a measurable long-lived retention exists depends on references, native ownership and error handling outside these functions. This is not yet a proven leak.

### Required tests

- **M-01:** One component's cleanup throws; assert remaining sibling effects, events, children and host widgets are all disposed **under the approved error policy**, even if the public operation ultimately raises.
- **M-02:** `renderer.unbind_event` throws once; establish whether teardown continues and reports the exception without orphaning subsequent subscriptions.
- **M-03:** Native `destroy` throws; test that other descendants still receive cleanup and that object state accurately reflects partial disposal.
- **M-04:** Repeated keyed insert/remove and host-type replacement; verify zero post-unmount live native widget/subscription growth, not RSS alone.
- **M-05:** Pending scheduler state callback after an instance is unmounted or host UI loop closes; verify no resurrected handles.
- **M-06:** Pydux selector subscriptions are released on unmount; simulate store updates after disposal.
- **M-07:** Qt `deleteLater` needs an event-loop drain; verify QObject deletion rather than merely Python wrapper GC. Test Tk widget destruction and Kivy `Window`/property unbind separately.

**Proposed contract resolution (NOT APPROVED):** best-effort complete teardown with deterministic exception reporting after all cleanup steps, preserving the public error contract; make fatal native corruption distinguishable from ordinary user cleanup exceptions. Do not silently catch everything or reset the `disposed` flag without review.

## 4. Existing tests and runnable audit commands

Source definitions identified: `tests/test_core.py` (identity, events, destroy once), `tests/test_hooks_scheduler.py` (cleanup/order/ref/thread), `tests/test_renderer_adapters.py` (adapter registration and lifecycle), `benchmarks/psx_benchmark.py` (headless performance, tracemalloc-style metrics). These **must be executed** in pinned clones before reporting current pass/fail.

```bash
# Commands are a protocol, NOT an execution log.
git fetch origin develop
git checkout develop
git pull --ff-only
git rev-parse HEAD
git ls-files > /tmp/psx-tracked-files.txt
python -m pip install -e ".[dev]"
python -m pytest tests/test_core.py tests/test_hooks_scheduler.py tests/test_renderer_adapters.py -q
python -m pytest tests/ -q
python benchmarks/psx_benchmark.py --help
```

Discover backend-specific test filenames using `git ls-files tests`; do not invent nonexistent filenames or silently substitute headless runs for native certification. Capture OS, Python, Qt/Tk/Kivy versions, graphics environment, command exit status, full logs, CI links, native object-count deltas and baseline SHA. CI logs linked in historical F2/F3/F4 ledgers are **historical evidence**, not runs of the latest P0 state.

## 5. Verification ledger to be filled by an executing agent

| Test gate | Current | Required closure artifact |
| --- | --- | --- |
| PKG-1 local-wheels resolver | NOT RUN | Wheel metadata, command, exit, exact dependency graph, SHA |
| PKG-2 published-package resolver | NOT RUN | Public-index resolution and package provenance |
| MEM-1 cleanup fault injection | NOT RUN | Reproducible pytest, observed exception and post-disposal object counts |
| MEM-2 Qt/Tk/Kivy native retention | NOT RUN | Platform-specific widget/subscription counts with event-loop drain |
| CORE-1 all PSX tests | NOT RUN | Versioned pytest report and failing/skipped list |
| CIN-1 Rust/Python differential and geometry | NOT RUN | Same-commit CI/local source and logs |
| CI-1 current native/CI matrix | NOT RUN | Workflow URLs, conclusions, matching SHA |
| FACADE-1 imported and mounted app | NOT RUN | Fresh-install execution logs |

## 6. Handoff and escalation

- **Do not edit production code in P0.** Faults become contract decisions/implementation tickets after Architecture Gate.
- **Escalate immediately:** inconsistent distribution namespaces, ambiguous ownership on cleanup exception, or modified public component semantics.
- The next agent must add actual evidence to this report **without changing the meaning of historical statuses**.
- After verification and [contract inventory](CONTRACTS_INDEX.md), draft only the normative **delta** contracts that are not already frozen in existing project specifications.
- **Architecture Gate = BLOCKED** while PKG-1, MEM-1 and the core/backend evidence requirements are unexecuted.

## 7. Offline PEP 440 specifier intersection check (2026-10-18)

An **isolated Python `packaging.specifiers.SpecifierSet` check was actually executed** against the literal versions/ranges extracted from the inspected source manifests. This is a numeric version-compatibility check **only**, not a pip installation or an assertion about published packages.

| Source-version / facade declared requirement | Observed result |
| --- | --- |
| PSX source version `0.1.0` vs facade `psx>=1.0.0a1,<2.0.0` | **False** |
| Pydux source version `0.1.0` vs facade `pydux>=1.0.0a1,<2.0.0` | **False** |
| Qyro source version `1.0.0a1` vs facade `qyro-engine>=0.1.0,<0.2.0` | **False** |

Command executed:

```python
from packaging.specifiers import SpecifierSet

checks = [
    ("0.1.0", ">=1.0.0a1,<2.0.0"),
    ("0.1.0", ">=1.0.0a1,<2.0.0"),
    ("1.0.0a1", ">=0.1.0,<0.2.0"),
]
for version, specifier in checks:
    print(version in SpecifierSet(specifier))
# False
# False
# False
```

**Scope:** this validates arithmetic incompatibility for exactly these three source-version/range pairs and strengthens **H-PKG-01**. It does not establish available wheel names, package index contents, environment markers, extras resolution, actual runtime compatibility, or that a resolver necessarily fails against a particular index. A clean-wheel resolver remains mandatory and **NOT RUN**.

## 8. P0.7 — Isolated fault-path execution and current manifests (2026-10-18)

**Execution provenance:** A local Python 3 isolated harness was run in the assistant's container, containing **the verbatim `dispose_hooks`, `Reconciler._unmount`, and `Reconciler.unmount` function bodies** as fetched from current `develop` source, with a tiny stand-in `MountedInstance`, `_EffectSlot` and recording fake renderer. **This was not a Git checkout, not the committed project test suite, not GitHub Actions, and not a native backend run.** It does provide actual deterministic fault-path output from those copied method bodies.

Immutable source blob anchors: `psx/core/hooks.py` `b379cf6e1144df23f6cff2d9e9cb0a8a0eb85221`; `psx/core/reconcile.py` `914ac924b2011f20f670b7dd81658a126a3a490c`.

### Observed fault-injection output

```text
normal: {'fault': False, 'exception': None,
         'destroyed': ['child', 'parent'],
         'root_cleared': True, 'child_disposed': True,
         'hooks_cleared': True}
injected: {'fault': True, 'exception': 'fault',
           'destroyed': [], 'root_cleared': False,
           'child_disposed': False, 'hooks_cleared': False}
```

**H-MEM-01 classification update:** `ISOLATED-HARNESS REPRODUCED`. A throwing effect disposer aborts the existing teardown algorithm before descendant or parent native destruction and before `Reconciler.root = None`. This strengthens the initial code-level hypothesis. **It is still not evidence of a permanent memory leak in a running Qt/Tk/Kivy app**, because native ownership, exception handling above reconciliation and collection roots are not measured here. The committed in-repository regression probe `tests/test_p0_teardown_diagnostics.py` has **not** been executed in a project checkout; it intentionally records the desired cleanup behavior as `expectedFailure`.

### Actual metadata arithmetic

The `packaging.specifiers.SpecifierSet(..., prereleases=True).contains(version)` comparison was run locally after fetching manifests. All three source version / facade declared range pairings evaluated `False`. Using `prereleases=True` did **not** repair these incompatible source versions.

| Distribution source / requirement | Source metadata blob | Is compatible? |
| --- | --- | --- |
| `velto-core==0.1.0` (PSX source) vs facade requirement named `psx>=1.0.0a1,<2.0.0` | PSX `pyproject.toml` `c06e405a45cd8e95cfec2b55690455b6962f4a7c7` | **NO** — mismatch includes the distribution **name**, not merely its version |
| `pydux==0.1.0` vs facade `pydux[psx]>=1.0.0a1,<2.0.0` | Pydux `pyproject.toml` `e3c03b6dd79f7776a88b0fe46c1f7f137340fae5` | **NO** at that source version |
| `qyro-engine==1.0.0a1` vs facade `qyro-engine>=0.1.0,<0.2.0` | Qyro `pyproject.toml` `b603f2097559205de1835dbee696e0105d757671` | **NO** at that source version |

Facade `pyproject.toml` blob: `0594252ce6b0d333ad16aee4342c27cb7673111f`. CLI `pyproject.toml` blob `8a65d833ed065532c0cd01b4359dff927f5b352e` requires `qyro-engine>=1.0.0a1,<2.0.0`, **also divergent from the facade**.

**H-PKG-01 classification update:** `SOURCE-METADATA CONFLICT VERIFIED + LOCAL SPECIFIER CHECK EXECUTED`; wheel/build/installation resolver and current public index availability remain **NOT RUN**.

### Environment constraint and next executed gates

Direct `git ls-remote https://github.com/Neuri-AI/PSX.git refs/heads/develop` failed in the container with `Could not resolve host: github.com`. The linked GitHub connector supports repository file reads and writes but no workflow dispatch/full checkout. Therefore do not claim project tests or clean-wheel installs. Next execution must use a GitHub Actions workflow runner or developer machine with network/installed source: check actual `tests/test_p0_teardown_diagnostics.py`, packages and native backends at a **single immutable source SHA**, then attach stdout, CI run URL and artifact receipts.
