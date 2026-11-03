# Cinnamon viewport-aware incremental layout

## Invariant

Cinnamon Rust remains the only authority for solved CSS geometry. Viewport awareness
is an optimization hint, never permission to commit guessed, stale, or incomplete
rectangles. Every committed or current-width-certified result must match the full solve for the same normalized
snapshot, subject to existing 1/64 CSS pixel accuracy. Renderers own native
measurements, scroll state, widget geometry and painting; the engine never
imports Qt, Tkinter or Kivy.

Virtualization is an internal PSX responsibility. Developers never change their
interface, restrict their components or manage the viewport to benefit from it.
There is no public opt-in, VirtualList or VirtualGrid API.

## Native resource lifetime and initial materialization

Certified ordinary text GridItems and repeated Flex/HTML/Block cards now start with a complete logical instance
tree and **no native handles**. `MountedInstance.native_suspended` differs
from an allocated widget that has merely been detached. `StructuralBinding`
retains logical layout identity and no toolkit resource. Cinnamon's existing
Grid/Flow composition resolves tracks, item heights and document extent using
one renderer-owned structural text probe, shared across intrinsic queries.
The viewport workset materializes only visible and partially visible groups,
the internal 96px overscan, and any group requiring the complete fallback.

The reconciler updates suspended descriptions and hook state without native
create/update/insert calls. Reactivation creates resources from current props,
CSS and event callbacks, without reevaluating components or cleaning up hooks.
Failed activation releases its partial native allocation while retaining the
logical subtree for retry. Actual native refs, effects and focus retain the
attached fallback. Unsafe nested Grid dependencies keep the established full
composition path. There is no developer-facing switch or annotation.

Native-only viewport commits reuse a renderer-owned mounted layout index;
logical reconciliation and native measurement epochs invalidate that index.
Native handle incarnation is excluded from the immutable logical projection,
while native readback and measurement continue using live identities.

The original four-column styled Grid has been measured with **218 initial
native widgets** for 100, 500 and 5,000 logical cards (plus one unmounted
structural measurement probe). Tests audit `renderer.create` itself, so a
create-all-then-destroy implementation cannot satisfy that check. Grid scroll
reentry and initial mount tests execute against Qt, Tkinter and Kivy.

The same internal workset serves ordinary repeated Flex and HTML/Block cards,
including their real Scroll clip. Component bodies execute logically before
native classification: discovering a control, exposed ref, effect or uncertain
positioning promotes its owning group alone. Hook state remains live while its
native resources are absent, including reactive updates before scroll reentry.
The structural text port uses each backend's existing glyph measurement;
an absent widget is never passed to a native getter or a geometry setter.

Normal-flow receipts additionally retain a conservative minimum height derived
from Cinnamon's accepted boxes and native intrinsic lower bounds. Static CSS
and row-packing proofs are cached with the immutable tree. These bounds permit
early P2 classification without treating a previous wrapped height as a new
width-specific measurement. Reused unwrapped text metrics still run through
Cinnamon to produce current-width horizontal rectangles.

## Indexed structural tracks and sparse native batches

An immutable fixed-span, complete-row Grid whose normal-flow cards have equal,
certified width-independent heights can retain **indexed Cinnamon tracks**.
The Rust `uniform_grid_template` calls the existing Grid kernel for the column
projection and validates the fixed-point stride and complete document extent.
Its indexed receipt retains geometry for every logical GridItem while creating
detailed Flow rectangles only for the viewport, overscan and currently live
groups that still require a native lifecycle transition. Partial final rows,
uncertain heights, responsive spans, non-unit device scale and complex CSS keep
the complete existing path. There is no independent Python layout algorithm.

The height proof uses independent native **unwrapped** text measurements. A
toolkit hint that clamps preferred width to the probe cannot certify a wrapped
height. Qt's integer glyph advances retain a conservative pixel in the proof;
Tk settles the scratch label before reading its requested size. All committed
rectangles still come from Cinnamon at the current width. Tests compare indexed
tracks and visible Flow boxes with the complete solve, including fractional
geometry, RTL, compact gutters, overflow and native baseline constraints.

