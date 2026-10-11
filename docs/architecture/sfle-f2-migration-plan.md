# SFLE F2.4 — migration inventory and renderer adapter contract

> **Planning only.** Source inventory audited on `feat/sfle-f2-core` at `fdff39037ad3f0f54fcc445246b17e32637f31a4` (2026-10-10). No public changes to Row, Column, Scroll, exports or the closed capability manifest are permitted until F3.
>
> Authority: [F1 final architecture](sfle-f1-final-architecture.md) §6 **F2.4**, D-F1.1–D-F1.12 and F1-RUST; [SFLE F1 box model](sfle-f1-box-model.md); [F1 contracts](sfle-f1-contracts.md); [typed props](sfle-f1-props-lengths.md). This plan cannot override those requirements.

## Verified F2.4 repository-wide tracked-source search

Executed in [SFLE Core run 38104644634](https://github.com/Neuri-AI/PSX/actions/runs/38104644634), job **F2.4 tracked Row Column Scroll inventory**, at commit `f3028853909ee5dc7b8182147ab5e4337c9f5dfd`. The exact command, also captured with the complete matching-line list in the uploaded CI artifact, is:

```bash
git grep -n -I -E '(^|[^[:alnum:]_])(Row|Column|Scroll)([^[:alnum:]_]|$)' -- psx docs tests examples
```

**Observed: 390 distinct matching source lines** (a line containing multiple names is counted once in this total); separate **case-sensitive token occurrence** counts:

- **Row:** **152 occurrences** / 145 matching lines / 48 distinct files. By scope: psx=38, docs=83, tests=18, examples=13.
- **Column:** **246 occurrences** / 231 matching lines / 74 distinct files. By scope: psx=39, docs=106, tests=78, examples=23.
- **Scroll:** **105 occurrences** / 98 matching lines / 25 distinct files. By scope: psx=36, docs=69, tests=0, examples=0.

Scope is tracked text in `psx/`, `docs/`, `tests/`, and `examples/`; exact case-sensitive, whole identifier matching. It does **not** claim coverage of third-party boilerplate repositories, other branch references, or lowercase `row`/`column`/abbreviated imports. For an F3 removal gate, repeat the search with intentionally broader patterns and generated artifacts/external boilerplates. Counts are **audited at the named commit**, not a claim that the evolving documentation will never alter them. No Row/Column/Scroll implementation, public export or capability manifest was edited during this verification.

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

## Verified external Qyro boilerplate inventory (2026-10-10)

The original repository-only inventory above is a **historical snapshot** (not the current exhaustive scope). [F2.4 external RED test 78016ca](https://github.com/Neuri-AI/PSX/commit/78016cad473221e31519f845fbbc788830254af0) / [Core 38114249063](https://github.com/Neuri-AI/PSX/actions/runs/38114249063) established that the audit could silently ignore external repository arguments and never produce the requested artifact. After correcting a test-fixture comment that itself contained a standalone `Scroll` token, [script d278a3e](https://github.com/Neuri-AI/PSX/commit/d278a3ee7d024edbb387f6f398105931715f1f31) now requires clean, independent tracked Git repository roots, a valid HEAD SHA, and exact per-repository identifier counts. Missing/dirty external checkouts fail closed.

[CI integration cb16d74](https://github.com/Neuri-AI/PSX/commit/cb16d749c245b83dd056cdaa1467b385054731a9) checks out each public external boilerplate at the pinned commit and attaches `inventory.json`, `git-grep-matches.txt`, `external-git-grep-matches.txt`. **[SFLE Core run 38114340439](https://github.com/Neuri-AI/PSX/actions/runs/38114340439)**: F2.4 inventory job success, as well as Python 3.10–3.13 tests for exact external counts and missing-source rejection. External Git commits and observed whole-token `Row`/`Column`/`Scroll` occurrences:

| External repository | Pinned HEAD | `Row` | `Column` | `Scroll` |
| --- | --- | ---: | ---: | ---: |
| [qyro-boilerplate-qt](https://github.com/Neuri-AI/qyro-boilerplate-qt) | `a9d1c65e2afcff3ddd878c8ff8175d423379293b` | 0 | 0 | 0 |
| [qyro-boilerplate-kivy](https://github.com/Neuri-AI/qyro-boilerplate-kivy) | `56da7d54e8323839c080c31658e435a18875c68b` | 0 | 0 | 0 |
| [qyro-boilerplate-tkinter](https://github.com/Neuri-AI/qyro-boilerplate-tkinter) | `2eb3ef8f93aa960137ee31da54c5e6d7e6d297f3` | 0 | 0 | 0 |

This is **source inventory only** for these exact identifiers at these immutable commits. It is not evidence that their runtime widget layout is SFLE-based, that lowercase aliases are absent, or that all F3 migration tasks are done.

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

**F2.4 acceptance state:** the documented current-repository and three pinned external-boilerplate source inventories, exact commands, and CI artifact are verified at their named commits. **F2.4 remains open** because the single-SFLE-authority adapter contract still needs executable enforcement tests and proof of no competing portable geometry; F3 executes the actual native/API migration. This is not grounds to defer F2.2/F2.3 pure Flex sizing/browser requirements to F3.

## F2.4 executable single-authority pre-migration contract — 2026-10-11

The F2 repair branch adds executable evidence without retiring any public Row,
Column or Scroll API. `psx/sfle/adapter_contract.py` now rejects duplicate
native Scroll hosts, duplicate SFLE content roots, missing/non-`Flex` roots,
disposed nodes and obsolete geometry generations. `derive_scroll_content_metrics`
derives scroll extent **exclusively** from the immutable engine-produced content
subtree rectangles and clamps native offsets without modifying the rectangles.
`tests/sfle/test_f2_adapter_authority_certification.py` verifies these rules
using a real Python SFLE compute result. A separate adversarial lifecycle test
detects and rolls back a native layout that overwrites the engine's width.

The real [Qt/Tk/Kivy UI job #38123542899](https://github.com/Neuri-AI/PSX/actions/runs/38123542899)
passed all 11 widget geometry/measurement tests without skips on Ubuntu/Xvfb.
Those are **ports and native widgets**, not evidence that the current legacy
Row/Column/Scroll renderers have stopped performing their own layouts.
Production adapter rewiring and Row/Column removal remain explicitly F3-G1–G5.

## Point 4 final executable certification — 2026-10-11

The historical F2.4 open notes above describe the earlier inventory-only evidence. The independent [point-4 certificate](sfle-f2-point4-final-certification.md) supersedes their status, not the migration plan.

Following RED commit [`73c0b6e`](https://github.com/Neuri-AI/PSX/commit/73c0b6e994b44721f38c39b5c870429de6c2fdf4), `adapter_contract.py` now rejects a crossed Scroll content-root binding supplied without reconciler authority; paired positive/adversarial tests prove nested viewport overflow separation, offset/resize immutability, reversible coordinates and worker-port rollback. [GREEN `33261d5`](https://github.com/Neuri-AI/PSX/commit/33261d50e6585a3c21c91e32664a90705e77b938) received 5/5 mandatory workflows passing on the same source SHA. The approved F2 point 4 is **CLOSED**.

F3-G1–G5 remain unchanged and unexecuted: the F2 contract does not assert that legacy native Qt/Kivy/Tk/Headless production adapters already consume SFLE results, nor that `Row`/`Column` are removed.
