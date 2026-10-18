# P0.9 C07 — Kivy direct vs Velto heap ownership results

**Date:** 2026-10-18  
**Status:** both A/B artifacts reviewed; retaining owner still unproven  
**Source:** owner-supplied artifacts `p0-kivy-heap-native-39145926751.zip` and `p0-kivy-heap-velto-39145926751.zip`, each containing a JSON report of 5,000 completed cycles.

## Observed samples

Each run samples cycles **500 / 2,500 / 5,000** after the profiler drains Kivy Clock events and runs Python GC. Jobs are Linux/Python 3.13 in separate processes.

| Metric | Kivy native @500 | Kivy native @5,000 | Velto+Kivy @500 | Velto+Kivy @5,000 |
| --- | ---: | ---: | ---: | ---: |
| RSS (bytes) | 157,724,672 | 173,342,720 | 169,631,744 | 219,545,600 |
| `tracemalloc` current (bytes) | 541,432 | 5,811,430 | 2,742,999 | 21,110,151 |
| `kivy.weakproxy.WeakProxy` count | 500 | 5,000 | 500 | 5,000 |
| `builtins.dict` count | 3,514 | 8,338 | 7,048 | 34,306 |
| `builtins.list` count | 3,699 | 8,322 | 6,539 | 33,596 |
| `builtins.tuple` count | 3,061 | 3,377 | 4,497 | 4,813 |

**Measured 500→5,000 deltas**:

| Metric | Direct Kivy | Velto + Kivy |
| --- | ---: | ---: |
| RSS | +15,618,048 B (14.89 MiB) | +49,913,856 B (47.60 MiB) |
| Traced Python current | +5,269,998 B (5.03 MiB) | +18,367,152 B (17.52 MiB) |
| WeakProxy live-count delta | +4,500 | +4,500 |
| `dict` live-count delta | +4,824 | +27,258 |
| `list` live-count delta | +4,623 | +27,057 |

The exact one-per-cycle surviving `kivy.weakproxy.WeakProxy` pattern occurs in **both** modes, so the previous suspicion of a Velto-only Kivy proxy leak is not supported. The **extra growth in Velto remains significant but not causally attributed**. The tests are not semantically identical: the native control does not run Cinnamon native layout or PSX reconciliation and uses different callback/build steps. Per-job starting RSS differs.

The collected `gc.get_referrers` samples in the reports capture the first few alphabetically sorted `psx.*`/`kivy.*` types (e.g. `ClockEvent`, `EventObservers`), **not** the growing `kivy.weakproxy.WeakProxy` or generic list/dict types. Therefore the current referrer results **cannot identify the owner of the +4,500 proxy population or the extra +22,434 dictionaries in Velto**.

A second measurement caveat: the profiler records a GC histogram and only then samples RSS, while snapshots and temporary arrays can affect short-term allocations. Neither direct mode nor Velto mode is an empty control. Future attribution should carefully rule out measurement-induced retention and model-related caches.

## Next narrow investigation

1. **Prioritize exact `kivy.weakproxy.WeakProxy` referrers** at cycle 500 and 5,000, along with concrete list/dict owners. Capture bounded referrer *type histograms* without serializing instances, object reprs or unbounded reference trees.
2. Distinguish Kivy's proxy churn from PSX/Cinnamon-specific retained containers: take independent snapshots in a fresh process and inspect Kivy global registries/Canvas/Clock and Cinnamon caches.
3. Add a controls matrix to isolate **direct Kivy**, **PSX Kivy without Cinnamon constraints**, and **PSX Kivy with Cinnamon** with comparable widget creation and event cycles. The middle arm is a proposal; verify renderer compatibility and lifecycle before treating it as a supported CI run.
4. Investigate only verified retaining paths; implement a targeted fix with regression tests if PSX owns leaked references. Retest 5,000 then 10,000 cycles.

**Gate:** C07 long-running Kivy memory certification remains **OPEN**; no production fix or global P0→P1 approval is justified by this evidence alone.
