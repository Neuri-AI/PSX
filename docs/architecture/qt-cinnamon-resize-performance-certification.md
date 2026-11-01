# Qt resize performance certification — Cinnamon Rust/Python

Status: audit and reproducible certification specification; **no runtime measurements recorded yet**.

Branch: `feature/semantic-inline-fragments`

## Architectural invariant

Cinnamon Rust and Cinnamon Python are coequal numerical implementations of `LayoutEngine`. The Python fallback is retained, including for prospective iOS deployment. Any future numerical behavior change must be implemented in both engines and certified against the same inputs. Renderer optimizations must not change either engine's geometry or diagnostics.

## Actual Qt resize call chain

1. `psx/renderers/qt/pyqt.py:_make_resize_filter` handles the actual Qt Resize event.
2. `_sfle_on_viewport_resize()` deduplicates dimensions and queues one `QTimer.singleShot(0)` for the latest pending size.
3. `_sfle_flush_viewport_resize()` sets constraints and calls `commit_layout(root)`.
4. `commit_layout()` dispatches Grid to `commit_native_grid`, otherwise to `psx/renderers/qt/cinnamon_qt_layout_bridge.py:commit_qt_sfle`.
5. `commit_qt_sfle()` prepares structural/CSS snapshots, reuses valid native measurements, invokes Cinnamon and commits rectangles to actual Qt widgets.
6. Qt performs native painting on subsequent events. Returning from `commit_layout` is **not** proof painting completed.

## Existing optimizations observed

- Deferred, coalesced resize dispatch using a zero-timeout QTimer and an epoch.
- `NativeIntrinsicCache` and targeted semantic invalidation.
- Structural snapshot reuse and layout/paint signature partitioning.
- Prior successful solver snapshots and incremental compute, when eligible.
- Stale-epoch checks and bounded retries.
- Some HTML-like roots use `engine.compute()` directly; do not assume incremental reuse across every root.

## Measurement protocol (mandatory before an optimization is certified)

Run on the same host, Python, Qt binding, viewport, rendered tree, and typography settings. Install the real native Cinnamon extension. Instantiate each engine explicitly rather than relying on automatic fallback selection.

Measure **separately** with `time.perf_counter_ns()`:

1. Native resize event ingress and the delay until scheduled flush.
2. CSS/structure snapshot preparation.
3. Native intrinsic measurement: call count, cache hits, per-measurement latency.
4. Rust or Python solver time, recording full vs incremental and reused contexts.
5. Native widget geometry commit: changed rectangles, setGeometry calls, widgets created/destroyed.
6. Qt paint events and latency through a *processed* paint event, separately from layout commit.
7. Overall resize-event-to-paint latency and number of resize events per committed frame.

Do not call `repaint()` merely to force a favorable benchmark: it changes production scheduling behavior. Instrument `QEvent.Paint` in a test-only event filter and pump the normal Qt event loop. Run both warm and cold profiles. Do not compare an offscreen pass against an onscreen pass.

## Scenarios

- 24 / 100 / 500 native widgets.
- Pure Flex and mixed Grid/Block/Inline.
- Height-for-width text and stable intrinsic sizes.
- Alternating widths around wrap and breakpoint thresholds.
- 100 sequential width changes and 200-event resize bursts.
- Font change, DPR change, semantic content edit, and no-op resize.
- Mount, unmount, remount; ensure no callbacks use disposed widgets.

## Outputs

Emit raw JSONL events (phase, engine, scenario, generation, timestamp_ns, duration_ns, reused_contexts, native_measurement_count, geometry_commit_count), and aggregate p50, p95, p99; report absolute ms and confidence caveats. Use identical scenarios for both engines and **assert exact geometry and diagnostics before interpreting timings**.

Acceptance:
- Geometry identical at signed 1/64 CSS pixel for declared supported features.
- Identical unsupported-feature diagnostic codes.
- No stale commit, crash, widget recreation on pure resize, or dropped final viewport size.
- No unsolicited Python numerical import on Rust execution.
- No regression against recorded baseline beyond a documented threshold.
- 60 FPS target is 16.67 ms frame budget, but must be judged with true end-to-end paint latency; report failures instead of hiding them.

## Optimization guardrails

Do not change scheduling to a fixed 16 ms debounce, introduce worker-thread native measurement, skip remeasurement when width affects intrinsic height, or bypass numeric parity checks. Only optimize shared projection, valid caches, Qt changed-rectangle commits, or equivalent *paired* engine algorithms after profiling identifies the bottleneck.

## Reproduction commands (from a branch checkout)

```bash
git checkout feature/semantic-inline-fragments
python -m pip install -e '.[dev]'
python -m pytest -q tests -k 'cinnamon and (parity or incremental or qt)'
```

The optional extra and filter must be adapted to the repository's actual test configuration if unavailable. These are starting commands, **not** evidence of a successful execution. Actual Qt GUI timings require a machine with a runnable Qt binding and a graphical/event-loop environment.
