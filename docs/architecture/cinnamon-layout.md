# Cinnamon layout architecture

## Ownership and non-negotiable dependency direction

Cinnamon is the **geometry authority**. PSX supplies semantic VNodes, CSS
resolution, native intrinsic measurements, and native widget commits. None of
these integrations belongs inside a numerical layout engine.

```text
psx.core / psx.markup / psx.css
    ↓
psx.layout.projection → psx.layout.contracts
    ↓
psx.layout.engine.backend (load-time selector)
    ├── _sfle_native            Rust: primary and independent
    └── psx.layout.fallback     Python: optional, loaded only if selected
    ↓
psx.layout.runtime / psx.layout.grid / psx.layout.inline
    ↓
psx.renderers.{qt,tkinter,kivy} / psx.renderers.headless
```

The layout contract uses signed **1/64 CSS pixel** fixed-point geometry,
stable node identities, immutable snapshots, native intrinsic measurements,
and explicit unsupported-feature errors. The Rust and Python numerical
kernels must have independently executed differential tests.

### Package inventory

| Location | Ownership |
|---|---|
| `rust/cinnamon-core/src/` | Native Rust numerical kernels: Flex, Block/Inline, Grid and inline fragments |
| `psx/layout/contracts/` | Shared input/output models, fixed-point/wire, errors, engine protocol, Grid identity |
| `psx/layout/engine/` | Rust PyO3 adapter and load-time optional fallback selection |
| `psx/layout/fallback/` | Optional Python numerical implementation; *not* required for the Rust engine |
| `psx/layout/projection/` | VNode and CSS projection into immutable Cinnamon input |
| `psx/layout/runtime/` | Measurement transactions, caching, generations, UI-thread and scheduling |
| `psx/layout/grid/` | Grid-to-solver dispatch, planning, and nested native component orchestration |
| `psx/layout/inline/` | Stable source inline fragments, native glyph measurement/painting delegation |
| `psx/layout/scroll/` | Toolkit-independent Scroll offset and viewport contracts |
| `psx/layout/adapters/` | Shared geometry commit and Headless/host integration |
| `psx/renderers/*/inline_paint.py` | Qt/Tk/Kivy widget-owned inline painting |
| `psx/renderers/*/inline_measurement.py` | Toolkit-owned font metrics |
| `psx/renderers/*/scroll_host.py` | Toolkit-owned native Scroll widgets/offsets |

The original `psx/sfle` directory was removed; it is not an alias, runtime
package, or fallback path. Every import must refer to the new owner.

### Rust-only acceptance

CI workflow `.github/workflows/cinnamon-rust-only.yml`:

1. Build a **real** `_sfle_native` wheel using maturin (never a mock).
2. Install that wheel and remove `psx/layout/fallback/` from the filesystem.
3. Verify `psx/sfle/` does not exist and no fallback modules were imported.
4. Run actual Flex, Block, Inline, Grid and nested Grid/Scroll composition
   in `tests/architecture/test_rust_only_layout.py`.
5. Run genuine Qt/Tk/Kivy paragraph + Button layout and resize under Xvfb.
6. Check that there are no eager imports of Python fallback from integration
   with `scripts/check_cinnamon_fallback_edges.py`.

`.github/workflows/semantic-inline-fragments.yml` separately executes the
actual Rust wheel, the Python alternative and their same-input differential
suites for inline fragments, Block/Inline and Grid.

### Failure policy

- Missing Rust extension: select Python **once**, if Python fallback exists.
- Rust installed but ABI/version is incompatible: **error**, not Python fallback.
- Rust compute fails: propagate the native diagnostic, do not retry using Python.
- A renderer must never calculate missing CSS geometry using native layout
  managers; it may measure glyph sizes and commit the final rectangles.
- Fragment/source identity is preserved: a word-wrap fragment is **not** a VNode.
- No generic backend import may eagerly import Qt, Tk and Kivy simultaneously.
- Contracts must not import `psx.layout.fallback`.

### What is not claimed

The differential corpus verifies exact geometry **for the supplied identical
input snapshots and intrinsic metrics**. It is not proof of equivalence for
every future CSS property, Unicode shaping mode, unsupported formatting
context or all possible native UI conditions. Extend the fixture corpus and
backend native tests when adding new capabilities. Legacy recursive
measurement compatibility APIs that only serve the Python numerical pipeline
must not be invoked in Rust mode.

Keep the feature branch and PR draft until every required workflow is green,
including Rust-without-fallback, native Qt/Tk/Kivy, pure Python, Rust core,
and per-feature differential parity.
