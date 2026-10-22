# Resource lifecycle and performance baseline

**Scope:** Initial measurement audit (P2.1 planning traceability). No production lifecycle API changes. This instrument measures **Headless only**, with **Cinnamon Rust and Cinnamon Python explicitly separated**, avoiding native toolkit timing comparisons.

## Reproducible run

From a checkout with this branch installed:

```bash
python benchmarks/resource_baseline.py --nodes 16 --cycles 100 --warmup 10 --engine both --output resource-baseline.json
python -m pytest -q tests/test_resource_baseline.py tests/test_ci_impact.py
```

The JSON captures Python/runtime/platform, independent mount/unmount, keyed reorder, state-like content change and idle workloads, per-operation mean/p95 wall latency, traced live bytes before workload and after explicit unmount/GC, traced peak bytes, intermediate checkpoints and GC object counts. Where available `resource.getrusage` reports **peak** RSS, not instantaneous RSS. USS is explicitly `null` without a supported provider. Native QObject/widget counts, GPU buffers, subscriptions and native signal counts are **not** measured by this harness; there must be no inferred PASS for these metrics. Callbacks are not instrumented by this minimal harness.

Results are environment- and allocator-specific. Python traced byte differences are observations; neither a positive delta nor a stable peak is alone proof of a leak or of its absence. No fabricated timing target, leak threshold or machine-independent baseline is used.

## Existing audit surfaces

| Risk | Available current evidence | Next audit |
| --- | --- | --- |
| VNode/reconciler | Headless mount/unmount and keyed-reorder probes; existing reconciliation tests | Check weakrefs and live handler counts after repeated native teardown |
| Hooks/effects | Existing hook scheduler/effect tests | Capture cleanup closure lifetime and active effect counts |
| Qt widgets | Existing native lifecycle and teardown tests | Track both QObject destruction and Python wrapper references |
| Tkinter | Existing native lifecycle tests | Track Tk bindings and widgets after teardown |
| Kivy | Existing mounted lifecycle tests | **Long-running memory-growth investigation explicitly deferred by owner to a separate iteration** |
| Pydux | External integration, not measured here | Audit subscription ownership in a dedicated increment |
| Async | Not measured | Add cancellation/late-callback ownership probes |
| Cinnamon | NativeIntrinsicCache generation-bounded tests and incremental solve parity | Sample cache entry counts before/after mount/unmount |
| Resources | Existing image/canvas lifetime tests | Quantify live buffers/assets and eviction |
| Diagnostics | Not measured | Count observer/log references after teardown |

## Audit execution and baseline acceptance

- This increment introduces a reproducible **instrument**, not an alleged recorded runtime measurement. CI must actually execute `tests/test_resource_baseline.py`; its JUnit receipt and exact SHA establish whether measurements and validation ran.
- Capture real numeric JSON per environment before setting per-scenario regression thresholds; **do not** claim CPU, USS, native-widget counts or native-platform memory as measured until a suitable instrument exists.
- For subsequent increments, establish a fixed warmup, repeated teardown, stable observation window and compare like-for-like environment baselines. Keep real memory growth and allocator high-water behavior distinct.
- Public API impact: **N/A** — no public component, method, prop, event or capability is introduced. This is a development-only benchmark under `benchmarks/` and tests under `tests/`.
- Kivy long-run memory growth is intentionally **out of scope for this iteration**, per owner decision; do not treat this as a resolved risk.

## Executed Linux headless baseline

**Implementation SHA:** `6779fca3ed44a2f35d4525eb2a8b94ba5b3b83be`. [Native CI run and JSON artifact](https://github.com/Neuri-AI/PSX/actions/runs/39809663985/artifacts/12440330245).

**Environment:** CPython 3.12.15, Linux 7.0.0-1017-azure x86_64, glibc 2.39; 16 nodes, 100 measured cycles and 10 warmup cycles.

| Workload | Mean ms/cycle | p95 ms/cycle | Traced delta after teardown (bytes) | Traced peak (bytes) |
| --- | ---: | ---: | ---: | ---: |
| Mount/unmount | 36.5516 | 38.6942 | +4,912 | 1,911,855 |
| Keyed reorder | 35.5891 | 37.4610 | -68,875 | 1,273,284 |
| State-like update | 36.2177 | 38.2310 | -65,318 | 1,180,548 |
| Idle | 0.0005 | 0.0006 | -57,273 | 286,377 |

The process peak RSS high-water observed was 29,863,936 bytes; instantaneous RSS and USS were not collected. The Python traced deltas reflect allocator/cache conditions, not leak verdicts. No native widget memory conclusion follows.

**Initial audit increment status:** instrument implemented, actually executed and machine-specific baseline captured with immutable implementation SHA and original JSON. Full native resource ownership and leak audits are later P2 work. Kivy long-running memory growth remains explicitly deferred to a separate iteration.


## Dual engine acceptance

The Rust sample requires the installed `_sfle_native` wheel, negotiated by `load_layout_engine()`, and fails explicitly if Rust cannot be selected; it must never relabel the Python fallback as Rust. The CI core job builds a Rust release wheel via maturin and records separate `engine=rust` and `engine=python` entries under identical benchmark parameters. The historical timings above are **Python-only** and must not be reinterpreted as Rust numbers. P2.2 ownership regressions also instantiate both engines while exercising teardown. Long-running Kivy memory growth remains excluded.

## Hook and reconciler lifecycle audit

The state setter closure is externally retainable by application code. Disposal now clears `_StateSlot.value` to release the obsolete payload even if the setter remains referenced; setters stay inert after disposal. Executable tests cover this invariant plus keyed subtree removal, `use_ref` clearing, `use_effect` cleanup exceptions and effect-owned payload release. Ownership regressions use an explicit Flex root and both Cinnamon engine implementations once the native Rust wheel is installed. These are tests of reference release, not a long-running heap-growth verdict. No public API, property, event, or component surface changes, so the public capability census is N/A.
