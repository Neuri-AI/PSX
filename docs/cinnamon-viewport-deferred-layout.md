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
   captured earlier in the same transaction for nodes that were not written.
   External native ports, Scroll hosts/descendants, image-painted nodes,
   changed text-wrap lengths, and relative Tk placements still get live
   native reads. Kivy always performs live readback.
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
