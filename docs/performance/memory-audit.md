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


## First directly measured Rust versus Python comparison

**Implementation SHA:** `07c0a8df3476b905488f7b90ba123ba82e2eac4f`. [Original dual-engine JSON artifact](https://github.com/Neuri-AI/PSX/actions/runs/39813985995/artifacts/12442150403). CPython 3.12.15; Linux x86_64, 16 nodes, 10 warmup cycles, 100 measured cycles per scenario. The workflow installs the actual maturin-built `_sfle_native` wheel and refuses to treat a Python fallback as Rust.

| Headless workload | Python mean / p95 (ms) | Rust mean / p95 (ms) |
| --- | ---: | ---: |
| Mount/unmount | 49.9696 / 52.6761 | 11.7703 / 13.5140 |
| Keyed reorder | 48.4896 / 50.5785 | 11.5673 / 11.9966 |
| State-like content update | 48.6448 / 51.0994 | 11.6183 / 11.8288 |
| Idle | 0.0010 / 0.0013 | 0.0008 / 0.0012 |

**After explicit teardown, traced retained delta (bytes):** Python +4,916 / -68,867 / -65,310 / -57,273, and Rust +4,900 / -72,880 / -69,323 / -61,222, respectively. This is a synthetic Headless workload; differences must not be attributed solely to Cinnamon's solver without isolating the full measured call graph. Single-environment timings are a baseline, not a general-purpose performance claim.

The earlier Python-only figures used different test-run conditions and cannot be directly treated as a before/after speedup. The JSON records actual values and setup, and future comparisons should use matched environments.

## Reconciliation and hook ownership acceptance

The exact executable revision `4216a8fa79da8e1901e9f7f99fdf8bab1cfd4c69` completed **7/7 PR workflows successfully** (including Native layout selective validation and Grid integral certification). The native-layout core job installed a release-built Rust wheel and ran the parameterized teardown tests with **both** `RustLayoutEngine` and `PythonLayoutEngine`. See [executed CI](https://github.com/Neuri-AI/PSX/actions/runs/39817089006) and [exact SHA checks](https://github.com/Neuri-AI/PSX/commit/4216a8fa79da8e1901e9f7f99fdf8bab1cfd4c69/checks).

The executed ownership regressions cover external state setters, keyed-node replacement and repeated keyed subtree churn (including callbacks retaining payloads), ref clearing on unmount, effect-owned payload collection following cleanup exceptions, reverse-order cleanup of multiple failing effects, and empty hook slots/root after teardown. The benchmark additionally produces distinct engine-tagged wall-time and Python traced-memory entries for four Headless workloads; its Rust-vs-Python comparison is **not** native UI FPS or an isolated solver-only speedup.

**Scoped status:** P2.1 instrumentation and baseline captured; P2.2 VNode/reconciliation/hooks ownership checks passed for the tested Headless workloads and both Cinnamon engines. Qt/Tk/Kivy native resource ownership, Pydux subscriptions, async work, image/GPU resources and broader long-run soak remain future increments. As explicitly directed by the owner, the *long-running Kivy memory-growth investigation* is deferred to a **separate iteration**.


## Native event and widget lifecycle acceptance

**Executed code revision:** `ccdeab62e5aa720d7d31c51abbd19ea4a6bc4de6`. All seven PR workflows completed with conclusion `success`: [native selective CI](https://github.com/Neuri-AI/PSX/actions/runs/39820931377) and [integral Grid CI](https://github.com/Neuri-AI/PSX/actions/runs/39820931453). Successful native suites include the explicit Qt binding matrix (PySide6, PySide2, PyQt5, PyQt6), real Tkinter widgets, and Kivy widgets in Xvfb/SDL2. Do not confuse an intentionally skipped unrelated job with an executed receipt.

The native regression `test_native_event_replacement_and_teardown_disconnects_real_toolkit_callbacks` performs eight iterations per backend: a real native click/command/event dispatch; callback replacement without widget reconstruction; another real dispatch; event-slot disposal and unmount; plus actual Qt deferred QObject deletion, Tk widget destruction, or Kivy parent detachment. One iteration deliberately disconnects the real native subscription and then raises; the reconciler must still destroy the widget and propagate the error. The shared Headless regression additionally detects whether a retained destroyed handle keeps application event closures alive; its destruction releases event props and slots, independent of diagnostic operation-log retention.

**Scope:** These are executed, functional event/teardown regressions, not an unlimited-duration memory soak. Qt deletion is assessed after processing deferred deletes; Kivy native ownership and Builder cleanup retain their distinct owned/borrowed contracts. The previously reported prolonged Kivy memory-growth investigation remains an explicit separate iteration. No public prop, method, event or interaction was added, so the public census is N/A; existing public native behavior receipts remain covered by the selected CI. P2.3 closes for the tested event binding and native widget teardown workloads, not for Pydux/async/cache/image lifetimes, which belong to later increments.


## External store subscriptions, deferred tasks and observers

**Executed implementation SHA:** `b6879e0ef7e41d5035452817100691752efca60c`. Seven of seven pull-request workflows concluded `success`, including the [native selective execution](https://github.com/Neuri-AI/PSX/actions/runs/39827638786) and [Grid integral execution](https://github.com/Neuri-AI/PSX/actions/runs/39827638922). These are exact-SHA code receipts rather than inferred success from a docs-only commit.

**Pydux:** The Qt integration exercises the PSX-aware Pydux adapter pinned in CI at `8de71cee892c5e65a5b5fb223829f4525680a543`. Tests exercise eight real `Store` subscription/dispatch/unmount cycles with no remaining `_subscriptions`, plus twelve provider/selector cycles with verified unsubscribe and last-provider inspector lease release. Selectors remain stable across updates; no subscribed callback acts on a disposed component. The native renderer is PySide6 for the actual store integration, not an unsupported claim of Pydux-specific test execution in every backend.

**Deferred UI work:** Root teardown clears queued scheduler dirty-component references and effect runners; the renderer's pending UI callback captures a weak scheduler reference, so a stale unprocessed callback does not by itself own the previous reconciler. Reuse of a reconciler after unmount remains tested. An effect-owned asyncio task has a cleanup that cancels it before delayed completion; this cancellation/retention regression runs under both Cinnamon Python and the installed Rust extension. Application-created tasks must still be associated with explicit cleanup; this does **not** claim PSX can discover or cancel arbitrary unregistered asyncio tasks. Additional native tests deliver already-queued updates *after* unmount in the real Qt binding family, Tkinter and Kivy, asserting no late re-render across eight cycles per backend.

**Development observers:** A stopped polling watcher clears cached paths/pending changes and releases the retained change callback. Delayed Qyro component-refresh operations use a weak reloader reference plus a watcher epoch; they cannot apply after watcher shutdown. These observer regressions are explicitly executed by the native CI core job through `tests/test_devtools.py`, alongside scheduler/hook regressions.

**Scope and exit:** P2.4 covers the tested subscription, delayed callback and development-observer ownership paths. There are no new public component props, events or methods, so a new public-behavior census cell is **N/A**. Native event ownership remains covered by P2.3. Generalized long-duration memory soak, unbounded third-party stores, arbitrary user-managed tasks, Cinnamon caches and graphic resources remain outside this increment. The explicitly deferred prolonged Kivy memory-growth investigation is still a separate owner-approved iteration.


## P2.5 — Cinnamon caches and owned graphics resources

**Executed implementation SHA:** `3b069a6ad2a2d18364bd63b748bbd31fba1d23e1`. All seven workflows concluded `success`: [native selective CI](https://github.com/Neuri-AI/PSX/actions/runs/39831224371) and [integral Grid CI](https://github.com/Neuri-AI/PSX/actions/runs/39831224118). The native regression was run using real Qt, Tkinter and Kivy toolkits. Rust/Python layout differential, Headless/Core and geometry contracts remain covered by their applicable selected or integral jobs, not by assuming a skipped job ran.

**Cinnamon cache lifecycle.** `NativeIntrinsicCache` is renderer-owned and publishes only complete successful rounds. Publication replaces the previous per-widget and width-specific dictionaries, discarding stale widget identities and previous width samples; failed transactions do not publish partial results. Existing renderer teardown explicitly clears intrinsic cache entries, prior solver results, native measurement invalidations and image resource watches. The new 128-round churn/weak-reference tests cover successive identities, width changes, explicit clear and preservation of the previous successful snapshot after a measurement exception. `StyleResolver` already applies an instance-owned finite LRU bound to stylesheet and computed-style entries (two dictionaries, each bounded by `max_entries`), tested with 100 distinct styles and explicit clearing.

**Native Image resources.** A destroyed Qt Image now clears its QLabel pixmap plus its decoded QPixmap source before `deleteLater()`. Tkinter destroys the widget and clears owned Pillow buffers and PhotoImage references even when the Python handle survives; source decoding closes the Pillow source file and failed source/invalid target paths release stale photos. Kivy removes the texture callback, detaches owned Image widgets, clears the renderer invalidation closure and source/props retained on the widget. Twelve live Image mount/unmount cycles per toolkit assert teardown clears the adapter-owned buffers. The fixture is a CRC-valid PNG accepted by the native Tk decoder. `ImageResourceWatch` synchronization and explicit clearing are also verified against 128 old mounted trees using `weakref`.

**Ownership boundary.** Do not clear the framework-global Kivy texture cache or destroy borrowed native widgets: those are managed by Kivy and the external owner respectively. This stage verifies release of PSX-owned resource references, not native allocator RSS returning to baseline, GPU-driver cache eviction, arbitrary third-party widgets or all global toolkit caches. The previously deferred long-duration Kivy memory-growth investigation remains outside this increment. Extended RSS/USS, image churn under prolonged load and cross-platform resource-growth envelopes belong to P2.6.

**P2.5 exit:** Cache publication/eviction and teardown contracts, native owned Image buffers and resource watcher disposal have executable regressions and successful exact-SHA CI receipts. No public API or behavior contracts were added, so a new public census cell is N/A. This is not a claim that all process/global memory has been freed or that multi-hour sessions are certified.
