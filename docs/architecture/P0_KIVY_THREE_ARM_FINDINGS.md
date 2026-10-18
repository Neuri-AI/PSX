# P0.9 C07 — Three-arm Kivy heap findings (5,000 cycles)

**Date:** 2026-10-18  
**Run:** `39146917385`  
**Status:** all three owner-supplied JSON artifacts analyzed; retaining owner not yet established.

## Input evidence

Owner provided three uploaded GitHub Actions artifact ZIPs for this run:
- `p0-kivy-heap-native-39146917385.zip` → `kivy-native-ownership.json`
- `p0-kivy-heap-psx_no_cinnamon-39146917385.zip` → `kivy-psx_no_cinnamon-ownership.json`
- `p0-kivy-heap-velto-39146917385.zip` → `kivy-velto-ownership.json`

Each completed 5,000 native cycles and reported post-GC snapshots at 500, 2,500, 5,000.

## Measurements

| Metric | Native Kivy | PSX without Cinnamon | PSX with Cinnamon |
| --- | ---: | ---: | ---: |
| RSS @500 (B) | 157,233,152 | 161,939,456 | 166,985,728 |
| RSS @2500 (B) | 166,928,384 | 172,130,304 | 202,010,624 |
| RSS @5000 (B) | 172,892,160 | 177,659,904 | 219,820,032 |
| RSS delta 500→5000 (B) | **15,659,008** | **15,720,448** | **52,834,304** |
| Traced Python current @500 (B) | 541,512 | 561,059 | 2,742,936 |
| Traced Python current @5000 (B) | 5,820,850 | 5,838,873 | 21,119,631 |
| Traced Python delta (B) | **5,279,338** | **5,277,814** | **18,376,695** |
| `kivy.weakproxy.WeakProxy` @500 → @5000 | 500→5000 | 500→5000 | 500→5000 |
| `builtins.dict` @500 → @5000 | 3514→8356 | 4493→9335 | 7048→34324 |
| `builtins.list` @500 → @5000 | 3699→8324 | 4049→8674 | 6539→33598 |

The common per-cycle proxy retention pattern appears independently in **all three** configurations. Direct Kivy and PSX without Cinnamon have nearly identical **post-warmup deltas** despite different starting heaps. With Cinnamon enabled, RSS and Python-traced memory rise substantially more, accompanied by **22,434 extra dicts and 22,434 extra lists** beyond the other two scenarios' increases.

This isolates the additional growth to **work enabled by the Cinnamon/SFLE integration path**, not necessarily the Cinnamon mathematical engine itself. Geometry commits, measurement, native adapter state, upstream Kivy bindings, or global caches are still possible origins. The `velto` arm uses a `Flex` root; `psx_no_cinnamon` uses a `Fragment` root because Kivy explicitly refuses Flex without SFLE. These are **not layout-equivalent controls**. No proof of a specific leaked object or ownership chain has yet been established.

## Referrer samples

The diagnostic's `growing_type_referrers` entries were mostly `builtins.list` and `builtins.dict` containers, including profiler-owned temporary lists/dicts. Final WeakProxy samples in direct/without-Cinnamon cases typically showed 1 list + 1 dict referrer; final Cinnamon samples showed 1 list + 6 dict referrers. This **does not prove** six owners or a cache: the snapshot machinery itself may contribute and sampled proxies need not represent the same provenance. A bounded recursive inspection of actual owning container structure, with profiler-owned references filtered, is needed before production changes.

## Recommended next investigation

1. Add a no-mount baseline and repeat with fixed labels to exclude toolkit text/texture and measurement effects.
2. Instrument before/after `commit_kivy_sfle` and `KivyRenderer.invalidate_layout`: count exact concrete types of `psx.sfle.*` instances and direct Kivy property/event bindings, and snapshot retained dict/list creation using `tracemalloc`.
3. Focus on the ~5 extra dict/list pairs **per cycle** visible only in the SFLE-enabled path; probe whether they are retained by Kivy widget properties, canvas instructions, callbacks or global registries.
4. Once a concrete reference path is identified, add a failing regression, implement narrowly scoped teardown if appropriate, and repeat 5,000 then 10,000 cycles.

**Gate:** C07 Kivy certification **OPEN**; no change to production code or P0→P1 Architecture Gate approval from these measurements.
