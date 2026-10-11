# SFLE F2.4 — migration inventory and renderer adapter contract

> **Planning only.** Source inventory audited on `feat/sfle-f2-core` at `fdff39037ad3f0f54fcc445246b17e32637f31a4` (2026-10-10). No public changes to Row, Column, Scroll, exports or the closed capability manifest are permitted until F3.
>
> Authority: [F1 final architecture](sfle-f1-final-architecture.md) §6 **F2.4**, D-F1.1–D-F1.12 and F1-RUST; [SFLE F1 box model](sfle-f1-box-model.md); [F1 contracts](sfle-f1-contracts.md); [typed props](sfle-f1-props-lengths.md). This plan cannot override those requirements.

## Existing surface inventory

| Surface | Existing implementation / registration | Migration impact in F3 |
| --- | --- | --- |
| Public imports | `psx/__init__.py` exports `Row`, `Column`, `Scroll` | Delete Row/Column imports and `__all__` entries. Keep Scroll (breaking migration documented); **no aliases or wrappers** |
| Component/markup registries | `psx/core/registry.py` registers `Column`, `Row`, `Scroll`; `psx/core/contracts.py` defines their individual contracts; markup compilation is registry-backed (`psx/markup/`) | One public `Flex` declaration/contract replacing legacy containers; remove Row/Column contracts/registrations, fail unknown tags. Scroll remains a native viewport component |
| Generic prop handling | `psx/renderers/components/column.py`, `row.py`, `scroll.py` | Remove legacy Row/Column prop logic and dependency on their alignment/spacing semantics; typed Flex props resolve in SFLE only. Retain Scroll input/offset props |
| Qt | `psx/renderers/qt/pyqt.py` registers Qt adapters; `qt/row.py`, `qt/column.py` use native QBoxLayout spacing/stretch/alignment; `qt/scroll.py` uses QScrollArea with a native QBoxLayout content container | Eliminate QBoxLayout **as portable Flex geometry authority**; use SFLE rectangles and widget geometry application. Preserve QScrollArea viewport, event routing, scrollbars and offsets |
| Kivy | `psx/renderers/kivy/kivy.py` registers `KivyRowAdapter`, `KivyColumnAdapter`, `KivyScrollAdapter`; `kivy/row.py`/`column.py` use BoxLayout + size_hint; `kivy/scroll.py` uses ScrollView + inner BoxLayout and content minimum size | Remove size_hint/BoxLayout portable sizing semantics from Flex. Native ScrollView retains touch/wheel/overscroll semantics, but content bounds must derive from SFLE, not BoxLayout's hidden sizing algorithm |
| Tkinter | `psx/renderers/tkinter/tkinter.py` registers three adapters; `tkinter/row.py`/`column.py` use `pack()` in repack; `tkinter/scroll.py` manages a Canvas/content Frame, scrollregion, wheel delta, fraction and remainder | Stop `pack()` from positioning portable Flex children; apply SFLE positions consistently. Retain Canvas scrollregion and pixel/remainder event handling, calculated from SFLE content extent |
| Headless | `psx/renderers/headless.py` registers a generic adapter and validates Scroll props | Consume pure SFLE geometry with exact IDs/order and no GUI dependencies; test source/frozen import without Rust |
| Documentation / examples | `docs/components/row.md`, `column.md`, `scroll.md`, `docs/tutorial-adding-portable-widgets.md`, `docs/tutorial-adding-native-widgets.md`, `docs/refactoring/renderer-adapters.md`; `examples/pyside6_markup_counter.py`, `examples/qyro_*_psx_demo`, `examples/qyro_*_pydux_demo` | Search and rewrite all Row/Column markup, docs, recipes and demos during F3. Explicitly document Scroll + nested Flex as breaking replacement; no fallback aliases |
| Current tests | `tests/test_component_contracts.py`, `test_component_registry.py`, `test_markup_registry.py`, `test_markup.py`, `test_renderer_adapters.py`, `test_pyqt_renderer.py`, `test_pyside6_renderer.py`, `test_kivy_renderer.py`, `test_tkinter_renderer.py`; SFLE `tests/sfle/`, `tests/interop/`, `tests/browser/` | Retire legacy container assumptions in F3 and add native geometry commit, event and scrolling regression tests. Keep F2 pure engine tests unchanged |