Already absent, certified P2 groups contribute no native batch entries. Their
accepted structural receipts remain available for future viewport selection.
Rollback captures only active widgets, and native style/resource observers use
the reconciler's live resource index. Logical edits and native resource changes
invalidate the corresponding projection or native-incarnation fence.

A distinct viewport receipt may replay an already solved P0/P1 window while
retaining explicit dirty P2 flags. It is never published as exact complete
geometry and cannot supply a Scroll extent. A changed clip, viewport, logical
tree, measurement epoch or newly visible group requires current geometry.
Production renderers retain P2 until it is needed; they do not rematerialize
thousands of offscreen groups after every resize idle interval.

If a narrow width invalidates only the tail's text-height proof, the planner
can certify P0/P1 independently and keep that tail dirty. If visible wrapping
also changes, a minimum-height bound selects a complete structural row prefix
for the existing Cinnamon solver. Later rows cannot influence earlier
fixed-span tracks. The provisional tail has no native handles or batch entries
and cannot supply a Scroll extent; entering a new clip forces current geometry.
This avoids rebuilding thousands of P2 measurement/placement records on each
intermediate narrow width.

`native_resize_fps.py` keeps the original four-column styled card workload and
reports initial VNode/mount cost, phase times/calls, actual materialized nodes,
mount/unmount activity, native pin reasons, structural fallback reasons, p50/p95
request-to-commit and request-to-processed-paint. Qt uses a synchronous repaint
fence, Tk flushes redraw idle handlers, and Kivy dispatches canvas draw/flip.
These are owner-thread processing measurements; compositor presentation FPS
remains explicitly unavailable. Both fresh and previously visited widths matter.

```bash
python benchmarks/native_resize_fps.py --adapters qt tk kivy --engine rust \
  --scenario cards --counts 100 500 5000 --cycles 40 --warmup 5 --timeout 60 \
  --output benchmark-results/automatic-native-virtualization
```

Conservative fallback remains necessary for uncertified width-dependent
structural work. This implementation does not promise O(visible) computation
for arbitrary auto-sized or overlapping CSS. Native fallback is per group;
an unsafe control or exposed handle does not pin unrelated pure siblings.

Tests for the current pipeline include `test_native_suspended_lifecycle.py`,
`test_grid_uniform_projection.py`, `test_grid_early_viewport.py`,
`test_grid_geometry_reuse.py` and `test_mounted_grid_native_renderers.py`.

The sections below retain the history of computation and attachment layers.
Statements about complete native mounting and idle settlement describe those
earlier layers, not the resource-lifetime pipeline documented above.

## Earlier computation and attachment layers

1. **Incremental definite Flex contexts.** The Rust engine can reuse an
   unchanged, definitely sized descendant when its assigned axes are unchanged
   even if the outer viewport constraints changed. Geometry still undergoes
   fresh parent placement. Style, measurement or percentage dependencies
   invalidate reuse.
2. **HTML-like normal flow.** Rust can defer recursion into certified,
   unchanged, text-only Block subtrees outside the viewport plus a 96 CSS px
   overscan. The prior complete geometry is translated to the new containing
   position only if the subtree's effective content width is unchanged.
   Parent flow height is retained, and *all* output boxes remain present.
   Scroll roots or percentage/viewport/unknown dependencies fall back to
   complete calculation. The visible subtree always resolves normally.
3. **Exact cross-generation results.** A bounded Rust-facade cache can reuse
   complete small normalized layout snapshots for previously seen constraint
   combinations, ignoring only generation and native measurement revision
   counters. It retains no widget handles, rejects incomplete/errorful
   results, and honors native invalidation barriers.
4. **Committed GridItem Flex/HTML text contexts.** A bounded per-renderer
   cache reuses solved rectangles at an identical effective content width,
   immutable vnode/CSS signature, pixel scale and invalidation epoch.
   Publication happens *after successful* native geometry commit and
   readback. A failed commit never exposes pending geometry.
