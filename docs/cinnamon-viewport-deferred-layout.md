# Cinnamon viewport-aware incremental layout

## Invariant

Cinnamon Rust remains the only authority for solved CSS geometry. Viewport awareness
is an optimization hint, never permission to commit guessed, stale, or incomplete
rectangles. Every result must match the full solve for the same normalized
snapshot, subject to existing 1/64 CSS pixel accuracy. Renderers own native
measurements, scroll state, widget geometry and painting; the engine never
imports Qt, Tkinter or Kivy.

No public developer opt-in or special VirtualList / VirtualGrid is required.

## Implemented

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
cargo test --manifest-path rust/sfle-core/Cargo.toml --lib html_offscreen_subtrees_defer_recursion_without_stale_geometry
cargo test --manifest-path rust/sfle-core/Cargo.toml --lib viewport_resize_reuses_still_definite_flex_children
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
readback for entire previously accepted **below-viewport** GridItem groups.
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