The inventory above names the definitive **paths and ownership categories**; occurrence counts are deliberately not treated as completeness evidence. Before F3 removal, perform a complete code/docs/examples grep in CI and fail if Row/Column names remain in public API, markup samples or legacy layout authority.

## Renderer-neutral F2 contract to carry into F3

1. **Measure on UI thread.** Adapter measures intrinsic content with constrained width and definite/indefinite axes, preserving `AUTO`, `NONE` and intrinsic keywords as tagged values. Measurement revisions and `generation` are captured in an immutable snapshot. Scroll exposes its native **viewport as constraints**; content bounds are computed separately.
2. **Pure engine boundary.** Backend receives only immutable normalized nodes, styles, intrinsic sizes, available sizes, direction and generation. Rust is selected at load time when available; otherwise Python implements the **same** features, rejections and 0.01px logical geometry. No widgets, VNodes, callbacks or native resources enter the compute transaction. No Python retry if Rust fails after starting.
3. **Width-driven remeasurement.** Engine computes flex targets, requests new UI-thread intrinsic measurements for the used widths, repeats to a bounded fixed point and rejects oscillation with the same diagnostic across both backends. A successful geometry result is never applied from a stale generation.
4. **Atomic current-generation commit.** Renderer validates generation and all node IDs first, applies geometries in a controlled UI transaction, and records `geometry_commit_error` separately from `measurement_error` and `engine_error`. Native integer-pixel rounding may differ within 1.0px but cannot change flex lines, ordering, logical identities or accept unsupported features.
5. **Scroll remains native.** ScrollAdapter owns wheel/touch/keyboard input, scroll offsets, clipping, scrollbars and viewport. An **explicit nested Flex** is the only portable layout root under a scroll content host; SFLE supplies content bounds; the host clamps native offset without recomputing Flex geometry itself. `content_direction` must never become a second native Flex layout authority.
6. **No silent compatibility layer.** `Row` and `Column` are deleted in F3; neither parser aliases, deprecated wrappers nor native automatic fallback layouts are permitted. `Flex` handles LTR/RTL (row/column/reverse/wrap) or emits `SFLE_UNSUPPORTED_FEATURE` with matching IDs/diagnostics in Rust/Python.
7. **Capability gates remain closed.** Do not modify F2 public capability manifest or advertise this adapter plan as current renderer support.

## F3 implementation gates (not F2 code changes)

- **F3-G1**: Add `Flex` declaration, contract and explicit Scroll-with-Flex child policy; prove nested tree normalization and unsupported diagnostics for each renderer.
- **F3-G2**: Wire Qt, Kivy, Tkinter and Headless `measure → snapshot → compute → remeasure → commit` through generation-safe scheduler without native layout ownership. Test 0.01px pure, ≤1px native, stable identities and independent error channels.
- **F3-G3**: Wire Scroll native viewport/scrollregion updates from SFLE content bounds. Preserve offsets across content and viewport updates; verify horizontal/vertical and nested input handling on each toolkit.
- **F3-G4**: Delete Row/Column public exports, registries, contract classes, adapters and old native layout algorithms. Migrate examples, boilerplates, tutorials and tests; add grep/no-alias gate. Keep Scroll.
- **F3-G5**: Verify Windows/macOS/Linux wheels, PyO3 load and fallback when absent, source/frozen imports, Qt/Kivy/Tkinter/Headless parity, RTL/reverse, bounded sizing and complete Chromium oracle.

**F2.4 acceptance state:** inventory and adapter boundaries are documented. **F2.4 remains open as a verified gate** until the inventory-completeness search and contract enforcement tests exist; F3 executes the native changes. This is not grounds to defer F2.2/F2.3 pure Flex sizing/browser requirements to F3.