5. **Native UI remains complete.** Qt, Tkinter and Kivy still mount every
   widget and apply/verify all changed native geometry. Existing skip-unchanged
   commit optimization prevents redundant property notifications. Scroll
   offsets and rollback remain controlled by toolkit-specific transactions.
6. **Unchanged native readback.** Qt and Tk reuse the rollback rectangle
   captured earlier in the same transaction for nodes that were not written,
   including explicitly placed Grid descendants. Changed Grid nodes still
   receive a fresh native read, and relative Tk placement is excluded.
   External native ports, Scroll hosts/descendants, image-painted nodes,
   changed text-wrap lengths, and relative Tk placements still get live
   native reads. Kivy always performs live readback. Kivy's outer geometry
   committer also uses the same-transaction snapshot for unchanged axis
   comparisons, avoiding duplicate native property getters.
7. **Conservative bitmap paint reuse.** Qt QLabel and Tk PhotoImage reuse a
   previously accepted bitmap when source, fit and native target rectangle
   are unchanged. No new image scaling or Tcl PhotoImage allocation occurs
   on those hits. Native widgets remain mounted and the accepted pixels
   remain available to Scroll and window expose events; failed geometry
   transactions invalidate unaccepted bitmap receipts. Kivy only refreshes
   text textures when an intrinsic probe or changed wrap width requires it.

## Fail-closed cases

A full solve is required if there is no accepted prior result, the effective
content width or any style/intrinsic measurement changed, children were
reconciled, the pixel scale changed, a resource invalidation occurred, or
a subtree contains unsupported native controls, nested Grid, Scroll, or
unknown/overlapping/complex CSS behavior. The presence of a viewport alone
is never evidence that a subtree has no effect on document height.

Overlapped, transparent, transformed or rounded widgets must not be
occlusion-culled without a separate backend-aware opaque-region and stacking
proof. Nothing in this change skips event handlers, focus,
accessibility, required redraws after content changes, or mounting. Pure
repainting of already accepted, byte-identical bitmap content is avoided.

This implementation is *not* universal windowed widget virtualization or
general occlusion culling. It is a safe first layer of viewport-aware deferred
**computation** with a complete fallback. Arbitrary auto-sized offscreen
subtrees may still require full measurements.

## Certification

Use the Rust core and Python native geometry tests:

```bash
cargo test --manifest-path rust/cinnamon-core/Cargo.toml --lib html_offscreen_subtrees_defer_recursion_without_stale_geometry
cargo test --manifest-path rust/cinnamon-core/Cargo.toml --lib viewport_resize_reuses_still_definite_flex_children
python -m pytest -q tests/test_grid_solved_subtree_reuse.py tests/test_cinnamon_exact_context_cache.py tests/test_native_readback_reuse.py
# With a real X display, or xvfb-run on Linux:
python -m pytest -q tests/test_native_image_paint_reuse.py
```

The `Grid resize performance` GitHub workflow also certifies native
Qt/Tk/Kivy Grid geometry and nested Scroll offset integrity.

## Reproducible A/B

```bash
python benchmarks/grid_resize_interactive.py \
  --engine rust --adapter qt --cards 60 --cycles 20 --warmup 2 \
  > solved-reuse-on.json

python benchmarks/grid_resize_interactive.py \
  --engine rust --adapter qt --cards 60 --cycles 20 --warmup 2 \
  --disable-solved-reuse > solved-reuse-off.json
```

Compare `native_widgets`, `rust_actual_compute_abi_calls`,
`deferred_text_subtree_hits`, mean and p95 event-to-commit.
The identical-widget baseline disables only solved-context caches, not
structural blueprint caching or native geometry commits.

**Performance caveat:** A completed native resize/layout transaction is not
an actual composited/presented frame. Do not describe `layout_hz` or
`event_to_commit` as verified display FPS.

