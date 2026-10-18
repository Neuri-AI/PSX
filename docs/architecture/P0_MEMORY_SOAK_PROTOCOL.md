# P0.9 C07 — Long-running Native Memory Soak Protocol

**Date:** 2026-10-18  
**State:** INSTRUMENTATION COMMITTED, NO VERIFIED SOAK RESULTS  
**Scope:** PySide6, Tkinter and Kivy; distinct native process for each backend  
**Branch:** `Neuri-AI/PSX:develop`

## Purpose

Measure whether mounted PSX UI elements, event subscriptions and renderer objects accumulate as users repeatedly update and remove widgets. This is prerequisite evidence for Web-like / CSS-like and later hot reloading, **not** a claim of perfectly bounded process RSS or a substitute for capability-specific testing.

## Implementation

- [`scripts/p0_memory_soak.py`](../../scripts/p0_memory_soak.py): command-line benchmark with backend selection, cycle count, sample interval and JSON output.
- [`.github/workflows/p0-memory-soak.yml`](../../.github/workflows/p0-memory-soak.yml): independent GitHub Actions matrix running Qt, Tk and Kivy in separate Linux/Xvfb jobs on Python 3.13. Pushes that change the benchmark and manual workflow dispatch trigger runs; manual dispatch supports **1,000, 5,000 and 10,000** cycles.
- Each cycle **mounts Button, reconciles a changed label and event callback, and unmounts**. Kivy uses the Cinnamon-required explicit Flex root. The benchmark does not use a simulation renderer.
- At checkpoints (default every 250 cycles), process native pending events, run Python GC, record process RSS via `psutil`, `tracemalloc` current/peak allocation, process-wide live `MountedInstance` count, weakly tracked widget wrappers and active event slot counts. The probe discards dead weakref objects rather than letting its own measurement store grow unbounded.
- JSON artifacts are uploaded from CI for each backend and retained for 30 days. Compare **series**, not just the final row.

## Interpretation and caveats

A memory allocator may retain freed arenas: **RSS growth alone is not proof of a leak**, while a flat RSS does not prove that Python/native callbacks are fully released. `tracemalloc` measures tracked Python allocations, not every native toolkit allocation. Python objects may also be held temporarily by Kivy Clock, Qt pending deferred-deletion, or toolkit caches. These require explicit settling windows and follow-up investigation where persistent.

The instrumented checker exits nonzero for a *diagnostic* retention signal (e.g. growing live mounted instances beyond the first settled checkpoint, more than 10 retained widget wrappers, or excessive active event slots). These are provisional thresholds for detecting anomalies, **not a universally calibrated leak budget**. False positives should be investigated and only waived with a reproducible trace and owner-reviewed baseline. A green run means the configured probe did not detect those anomalies on that specific runner; it does not certify all memory usage, image churn, async tasks or other platforms.

## Runbook

```bash
python -m pip install psutil
QT_QPA_PLATFORM=offscreen python scripts/p0_memory_soak.py \
  --backend pyside6 --cycles 1000 --interval 250 --json-out artifacts/pyside6.json
xvfb-run -a python scripts/p0_memory_soak.py \
  --backend tkinter --cycles 5000 --interval 250 --json-out artifacts/tkinter.json
xvfb-run -a python scripts/p0_memory_soak.py \
  --backend kivy --cycles 10000 --interval 250 --json-out artifacts/kivy.json
```

For full certification, run **each** backend at all three cycle depths (not just one cell per backend), capture exact SHA / Python / OS / toolkit versions, CI logs, artifact hashes, GC and callback counts, RSS curves and per-segment time. Run additional workloads (image churn, nested layout resizing, keyed lists, subscriptions, asynchronous tasks) after this baseline suite.

## Current acceptance ledger

| Check | Status |
| --- | --- |
| All 3 backend soak scripts committed | YES |
| 1k matrix CI configured | YES, result **UNVERIFIED** |
| 5k manual CI run | NOT VERIFIED |
| 10k manual CI run | NOT VERIFIED |
| Native widget and event-retention series | PENDING ARTIFACTS |
| Memory regression baseline/owner signoff | PENDING |
| C05 full clean ecosystem install | PENDING |

**Do not close C07 long-running memory certification or P0→P1 Architecture Gate solely because this protocol and job now exist.**


## Initial 1,000-cycle CI #3 and weak-proxy collector fix (2026-10-18)

