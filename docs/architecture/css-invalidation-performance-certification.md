# CSS invalidation and native performance certification

**Scope:** P1.4.7, incremental layout, intrinsic measurements and UI-thread work suppression.
**Status:** Functional test coverage implemented; exact final commit SHA and workflow conclusions must be confirmed before declaring the phase closed.
**Authority:** Cinnamon inside PSX owns geometry. Qt, Tkinter and Kivy retain native paint and measurement ownership. No parallel layout engine is introduced.

## Behavior-specific evidence

| Capability | Production path | Executed behavior tests | Required evidence |
| --- | --- | --- | --- |
| Paint versus geometry and text measurement | `psx/css/effects.py`, `psx/core/reconcile.py` | `tests/css/test_effects.py` | Paint-only updates preserve keyed widgets and skip geometry; dimensions and fonts still reflow |
| State-driven coalescence | `psx/core/scheduler.py`, `psx/core/reconcile.py` | `tests/test_hooks_scheduler.py` | 100 batched state updates produce no redundant layout commit; subsequent dimension change commits |
| Native invalidation epochs | `psx/sfle/native_measurement_invalidation.py` | `tests/test_native_measurement_invalidation.py` | Duplicate reasons/targets coalesce; new dependencies/global scope advance epoch; stale acknowledgements are rejected |
| Isolated Flex context reuse | `psx/sfle/context_invalidation_plan.py`, `psx/sfle/compute_alpha.py` | `tests/test_incremental_result_reuse.py` | 1,000 alternating width changes match full geometry on every cycle; unrelated Flex subtree is explicitly reused |
| Measurement cache | `psx/sfle/native_intrinsic_cache.py` | `tests/test_native_intrinsic_cache.py`, `tests/test_native_measurement_invalidation.py` | Content, font, resource, constraint and width changes remeasure affected widgets, not independent widgets; cache publication is transactional |
| Native CSS rendering and theme events | `psx/renderers/qt/pyqt.py`, Tkinter and Kivy native renderers | `tests/test_mounted_grid_native_renderers.py` | 100 CSS foreground alternations preserve native geometry and produce zero redundant geometry commits; a real child width change commits |
| Native lifetime and cleanup | `psx/sfle/native_intrinsic_cache.py`, renderer unmount | Native lifecycle tests and 1,000-cycle intrinsic cache soak | At most one live cache entry per visited native widget in the tested scenario; clearing removes entries and tracked measurements |

## Reproducible measurements

The native test `test_native_css_paint_burst_does_not_commit_cinnamon_geometry` runs under `PSX_GRID_BACKEND=qt`, `tk` and `kivy`, including the Qt binding jobs in the native layout workflow. It stores numeric properties in the per-platform JUnit report:

- `paint_100_elapsed_ns`: monotonic wall-clock latency for 100 native paint updates.
- `paint_100_cpu_ns`: process CPU time consumed during those updates.
- `paint_100_memory_growth_bytes`: change in live traced Python allocations over the update burst.
- `paint_100_tracemalloc_peak_bytes`: peak traced Python allocations during the same test.
- `paint_100_layout_commits`: **required value 0** for those 100 paint-only changes.
- `geometry_update_elapsed_ns`: wall-clock cost of one real width change after the paint burst.
- `backend`: the native renderer used.

Timing metrics are measurements, not fixed acceptance thresholds: shared CI virtual machines, fonts, native themes and display backends affect absolute values. The stable acceptance gate is geometry identity, correct native visual changes and a measurable absence of unnecessary layout commits. A numerical speedup across different workloads is **not** claimed from these counters.

### Reference measurement-work reduction

The 1,000-cycle pure cache soak retains 16 native widget identities with one edited leaf per cycle. The assertions require **1,015 intrinsic measure calls**, versus **16,000** for measuring all 16 every round (93.65625% fewer calls). This is an instrumented *count*, not a 93.6% CPU speedup. At each successful commit the cache contains exactly 16 live identities, and explicit disposal empties it. The complementary width-measurement tests cover wrapping width keys and global invalidation.

The independent Flex subtree is reused across 1,000 consecutive incremental solves; every computed rectangle is compared with a full Python Cinnamon solve. A changed environment, an unsupported formatting host or an unsafe dependency graph conservatively falls back to a complete solve, rather than claiming partial computation.

## Known boundaries

- Only a **proven paint-only** host-subtree change may bypass `commit_layout`. Component/native structural changes, new props, absent or incompatible style snapshots, pending semantic invalidations and font/geometry effects all require a normal commit.
- External Qt font, palette, system style and DPI events must remain invalidation sources. Qt-generated QSS style events from PSX's own projection are not equivalent to external system-theme notifications.
- CPU time, traced Python allocations and a 100-cycle native smoke benchmark cannot establish absolute FPS, native C++/Tcl/SDL memory totals, or process lifetime memory growth. Those require a separate process-level soak and release hardware matrix.
- The P1.4.8 release gate still owns full platform/font/DPI/theme matrix and CSS Core visual parity, not these bounded performance acceptance tests.

## CI execution

The native selective workflow executes the named CSS, scheduler, intrinsic cache, incremental solver and mounted Qt/Tkinter/Kivy suites (including PySide/PyQt matrices); the routed public behavior and grid workflows preserve their previous independent gates. Every claim of green certification must identify the **same immutable implementation SHA**, executed non-skipped job names, artifacts and final conclusions. A queued or cancelled job is not a PASS.
