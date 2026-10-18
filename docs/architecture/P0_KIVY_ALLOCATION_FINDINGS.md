# P0.9 — Kivy allocation-site investigation (5,000 cycles)

**Date:** 2026-10-18  
**Status:** TRACE ANALYZED; RETAINING OWNER NOT YET IDENTIFIED  
**Source:** User-provided GitHub Actions artifact `p0-kivy-allocation-sites-39144692699.zip`, containing `kivy-allocation-sites.json`.  
**Target:** `Neuri-AI/PSX:develop`; analysis is observational, not implementation approval.

## Actual execution measurements

The profiler completed **5,000 Kivy cycles**, with its comparison baseline captured **after cycle 500** (not at startup). Python-traced allocations are compared after event flushing and GC.

| Metric | Value |
| --- | ---: |
| Duration | 468.967 seconds |
| RSS at startup | 152,805,376 B |
| RSS at cycle 500 | 170,131,456 B |
| RSS at cycle 5,000 | 245,407,744 B |
| RSS increase after warmup (500→5,000) | **75,276,288 B (~71.79 MiB)** |
| Total positive tracked Python allocations | 17,604,816 B |
| Total negative tracked Python allocations | -102 B |
| Net Python-traced allocation delta | **17,604,714 B (~16.79 MiB)** |

**Interpretation:** positive Python allocation deltas persisted over the observed interval, and RSS increased more than Python-traced memory. RSS includes SDL2/OpenGL/Kivy native allocations and allocator arenas; **neither figure alone proves a permanent leak**, and neither can be labeled Velto-only RAM.

## Largest six allocation tracebacks

The profiler reported positive allocation sites grouped by **full traceback** (not object-retaining referrer). The six dominant groups sum to **17,604,000 B**, accounting for about **99.995%** of tracked positive allocation growth.

| Rank | Allocation bytes | Count delta | First reported frame | Notable downstream frames |
| --- | ---: | ---: | --- | --- |
| 1 | 10,800,000 | +27,000 | `psx/core/reconcile.py:72` | `reconcile.py:120`, `:113`, `psx/renderers/kivy/kivy.py:664` |
| 2 | 2,808,000 | +54,000 | `psx/core/reconcile.py:72` | `reconcile.py:120`, `:113`, `kivy.py:664` |
| 3 | 1,728,000 | +27,000 | `psx/core/reconcile.py:120` | `reconcile.py:113`, `kivy.py:664`, `psx/renderers/adapters.py:68` |
| 4 | 1,008,000 | +18,000 | `scripts/p0_memory_soak.py:184` | `reconcile.py:72`, `:120`, `:113` |
| 5 | 720,000 | +9,000 | `scripts/p0_memory_soak.py:184` | `reconcile.py:72`, `:120`, `:113` |
| 6 | 540,000 | +9,000 | `scripts/p0_memory_soak.py:184` | `reconcile.py:72`, `:120`, `:113` |

The counts are strikingly proportional to the **4,500 cycles between snapshots**, consistent with surviving small allocations from repeated root/child Kivy mount work.

### Source inspection

- [`Reconciler.render`](../../psx/core/reconcile.py) at around line 72 performs `self.root = self._mount(node, None)` when empty; `_mount` at around 113–120 creates a `MountedInstance` and delegates native node creation to `renderer.create`.
- [`KivyRenderer.create`](../../psx/renderers/kivy/kivy.py) at around line 664 creates a new `VNode` with a filtered props dict when Cinnamon native layout is enabled and the node is not Flex/Grid/GridItem.
- The [soak driver](../../scripts/p0_memory_soak.py) around line 184 constructs fresh `Flex(Button(...))` inputs per iteration.
- [`KivyRenderer.invalidate_layout`](../../psx/renderers/kivy/kivy.py) clears its mounted root, root-size/window bindings, native intrinsic cache and image watchers on normal unmount.

**Supported inference:** the dominant retained allocation sites are **on the PSX reconciliation → Kivy native create → new VNode/props path**. This is **not** proof that `KivyRenderer.create`, Cinnamon, a specific closure, or Kivy Clock is the retaining owner. `tracemalloc` attributes *where bytes were allocated*, not *which references keep them alive*.

The earlier 5,000-cycle baseline reports zero remaining tracked PSX MountedInstance objects, tracked widget wrappers and active event slots; this does **not** rule out cached `VNode` descriptions, Python functions, native bridges or unobserved Kivy global registries.

## Next attribution step (before changing production)

1. In a fresh Kivy subprocess, collect `gc.get_objects()` **exact-type histograms** at cycles 500, 2,500 and 5,000. Include `VNode`, `KivyHandle`, `dict`, `tuple` and Kivy `Widget` classes. Avoid `isinstance()` on dead Kivy weak proxies.
2. For growing concrete types, identify referrer **classes and ownership paths** with bounded sampling; avoid retaining the objects in the profiler itself. Prefer a heap inspection / referrer report over guesses about caches.
3. Run an **A/B comparison**: same 5,000-cycle widget churn in the direct Kivy toolkit vs Kivy through PSX/Cinnamon, preserving equivalent layout and event binding and synchronized GC. A/B must be run on a comparable environment.
4. Retest a narrow suspected reference owner with a minimal regression. Only then implement a targeted fix or explicitly document a bounded upstream Kivy cache.
5. Repeat 5,000 cycles and verify that allocated Python bytes and native RSS **plateau after warmup**; retain 10,000-cycle long-run as the final cross-backend gate.

**Gate decision:** C07 Kivy long-running memory certification remains **OPEN**; broad P0→P1 Architecture Gate is not approved by this analysis.
