# P0 Contract Review — Batch 2: Safety, Ownership and Packaging

**Date:** 2026-10-18 · **Status:** SOURCE REVIEW COMPLETE; EXECUTABLE GATES AND OWNER SIGN-OFF PENDING  
**Decisions:** AD-05, AD-07, AD-09 · **Contracts affected:** C04, C05, C06, C07, C08, C09, C11, C12  
**No production code changed.**

## 1. Evidence

- [Reconciler teardown](../../psx/core/reconcile.py): `_unmount` marks disposed, detaches, iterates event disposers/unbinds, clears refs, calls `dispose_hooks`, recurses into children and destroys its native handle.
- [Hooks](../../psx/core/hooks.py): `dispose_hooks` invokes cleanups sequentially in reversed order with no exception aggregation.
- [Scheduler](../../psx/core/scheduler.py): retains dirty instance/effect callbacks until flushed; closure during a pending UI callback needs tests.
- [Renderer protocol](../../psx/renderers/protocol.py): basic create/update/insert/move/remove/events/destroy/schedule/run.
- [Qt](../../psx/renderers/qt/pyqt.py), [Tk](../../psx/renderers/tkinter/tkinter.py), [Kivy](../../psx/renderers/kivy/kivy.py): implement separate native geometry commit/invalidation and native ownership strategies.
- [P0 verification](P0_VERIFICATION_REPORT.md): H-MEM-01 fault-path risk and H-PKG-01 packaging constraints.
- [Velto](https://github.com/Neuri-AI/Velto/blob/main/pyproject.toml), [PSX](../../pyproject.toml), [Pydux](https://github.com/Neuri-AI/Pydux/blob/main/pyproject.toml), [Qyro](https://github.com/Neuri-AI/qyro/blob/main/pyproject.toml): declared package versions/ranges differ.

**Actually executed in isolated Python environment:** `packaging.specifiers.SpecifierSet` with `prereleases=True` returned `False` for all three source-version versus facade-required ranges: PSX `0.1.0` vs `>=1.0.0a1,<2.0.0`, Pydux `0.1.0` vs same, Qyro `1.0.0a1` vs `>=0.1.0,<0.2.0`. This is a narrow PEP 440 check, **not** a pip resolver run.

## 2. AD-05 — Disposal on callback failures

**Static review: COMPLETE; implementation authorization: NO.**

A throwing disposer can unwind `_unmount` before later children/native handles are destroyed. Mark this as `SOURCE-INDICATED FAILURE PATH`; do not claim measured leaks.

**Recommended policy (PROPOSED):** attempt all safely independent cleanup actions (native unsubscribe, refs, effects, children, handle destruction) while retaining deterministic exception ordering and surfacing any failures after cleanup. Adopt a precise policy for fatal toolkit errors rather than `except Exception: pass`.

**Open:** whether to use `ExceptionGroup` (Python 3.10 target makes that non-uniform), a compatible custom exception aggregator, or first-exception-plus-notes; whether to distinguish user callback error from renderer corruption. Review thread-specific teardown guarantees. Do not select on behalf of owner.

**Acceptance evidence:** pytest fault injection for hook disposer, native event unbind and child destroy; confirm all sibling native handles released, once only, and exception semantics. Then native Qt `deleteLater()` + event-loop drain, Tk actual destruction, Kivy parent/hint restoration and stale watcher counts.

## 3. AD-07 — Distribution compatibility and facade dependency graph

**Static review: COMPLETE; clean-install validation: BLOCKED/NOT RUN.**

Source manifest names and ranges are internally divergent. The offline PEP 440 comparison demonstrates that **these exact source versions do not satisfy the facade's exact declared ranges**. It does not rule out an entirely different published set of compatible wheels. No `pip install velto` success/failure is asserted.

**Recommended policy (PROPOSED):** owner chooses one coordinated distribution namespace/release train; publish a version table for `velto`, `velto-core` or `psx`, `pydux`, `qyro-engine`, and CLI. Keep existing Python import paths usable during any metadata migration.

**Blocked decisions:** choose package names, target versions, pre-release policy, GitHub/PyPI source-of-truth and supported Python extras. No automated version bump until fresh-wheel METADATA and dependency resolver logs exist.

**Acceptance evidence:** reproducible isolated wheels, `pip install --no-index --find-links` wheelhouse test, public-index dry-run, import smoke and real mounted PySide6 app. Test valid and explicitly unsupported Python/backend cells.

## 4. AD-09 — Measurement, layout commit and invalidation interface

**Static review: COMPLETE; protocol change approval: NO.**

Existing base `Renderer` protocol deliberately lacks geometry/measurement entry points, whereas real Qt/Tk/Kivy implementations already provide layout commit/invalidation. A breaking required-method addition would impact user-registered adapters and nonnative/headless paths.

**Recommended policy (PROPOSED):** versioned optional capability protocol. Preserve existing public adapter interface; declare which capabilities are required when Cinnamon owns geometry, how to provide intrinsic hints, errors for unsupported native cases, and how stale measurement epochs are discarded.

**Acceptance evidence:** fake adapter without optional port remains functional in its existing scope; three native renderers implement/advertise supported port; measurements run on UI thread; invalid negative Qt hint vs intentional zero; invalidation does not cause resize recursion; Kivy missing intrinsic ports fail closed.

**Open:** capability registration/version and compatibility migration path, whether measurement is a renderer service or adapter callback, and exact name/typing of error results. Do not invent interfaces as implemented.

## 5. Batch 2 decision ledger

| Decision | Static technical review | Evidence gate | Owner selection |
| --- | --- | --- | --- |
| AD-05 | Reviewed; recommendation recorded | H-MEM-01 fault injection + native retention **NOT RUN** | PENDING |
| AD-07 | Reviewed; offline range check actually executed | Fresh pip/wheel resolver and facade app **NOT RUN** | PENDING |
| AD-09 | Reviewed; recommendation recorded | Native bridge/capability test matrix **NOT RUN** | PENDING |

**Outcome:** technical review does not cure blockers. See [Architecture Gate](ARCHITECTURE_APPROVAL.md). No production implementation authorized.
