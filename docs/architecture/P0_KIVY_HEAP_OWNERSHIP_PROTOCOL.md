# P0.9 C07 — Kivy heap ownership & direct-toolkit comparison

**Date:** 2026-10-18  
**Status:** Instrumentation committed; CI measurements not yet verified.  
**Branch:** `Neuri-AI/PSX:develop`

## Goal

Investigate the measured Kivy +~71.79 MiB process RSS and +~16.79 MiB Python-traced allocations between cycle 500 and 5,000 in the prior allocation trace. The previous `tracemalloc` results **identify allocation call paths**, not who owns references that survive native widget teardown.

## Diagnostic implementation

- [`scripts/p0_kivy_heap_ownership.py`](../../scripts/p0_kivy_heap_ownership.py) runs either `--mode velto` or `--mode native` and emits JSON with settled samples at 10%, 50% and 100% of the specified cycles.
- [`.github/workflows/p0-kivy-heap-ownership.yml`](../../.github/workflows/p0-kivy-heap-ownership.yml) runs independent Python 3.13/Linux/Xvfb jobs for each mode, 5,000 cycles by default, with a 50-minute job cap and uploaded evidence artifacts.
- In **velto** mode, the existing `make_backend('kivy')` driver uses real `Reconciler`, `KivyRenderer`, `Flex(Button)`, Cinnamon layout, event callbacks, native updates, unmount, Kivy Clock drain and GC.
- In **native** mode, Kivy alone creates a `BoxLayout` and `Button`, registers an `on_release` callback, updates the label, explicitly unbinds, removes the layout and drains Clock/GC.
- At each checkpoint, the tool records RSS, `tracemalloc` current/peak memory, exact-type histograms from `gc.get_objects()`, and bounded **type-only** `gc.get_referrers()` samples for `psx.*` and `kivy.*` objects at the last checkpoint.
- Exact-type classification is used throughout to avoid the previously observed `ReferenceError` from dereferencing dead Kivy `weakref.proxy` objects.
- [`tests/test_p0_kivy_heap_ownership.py`](../../tests/test_p0_kivy_heap_ownership.py) covers expired proxies and non-leaking report shapes.

## Evidence limitations

**This is a directional A/B control, not workload equivalence.** Native mode omits PSX reconciliation, Cinnamon and the actual native SFLE measurement workload, so a difference proves only that the workload stacks differ. Comparable growth in both modes would support investigating Kivy infrastructure; growth only with Velto would prioritize PSX integration.

The GC inventory cannot enumerate all underlying Cython/native allocations, and `gc.get_referrers` also sees profiler-owned temporary lists/dictionaries. Class histogram changes identify which managed types survive, but **do not themselves identify a unique retaining owner**. Referrer type samples are bounded, do not show object identities or memory addresses, and cannot distinguish all indirect ownership.

Run the modes in separate fresh processes to avoid shared global Kivy registry state. Compare *post-warmup deltas*, not absolute RSS, across jobs. Each job has its own Xvfb and Kivy SDL process state. The script must not be promoted to a failing memory-regression gate based on arbitrary RSS thresholds.

## Runbook

```bash
xvfb-run -a python scripts/p0_kivy_heap_ownership.py \
  --mode native --cycles 5000 --json-out artifacts/kivy-native-ownership.json
xvfb-run -a python scripts/p0_kivy_heap_ownership.py \
  --mode velto --cycles 5000 --json-out artifacts/kivy-velto-ownership.json
```

Inspect the `samples[].tracked_type_histogram` changes, final `referrer_samples`, RSS and Python allocation deltas. If one concrete type is steadily growing, follow its ownership path in a focused reproduction before editing production renderer or Cinnamon code.

## Certification status

| Requirement | Status |
| --- | --- |
| 1,000-cycle native matrix | Verified green with owner-uploaded artifacts |
| 5,000-cycle native matrix | All three raw series reviewed; PySide6/Tk plateau, Kivy rising |
| Kivy allocation traceback profiling | Reviewed; dominant paths in PSX mount → Kivy adapter |
| Heap / reference ownership profiles | **Committed, CI result pending** |
| Direct Kivy A/B control | **Committed, CI result pending** |
| Targeted memory fix or justified bounded upstream cache | Pending attribution |
| Final 5,000- and 10,000-cycle post-fix or approved control | Pending |
| C07 long-run certification | **OPEN** |
| C05 clean release ecosystem wheel installation | **OPEN** |

**Do not certify C07 or the global P0→P1 Architecture Gate on the basis of profiler publication alone.**


## Follow-up implementation: three-arm isolation (2026-10-18)

The profiler now runs **three** independently isolated arms: `native` (direct BoxLayout/Button), `psx_no_cinnamon` (PSX Reconciler + KivyRenderer without SFLE constraints, using the supported `Fragment(Button)` root), and `velto` (PSX Reconciler + KivyRenderer with Cinnamon SFLE constraints and `Flex(Button)`). The CI matrix has three jobs and defaults to 5,000 cycles. The profiler also captures bounded `gc.get_referrers()` **type summaries** for the specifically growing `kivy.weakproxy.WeakProxy`, `builtins.dict` and `builtins.list` types at each checkpoint. It does not traverse reference chains or identify individual owning instances. Temporary GC inventory and profiler-owned references can appear in these counts.

**Important comparability caveat:** `Fragment` and `Flex` are different layout constructs; this comparison isolates a supported no-SFLE renderer configuration but does not hold layout semantics constant. All results require a measured CI receipt before conclusions. The three-arm CI has been committed; **no run results yet verified**. Production renderer/Cinnamon unchanged.
