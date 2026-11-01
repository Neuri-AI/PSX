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

## Historical recursive APIs with engine selection

The three historical runtime functions `measure_resolved_margin_tree`,
`compute_recursive_pipeline`, and `layout_and_commit` now accept an
optional `engine` argument. They use the selected native Rust or independent
Python numerical kernel while sharing UI-thread measurements, typed tree
contracts and convergence/commit policy. With `engine=None`, the runtime
selects Rust when the native wheel is available.

All 19 historical tree, margin, alignment and intrinsic dataclasses/enums
have one stable identity under `contracts.recursive_tree`; old imports from
`fallback` still reference those same objects.

`runtime.recursive_geometry.compute_margin_tree` dispatches to the Rust
`margin_tree.rs`/`auto_cross_tree.rs` kernels through
`_sfle_native.compute_recursive_tree_json`, or to the Python
`fallback.margin_tree`/`fallback.auto_cross_tree` algorithms.
`runtime.recursive_preparation` handles only pure intrinsic metadata
adaptation. Native/widget measurement and committing geometry remain owned
by the shared coordinator, not the Rust numerical engine.

The `recursive_resolved_flex` capability is advertised for Rust only when
that native ABI is present. Real-wheel differential tests cover exact
geometry, UI measurement requests and iterative convergence; a separate
Rust-only test physically removes the Python fallback and exercises all
three historical functions. Certification applies to the bounded tested
grammar, not every possible CSS tree. The seven `psx.layout.compat.native_*`
modules are deprecated development/test aliases into `tests.certification`.
That test package is intentionally absent from installed PSX wheels; these
aliases are **not application runtime APIs**.

## Historical APIs migrated to fallback-independent layers

The following historical interfaces are **not** Python-only:

- `runtime.remeasurement.plan_remeasurement` accepts
  `contracts.used_size.UsedSizeTree` directly, without importing the fallback.
- `runtime.constraint_propagation` owns `ChildSizing`, the child
  constraint resolver, and both styled/used-box measurement planners.
- `projection.size_resolution` owns CSS length resolution and its enums.
- `projection.box_sizing` and `projection.used_size` own CSS box sizing
  and definite content-size resolution.
- `projection.used_size_tree.propagate_definite_used_sizes` computes
  declared, definite, preorder CSS reference sizes without importing
  the optional numerical engine.

Import paths in `psx.layout.fallback` remain backward-compatible
re-exports of the **same** class/function objects. All five operations
are tested both with the fallback present and physically removed. They
belong to CSS projection and measurement orchestration, not the native
Cinnamon numerical geometry solver.

## Remaining legacy numerical compatibility boundary

Historical `MarginTreeNode`, `MarginFlexItem`, intrinsic leaf, and
auto-cross typed-tree computation must not be silently redirected through
the Python fallback when the Rust engine is selected. The current Rust
snapshot-native compute API is independent, but exact binary compatibility
with those old Python-only typed-tree signatures is **not yet proven**.
Do not label those historical operations as Rust-certified until their
inputs/types are shared and both implementations pass strict differential
fixtures.

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

## Backend-neutral measured Block / Inline atom placement

`layout_measured_children` now dispatches through
`psx.layout.flow.solver`, taking `BlockItem` and `InlineAtom` from
`psx.layout.contracts.flow` rather than the numerical fallback.
The historical `psx.layout.fallback.flow_layout` names are re-exports
of those same immutable data records for existing Python consumers.
Rust invokes independent compiled `flow_layout.rs` functions using
`compute_measured_flow_json`; Python calls its own numerical implementation.
The native wheel's ABI is exposed as `measured_flow_primitives` only when
actually installed. Differential tests compare 256 seeded block and 256
seeded inline atomic cases with source identity and exact geometry;
Rust-only tests exercise the historical entry point after fallback removal.