User-supplied workflow screenshot/log for the `P0 memory soak` push run #3, commit `140ee65`, establishes **PySide6 Python 3.13 SUCCESS** and **Tkinter Python 3.13 SUCCESS** for the configured 1,000-cycle job, while **Kivy Python 3.13 FAILED**. The Kivy failure was **instrumentation**, not a verified retained-object leak:

```text
scripts/p0_memory_soak.py:85
if isinstance(obj, MountedInstance):
ReferenceError: weakly-referenced object no longer exists
```

At a GC sample, Kivy had an expired `weakref.proxy` among `gc.get_objects()`; `isinstance` dereferenced it and raised `ReferenceError`. This cannot establish that any widget leaked.

**Committed repair:** [`mounted_instance_snapshot`](../../scripts/p0_memory_soak.py) selects **only** objects whose concrete type is `MountedInstance` using `type(obj) is MountedInstance`, avoiding proxy dereferencing. This limits counts to the intended slotted instance class; subclasses are not included. [Two regression tests](../../tests/test_p0_memory_soak_probes.py) exercise an expired weak proxy and a foreign widget/proxy. The [CI workflow](../../.github/workflows/p0-memory-soak.yml) runs these tests before the native soak.

**Current verification:** fix, regression tests and CI configuration committed and source-verified. **No post-fix green Kivy CI run or artifact analyzed yet.** PySide6/Tk 1,000-cycle job outcomes were green by screenshot, but raw RSS/heap/retention series have not yet been inspected. The C07 soak gate remains open; 5,000/10,000-cycle runs and full C05 install remain outstanding.


## P0.9 post-proxy-fix measurement and CI reporting (2026-10-18)

The weak-proxy `ReferenceError` instrumentation patch is committed to `develop`, but a post-fix workflow run conclusion could **not** be retrieved via the available GitHub integration. GitHub legacy commit status and PR-filtered workflow listings were empty for the recent push commits; this is **not evidence of a failed or missing GitHub Actions run**. Live GitHub Actions pages and direct repository checkout were not accessible from the execution container. **Kivy 1,000-cycle certification remains UNVERIFIED** until a new run receipt is supplied.

Added [`scripts/p0_memory_soak_report.py`](../../scripts/p0_memory_soak_report.py) with three [report tests](../../tests/test_p0_memory_soak_report.py). The analyzer consumes the raw per-backend JSON and reports first-to-last and second-half deltas for RSS, Python allocations, live mounted instances, native widget wrappers and active event slots. It deliberately refuses to infer a trend from fewer than two settled samples and does not turn RSS growth alone into a leak verdict. The [CI workflow](../../.github/workflows/p0-memory-soak.yml) now runs both instrumentation/test-report suites, writes a per-job GitHub Step Summary and uploads JSON plus Markdown summary files whenever a raw artifact exists.

**Next gate:** inspect the next 1,000-cycle GitHub Actions run for all three backends, download the artifacts, review the measured series, then execute the 5,000/10,000-cycle matrix only if the baseline supports it. No P0→P1 approval is implied by committing analysis tooling.


## P0.9 actual 1,000-cycle artifacts — owner evidence (2026-10-18)