## Large-Grid cache capacity

Solved GridItem text contexts are keyed by the item's immutable style/VNode,
pixel scale, effective content width and invalidation epoch. A cache bounded
at only 4,096 entries can thrash at 500 cards traversing nine widths
(4,500 independent solved receipts). Structural Flow blueprints remain
limited to 4,096 nodes, while the independently bounded solved cache
retains up to 8,192 width-specific results. Native Grid text intrinsic
hints have a separate 16,384-entry bound because each card can contain
multiple text leaves. Reuse is still conditional on unchanged semantic
identities and successful native commit; no stale or guessed geometry
becomes eligible because of these capacity changes.

Neither larger cache nor fewer native readbacks constitutes universal
offscreen geometry virtualization, and cache capacity alone cannot
guarantee the 60 Hz frame budget for 3,002 mounted native widgets.

## Automatic native Grid viewport worksets (new)

The root Grid and Grid descendants inside Flex/Block/Scroll retain all
Cinnamon-solved rectangles, all mounted widget identities, normal flow extent,
and the exact native clipping/scroll behavior. After one complete accepted
native commit, a 96px-overscanned viewport planner can defer *native*
geometry setters, pre-mutation reads, rollback snapshots and post-commit
readback for entire previously accepted GridItem groups **fully above or
below the live viewport**. Above-viewport pruning uses a conservative
whole-subtree bottom bound derived from hierarchical local Y chains (rather
than summing sibling offsets), not merely the GridItem's own rectangle.
Such groups are not reported as newly verified native rectangles;
`GridNativeCommitReceipt.deferred_node_ids` names them precisely.

A GridItem is eligible only when the complete group was physically committed
below the viewport in the previous accepted transaction and its newly
allocated rectangle also remains below the live clip; a changed native
identity, semantic invalidation epoch, unknown positioned/overlapping CSS,
unsupported paint overflow, native leaf, external scroll owner or incomplete
group forces real native placement and verification. No occlusion inference
based merely on z-order or overlap is made. Scroll X/Y changes are observed by
Qt scrollbars, Kivy ScrollView properties and Tk wheel/key handlers. The
renderer schedules an owner-thread Cinnamon transaction to update elements
before a previously deferred group is considered accepted onscreen.

A pure window-resize fast path can skip the majority of the 3,002 native
widgets when those are inside eligible card groups and after the first full
commit. The Rust engine remains authoritative: this is **sparse native commit
virtualization**, not wholesale skipping of all Rust CSS/layout computation or
native mounting. Newly visible groups, complex CSS, repaint invalidations,
and root Scroll extent changes still require full geometry or measurements.
It does not provide automatic destruction/recreation of offscreen controls or
occlusion culling behind arbitrary opaque layers.

Regressions for the three backend-specific native geometry protocols:
`tests/test_grid_viewport_workset.py`,
`tests/test_grid_viewport_native_three_backends.py`, and
`tests/test_viewport_scroll_reentry.py`. Platform-native certification and
Mac resize p95/FPS must be evaluated separately; headless widget-port tests
cannot certify presented frames. Before/after comparisons should include
unchanged mount counts, active/deferred native receipt counts and scroll
reentry/scrollbar extent integrity, not merely cache-hit ratios.

## Ordinary HTML and Flex card lists

A separate `native_flow_viewport` workset detects the largest repeated
sibling tier in the already resolved Cinnamon tree (at least 12 siblings)
and groups each card with its nested native descendants. After an accepted
first commit, the same conservative viewport guard can omit native
placement, pre-commit geometry reads, rollback snapshots, and readbacks for
entire known-offscreen card subtrees. These worksets are automatic and do
not require a new public CSS tag or the developer to manually annotate
virtual lists. `renderer._psx_native_flow_deferred_ids` exposes a
diagnostic-only count of the IDs deferred in the latest accepted native
geometry commit. These are never counted as newly verified rectangles.

