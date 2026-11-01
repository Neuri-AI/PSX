# Cinnamon API migration and compatibility boundary

The old `psx.sfle` package was intentionally removed. Its 33 root exports
have been assigned to `psx.layout`, retaining the public names, including
the `LayoutEngine` and `UnsupportedLayoutFeature` symbols. The Python engine
and toolkit workers are exported lazily, so importing `psx.layout` does not
load the fallback.

Use `psx.layout.engine.backend.load_layout_engine` and the immutable
`psx.layout.contracts` interfaces. Grid and source-preserving inline text
have neutral entry points in `psx.layout.grid.solver` and
`psx.layout.inline.semantic_inline_text`. If an engine is omitted, these
entry points negotiate Rust first.

## Python-only historical APIs

These entry points work with historical Python numerical tree types. They
remain available **only with the Python numerical fallback present**:

- `runtime.recursive_measurement.measure_resolved_margin_tree`
- `runtime.recursive_pipeline.compute_recursive_pipeline`
- `runtime.native_lifecycle.layout_and_commit`
- `runtime.remeasurement.plan_remeasurement` (uses Python `UsedSizeTree`)
- `projection.display_context.layout_measured_children` (uses `BlockItem`/`InlineAtom`)

These are not called by the modern Rust engine. They are retained for explicit
legacy Python consumers, not advertised as cross-engine APIs. A Rust-only
consumer that needs their behavior must build the shared immutable layout
snapshot and call the native engine. The seven `psx.layout.compat.native_*`
modules are deprecated development/test aliases into `tests.certification`.
That test package is intentionally absent from installed PSX wheels; these
aliases are **not application runtime APIs**.

## Real capability manifests

`EngineCapabilities.features` means an implemented bounded kernel.
`certified_features` is the subset covered by explicit regression and/or
differential tests. `status()` distinguishes "certified", "implemented"
and "unsupported". Optional Grid/inline Rust features are advertised only
when their PyO3 entry points are installed. The historical empty placeholder
`CONTRACT_ONLY_CAPABILITIES` is retained for compatibility but is no longer
returned by the actual engines.

`block_flow_measured` and `inline_flow_measured` are finite normal-flow
grammars using renderer-supplied metrics, not a browser implementation.
`grid_12_columns` is the PSX twelve-column allocator. The inline text
capability is limited to LTR `white-space:normal` fragment placement.
Full bidi, complex shaping, floats, unsupported CSS and any untested native
UI conditions are *not* advertised.

## Acceptance policy

The Rust-only workflow physically removes the fallback and tests the actual
native wheel plus Qt/Tk/Kivy. The historical suite (`tests/sfle`), Rust
core tests, and exact Rust/Python differential suite must be triggered by
the active PR base, not only PRs targeting `main`. An approved test corpus
proves its declared inputs and contracts; it is not a universal proof for
every possible CSS combination.

## Engine-wide parity gate

The shared `LayoutEngine` protocol requires all five public numerical
operations: complete snapshots, provisional snapshots, incremental snapshots,
12-column Grid, and source-preserving inline text. Differential certification
runs the **actual installed Rust wheel** against the independent Python solver
using identical immutable snapshots and metrics. It compares entire
`LayoutResult` objects, or matched `SFLEError` code and node identity.

The suite `tests/interop/test_cinnamon_engine_wide_parity.py` covers all
30 historical F2 cases in full/provisional/incremental modes, versioned
updates, changed dimensions, changed native measurement revisions, multiround
intrinsic convergence, RTL, offsets and min/max in Grid, plus a fixed-seed
Flex property corpus covering direction/wrapping/alignment/margins/gaps.
`tests/architecture/test_rust_only_layout.py` invokes every shared public
operation after physically deleting the fallback directory.

The declared certification scope is this bounded protocol and the tested
input families. `reused_contexts` is implemented by both engines and reports their actual
incremental subtree reuse. Rust's PyO3 boundary emits a real native reuse
receipt; the differential suite asserts identical receipts on 100 successive
updates and Rust-only tests verify the receipt with Python absent.
Privately-owned legacy Python recursive solver APIs are still outside the
shared numerical protocol. The manifest does **not** promise CSS/browser
conformance or equivalence on unsupported features.