The owner supplied a screenshot of successful [P0 memory soak run #8](https://github.com/Neuri-AI/PSX/actions/workflows/p0-memory-soak.yml), commit prefix `1d6f1d4`, **3/3 green** (PySide6, Tkinter, Kivy), together with all three backend raw `*-memory.json` files and their generated summaries. Each series contains four samples at 250, 500, 750 and 1,000 cycles from Linux / Python 3.13.16. **These are measured outputs, not inferred values.**

| Backend | RSS at 250 | RSS at 1,000 | RSS delta 250→1,000 | tracemalloc current delta | Live instances / widget wrappers / event slots at 1,000 |
| --- | ---: | ---: | ---: | ---: | --- |
| PySide6 | 94,089,216 B | 96,018,432 B | +1,929,216 B | +2,215,761 B | 0 / 0 / 0 |
| Tkinter | 40,210,432 B | 40,210,432 B | 0 B | +999,276 B | 0 / 0 / 0 |
| Kivy | 164,962,304 B | 170,848,256 B | +5,885,952 B | +3,678,821 B | 0 / 0 / 0 |

**Second-half comparison (750→1,000):** PySide6 RSS 0 B and tracemalloc +537 B; Tkinter RSS 0 B and tracemalloc +488 B; Kivy RSS +1,691,648 B and tracemalloc +978,488 B. Kivy also grows over the 500→750 segment. **This continued increase warrants a longer trend investigation before accepting C07 as performance-stable.** None of these results independently proves a leak; Kivy/Cinnamon/Kivy-native caches or allocator behavior can create nonzero tracked memory without keeping retired PSX widgets alive. A fresh-process A/B control and 5,000-cycle Kivy run can help distinguish warmup from persistent growth.

**Limitations:** zero retained objects means zero within the exact probe's observed `MountedInstance` concrete type, weakly-referenced widget wrappers, and recorded live event-slot scopes after event draining and GC. It does not count all native allocations, Kivy `Clock` observers, Rust buffers, GPU resources, or arbitrary Python global caches. The first sample is at cycle 250, **not** pre-mount baseline. Process RSS includes toolkit and SDL/OpenGL overhead and must not be called 'Velto-only RAM.' Reported success represents the script's provisional thresholds, not zero growth in RSS or `tracemalloc`.

**Decision:** 1,000-cycle smoke **VERIFIED GREEN** for three Linux backends. **Long-duration C07 certification remains OPEN.** Suggested next work: Kivy 5,000 cycles with raw artifacts; PySide6 and Tk 5,000 for matched-baseline comparison; 10,000 cycles and a warmed steady-state repeat if growth persists. Record comparable hardware, SHA, Python toolkit versions, slope after warmup, and possible owning cache roots before deciding on code changes.


## Actual 5,000-cycle artifacts — owner uploads (2026-10-18)

The owner supplied **three GitHub Actions ZIP artifacts** for run identifier `39144005023`, each containing the raw `*-memory.json`, summary JSON and Markdown. The following statistics were calculated by inspecting those actual raw files. Every backend has 20 samples at 250-cycle intervals, Linux / Python 3.13.16, and reports 5,000 completed cycles.

| Backend | RSS at 250 cycles | RSS at 5,000 cycles | RSS delta 250→5,000 | tracemalloc current delta 250→5,000 | Tail RSS delta 2,750→5,000 | Retained instance / widget / slots |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| PySide6 | 93,855,744 B | 95,805,440 B | +1,949,696 B | +2,218,958 B | +20,480 B | 0 / 0 / 0 |
| Tkinter | 40,050,688 B | 40,050,688 B | 0 B | +1,006,057 B | 0 B | 0 / 0 / 0 |
| Kivy | 164,429,824 B | 213,856,256 B | **+49,426,432 B** | **+19,331,078 B** | **+29,642,752 B** | 0 / 0 / 0 |

**Technical interpretation:**

1. Tk and PySide6 have nearly flat RSS and traced heap after initial warmup, with zero tracked stale instances, weak widget wrappers and active event slots.
2. Kivy continues to grow in RSS and `tracemalloc` throughout the 20 measured checkpoints; it does **not** reach a convincing steady state by 5,000 cycles. The Python-traced heap gain is ~18.44 MiB over 4,750 cycles (~4.1 KiB/cycle), separate from the total RSS gain (~47.14 MiB). Do not call the benchmark's `no_sustained_growth_detected_in_sample` string a measured assertion that Kivy memory is flat: this status currently checks specific retained instance/widget/event counts, not positive heap/RSS slopes.
3. Kivy's zero tracked retained native widget wrappers is evidence against one specific failure mode, but does not rule out Kivy Clock/Cython native resources, binding registries, caches or allocation churn. **No ownership attribution or confirmed leak cause yet.**
4. The three ZIP artifacts establish successful completion and available samples; they do not alone reveal full GitHub Actions job conclusion or every warning/skip. We have not claimed an inspected 5,000-cycle workflow screenshot.

**Next investigation:** [Kivy allocation tracer](../../scripts/p0_kivy_allocation_trace.py) and [dedicated CI workflow](../../.github/workflows/p0-kivy-allocation-trace.yml) were committed to profile Python allocation sites, comparing cycle 500 vs cycle 5,000 after native pending-event flush and GC. Inspect the tracebacks and repeat under a warmed control before changing production Kivy/Cinnamon code. The tracer's result is **not yet executed or available**.

**C07 gate remains open** pending explanation/mitigation of Kivy's positive slopes, corroborating 10,000-cycle or warmed stable-state evidence, and final owner acceptance. C05 full clean ecosystem installation is independent and still pending.