Native Scroll owners retain their independent scrolling contract; the
workset compares solved absolute card coordinates against the actual
viewport and current native scrollbar offset. Each backend connects the
native scroll event to a coalesced layout transaction so cards entering
the viewport regain freshly committed geometry. Explicit CSS
positioning/transformations, unknown paint overflow, native widgets,
nested scroll owners, and uncertain subtree bounds are not culled.

These optimizations leave Rust Cinnamon's full fixed-point structural
geometry, width dependencies, scroll extents and semantic invalidation
authority intact. They do **not** claim complete offscreen Rust computation
elimination, FPS certification or safe occlusion culling for arbitrary
overlapping transformed elements. Tests cover 500-card pure worksets,
30-card native backend ports, 48-card real native HTML/ Grid flows,
and deterministic Scroll reentry. The dedicated
`.github/workflows/viewport-native-certification.yml` provides
per-backend Qt, Kivy and Tk CI checks. Mac latency p95 must still be
remeasured on a real display session to claim the 16.67ms target.


## A/B benchmark: same Rust solver with/without sparse native worksets

The diagnostic `--disable-viewport-defer` flag forces the exact same
Cinnamon/layout/widget tree through a full native commit. It disables only
native viewport workset pruning for that benchmark process, without
altering the Rust engine, CSS values or native widget mounting.

Run the same native resize workload twice on the same machine:

```bash
python benchmarks/native_resize_scaling.py --adapter both --engine rust \
  --counts 24 100 250 500 --scenarios cards --cycles 40 --warmup 5 \
  --output benchmark-results/viewport-on.json

python benchmarks/native_resize_scaling.py --adapter both --engine rust \
  --counts 24 100 250 500 --scenarios cards --cycles 40 --warmup 5 \
  --disable-viewport-defer --output benchmark-results/viewport-off.json
```

Compare `p95_event_to_commit_ms`, `native_widgets`,
`deferred_native_flow_node_count` and
`deferred_native_grid_node_count`. The disabled control should show zero
deferred native nodes. This is not a compositor FPS certificate. The
benchmarks measure real Qt/Tk native resize events; Kivy still requires
the separate three-backend native certification and a paced-window benchmark.


### Post-commit scroll reentry and moving ancestors

Qt, Tkinter and Kivy coalesce native Scroll input while Cinnamon is
committing. If a scroll offset is clamped or a pending callback fires
during an in-progress generation, a single follow-up owner-thread
transaction is scheduled **after** the successful native commit.
HTML/Flex and Grid maintain separate deferred-work flags on a shared
Scroll host, so neither can accidentally clear the other's outstanding
reentry request. HTML/Flex deferral receipts additionally stamp the
containing native parent's identity and solved position; when an
ancestor moves, its descendants receive fresh native placements rather
than relying on stale offscreen positions. No deferred box is reported
as newly read back.


### Kivy/Qt native mixed-widget A/B

The existing `kivy_qt_mixed_resize.py` uses the same 1,000 mixed native
widget scene, viewport widths and Cinnamon engine in separate GUI processes.
The additional diagnostic flag disables only accepted viewport skipping,
so it can reveal whether Kivy's expensive native property writes or
Rust/CSS/layout solving dominates. It reports event-to-Cinnamon-commit
latency, **not presented frames per second**.

```bash
python benchmarks/kivy_qt_mixed_resize.py --adapter kivy --engine rust \
  --cycles 100 --warmup 10 --output benchmark-results/kivy-viewport-on

python benchmarks/kivy_qt_mixed_resize.py --adapter kivy --engine rust \
  --cycles 100 --warmup 10 --disable-viewport-defer \
  --output benchmark-results/kivy-viewport-off
```

Review `summary.p95_ms`, `summary.p95_commit_ms` and the
`deferred_native_grid_node_count` diagnostic. Both runs must have identical
mounted widget counts. A large improvement is not guaranteed for complex
interactive content, which deliberately uses conservative safety exclusions.


### Observed 500-card CI A/B result (2026-11-02)

On the same GitHub Actions Ubuntu runner with the Rust engine, 500 styled
cards and equal native widget counts, the workset selected thousands of
offscreen native rectangles. The recorded p95 values were:

| Native backend | Full commit A/B control | Viewport workset | Deferred node receipts | Relative p95 change |
| --- | ---: | ---: | ---: | ---: |
| Qt | 724.29 ms | 664.47 ms | 2,760 | -8.3% |
| Tkinter | 952.47 ms | 669.86 ms | 2,784 | -29.7% |

Source: [Grid resize performance — Cinnamon CPU profile](https://github.com/Neuri-AI/PSX/actions/runs/41499738207/job/125463821915).

These are measured **event-to-completed-layout** p95 values, not render
FPS, and they are not directly comparable to macOS measurements or other
hardware. The data proves that native-commit culling activates but also
shows that remaining full-tree CSS projection, intrinsic/structural
composition and native processing are still too expensive for 16.67 ms
with 500 cards. Neither the present workset nor larger caches certifies
interactive 60 FPS. Actual layout-computation virtualization and
paint/mount virtualization require further architectural work.

### Repeated 500-card CI measurement (commit `1845c55f`, 2026-11-02)

A later same-run A/B sample used 500 cards, 3,002 mounted widgets,
Cinnamon Rust, eight measured cycles and two warmups per backend.
The measurements below are event-to-commit, **not displayed FPS**:

| Backend | Viewport enabled mean / p95 | Full commit mean / p95 | Deferred receipts |
| --- | ---: | ---: | ---: |
| Qt | 275.57 / 503.34 ms | 326.84 / 480.32 ms | 2,760 |
| Tkinter | 316.05 / 584.96 ms | 442.56 / 629.44 ms | 2,784 |

The Qt mean improved but its p95 did not. Eight samples are insufficient
to assert a repeatable p95 speedup, especially across separate process runs.
This workflow certifies that culling is *active*, not that every workload
is faster. See the [actual measurements and CI logs](https://github.com/Neuri-AI/PSX/actions/runs/41559213543).

In that same workflow, the macOS ARM runner's native Kivy smoke check
failed before layout on `Failed creating OpenGL pixel format` while
initializing SDL2. That is an unavailable native graphics context in the
CI environment, **not** proof of a Rust geometry regression. Its real
Apple Silicon Kivy coverage remains unverified in this run; do not turn
the native smoke check into an unreported pass.

The separate viewport native certification runs the same mounted
Qt/Tk/Kivy lifecycle and scrolling cases first against the Python
layout backend and then against a compiled, explicitly checked Rust
Cinnamon wheel. For CI status consult:
[Viewport native certification](https://github.com/Neuri-AI/PSX/actions/workflows/viewport-native-certification.yml).


## Continuous resize priorities and quiescent reconciliation (2026-11-02)

The automatic, conservative worksets now share a three-tier viewport policy:

- **P0**: a group overlapping the overscanned viewport in either the last
  accepted native geometry or the current Cinnamon result. Always commit.
  A newly visible group is immediately P0, even mid-resize or on Scroll.
- **P1**: a group without a complete accepted receipt, with unsafe CSS,
  a changed semantic/intrinsic epoch, native identity/context changes, or
  a possible above-to-below crossing. It must be solved and committed.
  Grid track sizing, ancestor placement, scroll extents, and auto-height
  dependencies remain structural work, not candidate P2 work.
- **P2**: a complete previously accepted subtree whose old and new
  conservative paint bounds are both wholly above or below the live
  viewport. It can defer native geometry writes/readback while resizing.
  The Rust solver independently reuses immutable, definite contexts;
  P2 classification does not grant permission to invent solver results.

Each accepted interactive viewport resize updates a monotonically increasing
generation. A **125ms UI-thread idle debounce** discards superseded resize
generations. If the latest transaction has deferred native groups, the
coordinator starts reconciliation: at most **64 distinct P2 groups per UI
event-loop turn**, with subsequent batches scheduled no earlier than 16ms
later. The group is marked reconciled only after the entire native commit
succeeds. An unsuccessful batch cannot publish receipts. A new resize cancels
the pending settle generation. A Scroll reentry continues to promote newly
visible groups without waiting for the debounce.

The coordinator is backend-neutral and never owns timers or native widgets;
Qt uses QTimer, Tk uses after(), and Kivy uses Clock. All commits remain on
the owning UI thread. It performs no asynchronous Rust solves or concurrent
native mutations. Native paint, focus, accessibility, and full-scroll
semantics must remain correct even while offscreen P2 placement is pending.

### Additional Rust computation savings

The closed HTML-like normal-flow Rust engine can now replay certified
**offscreen embedded Flex** contexts with unchanged containing/content widths,
CSS and intrinsic metrics, in addition to safe Block/Text and heading
contexts. Newly visible or mutated contexts fall through to the complete
Rust solver. For normalized Flex, reusable size receipts are populated by a
single traversal of the accepted subtree; the old eager per-ancestor
descendant-vector construction could consume quadratic memory on deep trees.
Equality of immutable intrinsic sizes and constraints is now typed and
allocation-free rather than JSON-serialized for each comparison.

This is **not** fully universal offscreen computation virtualization:
Grid track sizing, native intrinsic probes, CSS projection and auto-sized
offscreen content can still require complete work at every intermediate
viewport size. Fixed layout/measurement dependencies may qualify for
incremental reuse, but any unknown dependency fails closed. A 64-group
native settlement batch may itself require an expensive full Cinnamon
transaction; limiting groups limits native setters, **not** the solver's
full-snapshot cost. Therefore do not describe the event-loop batch cadence
as a 60 FPS or nonblocking guarantee.

### Targeted certification

```bash
python -m pytest -q tests/test_viewport_resize_priority.py \
  tests/test_grid_viewport_workset.py tests/test_native_flow_viewport.py \
  tests/test_viewport_scroll_reentry.py

cargo test --manifest-path rust/cinnamon-core/Cargo.toml --lib viewport_priority_reuse_tests

# Use a real native display/Xvfb for backend-scroll certification:
xvfb-run -a python -m pytest -q tests/test_mounted_grid_native_renderers.py \
  -k 'automatic_grid_viewport_sparse_commit_and_resize_reentry or automatic_html_card_flow_deferred_native_resize or scroll_newly_visible_grid_items_receive_native_geometry'
```

The dedicated viewport certification workflow compiles a Rust extension and
exercises real Qt, Tk and Kivy widgets. Its status is independent of any
preexisting unrelated failures in PSX's broader test matrix. Re-run real
resize A/B on the same machine before claiming a specific performance gain.


## Pre-measurement Grid P2 and exact viewport reuse (November 2026)

The native workset alone was too late: a 500-card Grid still measured native
text, ran sub-Flow Cinnamon computations, and flattened all child rectangles
before dropping offscreen widget setters. The early path now moves a narrowly
certified subset of the P2 decision **before** those computations.

- **P0:** all visible/newly visible cards get fresh native width measurement,
  a Cinnamon solve and a live native geometry commit.
- **P1:** all cards whose size or position can affect visible structure remain
  fully measured and solved. The current conservative selector requires
  a fixed-span, zero-offset uniform Grid, nonnegative row gaps, and a plain
  root (or sole unstyled block wrapper). It leaves every uncertain or unsafe
  subtree in the structural prefix. It never guesses row height.
- **P2:** only complete trailing Grid rows whose *zero-height lower bound*
  from previous row gaps is below the clipped viewport and overscan **and**
  whose last accepted native position is already below that cutoff may skip
  fresh Flow measurements and sub-Flow solver calls during the native resize
  gesture. A previous accepted Flow provides a **provisional height**, not a
  newly certified current-width result. Those Flow children must not receive
  native geometry setters while provisional. If the final current-viewport
  preflight would make one visible, the renderer aborts the provisional
  transaction before mutation and retries one complete Cinnamon layout.
- **Finalization:** after 125ms of resize idle, the normal UI-thread
  coordinator reconciles at most 64 deferred groups per batch. It rejects
  obsolete generations and disposed/replaced native roots. A new intrinsic
  invalidation clears receipts. Previously solved exact viewport geometry is
  reused before leaf measurements and solver calls; flattened geometry
  receipts may likewise be reused but are rebound to the current mounted
  widget identities.
- **Teardown:** cache entries retain no native handles, are published only
  after successful native readback and viewport acceptance, and are released
  on renderer unmount. Qt, Tkinter and Kivy retain the same safety fences.

**Scope limitation:** this does not yet prove generalized O(visible) layout
for arbitrary Flex trees, scrollers, variable-span/offset Grids, transforms,
overlays, or CSS whose measurements can change independently of a mounted
immutable VNode. Those cases deliberately use the complete existing layout
pipeline; scrolling and newly visible elements still re-enter the live
solver. The provisional tail can temporarily retain an older offscreen
total content height until idle reconciliation; this is not an exact
up-to-date scroll extent and is forbidden beneath a native Scroll owner.

### Reproducible native A/B

The two benchmark scripts now share one implementation and run each
Qt/Kivy/Tk cell in an isolated subprocess:

```bash
poetry run python benchmarks/native_resize_fps.py \
  --adapters qt kivy tk --engine rust --scenario cards \
  --counts 6 12 24 48 100 250 500 --cycles 40 --warmup 5 \
  --timeout 10 --output benchmark-results/viewport-optimization-after

poetry run python benchmarks/native_resize_fps_viewport.py \
  --adapters qt kivy tk --engine rust --scenario cards \
  --counts 6 12 24 48 100 250 500 --cycles 40 --warmup 5 \
  --timeout 10 --output benchmark-results/viewport-optimization-ab
```

The A/B's `before` phase disables the new accepted exact Grid geometry
cache and the native P2 workset; `after` enables both. Pre-existing Rust
incremental layout and immutable text caches remain enabled in *both*
phases. This is an **optimization-switch control**, not two historical
Git commits.

`event_to_commit` is urgent native resize latency.
`request_to_full_settlement` includes idle P2 reconciliation and its
125ms debounce. Per-sample `full_solver_calls`,
`idle_reconciliation_commits` and `early_provisional_p2_groups` distinguish
work truly eliminated from work postponed. `layout_hz` is neither a GPU
presentation rate nor measured compositor FPS; the script deliberately
reports `presentation_fps: null`.

A successful pure 500-card measurement reduction verifies that more than
half of native leaf-width probes have been avoided in the certified sparse
case; it does **not** by itself certify a 60 FPS UI. Real performance still
requires valid Qt/Kivy/Tk native CI, the full benchmark artifacts, and
comparison on the target Mac/Retina hardware.

## Earlier allocated-handle attachment layer

Before handle-free materialization, viewport worksets used an allocated-handle attachment layer. PSX
keeps the logical `MountedInstance` tree, component hooks, keys and Cinnamon
geometry alive, while a certified P2 card root can be removed from its native
parent after a successful commit.  A P0/P1 card is reattached before its next
native geometry write.  The behavior is internal: there is no `VirtualList`,
viewport prop, annotation or application opt-in.

The classifier is fail-closed and works per repeated card/group, including
direct Grid items.  Borrowed `Native` controls, exposed native refs, active
focus, effects that may depend on a handle, and any group with uncertain CSS
remain attached; their siblings can still be virtualized.  Detachment retains
the existing native handle rather than destroying it, so a safe group keeps
its logical identity and can be reattached without hook cleanup or stale
native recreation.  Diagnostics on the renderer report materialized and
dematerialized group counts plus pin reasons.  This is intentionally not an
occlusion algorithm and never changes Cinnamon's structural solve, scroll
extent, or CSS geometry authority.
