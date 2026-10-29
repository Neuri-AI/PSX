# Qt ↔ Kivy parity: source inventory and reproducible baseline

**Audit:** 2026-10-29 · **Repository:** `Neuri-AI/PSX` · **Branch:** `fixes/psx-issues` · **Inspected HEAD:** `24a9a25bd17c28c6019924c5c03968bf5f8fe21b`
**Scope:** The owner-requested *stage 0*, inventory and baseline, comparing Qt (PySide6 reference) with Kivy before further Kivy geometry, CSS, or performance changes.
**Method:** Read the current branch's runtime sources, architecture contracts, test names and implementation bodies, prior audit and owner-submitted native failure. No fresh native process, screenshot, pixel comparison, or same-SHA CI was run as part of this source audit. **Do not interpret source-path existence as runtime parity.**

## 1. Acceptance rule and status vocabulary

Qt is the **acceptance reference for authored CSS and visual presentation**, not a license to copy its theme or hardcode colors. For every comparable input, inspect six independent dimensions:

1. **Authoring/AST:** same PSX Markup or public VNode, keys and supported attributes.
2. **Computed style:** same cascade, inheritance, precedence and specified-value provenance.
3. **Canonical geometry:** identical logical content/padding/border/margin and Cinnamon rectangles, subject to bounded native measurement differences.
4. **Native presentation:** equivalent visible background, text, outline, corner, clipping and selected/disabled state, with native rendering differences reported.
5. **Interaction:** event, focus, selection, editing, scroll, ref/native handle and keyed reconciliation.
6. **Ownership:** clean teardown, no lingering native subscriptions, old canvas resources, or stale geometry callbacks.

**Status:** `E` = evidenced implementation/test path **only** (NOT independently re-run at this SHA); `P` = partial scope or known exclusions; `D` = observed defect; `U` = unverified native/visual parity; `NA` = contractually not applicable. An E in two columns **never implies** cross-backend visual equivalence. Historical certified subsets apply only to their own exact SHA and operations.

### Scope and out of scope

The inventory covers existing public controls, CSS Core, Grid/Flex/Flow/Scroll, viewport events, native extensions, state and teardown. Do not implement renderer changes or optimize to 60 FPS in this stage. The separately introduced 1,000-element benchmarks are **diagnostic tooling for stage 6**, not a criterion for closing stage 0. Do not broaden the CSS support contract to complete browser CSS, CSS Grid tracks, universal child clipping, or nonexistent native control surfaces.

## 2. Exact source map

| Boundary | Common implementation | Qt | Kivy |
| --- | --- | --- | --- |
| Public markup and tree | `psx/core/vnode.py`, `psx/markup/`, `psx/core/reconcile.py` | same tree | same tree |
| CSS resolution | `psx/css/parser.py`, `properties.py`, `cascade.py`, `markup.py` | shared computed style | shared computed style |
| Native CSS projection | `psx/css/native_paint.py` | `psx/renderers/qt/pyqt.py::apply_css/_apply_css_projected` | `psx/renderers/kivy/kivy.py::apply_css` |
| Core mounted native geometry | `psx/sfle/native_layout_snapshot.py`, `native_measurement.py` and Cinnamon | Qt renderer `commit_layout` | `psx/sfle/kivy_layout_bridge.py::commit_kivy_sfle` |
| Grid/Mixed composition | `psx/sfle/grid_native_composition.py`, `grid_native_commit.py`, `mixed_grid_native.py` | `GridCommitBackend.QT` | `GridCommitBackend.KIVY` and parent-height inversion |
| Resize/invalidations | `psx/sfle/native_measurement_invalidation.py` | `QtRenderer._sfle_on_viewport_resize/_sfle_flush_viewport_resize` | `KivyRenderer._sfle_on_root_size/_sfle_on_window_resize/_sfle_flush_viewport_resize` |
| Native components | `psx/sfle/native_component_capabilities.py`, shared component builders | `psx/renderers/qt/` | `psx/renderers/kivy/` |
| Keys/events/disposal | `psx/core/reconcile.py`, native event subscriptions | Qt signal/filter lifecycle | Kivy property/Clock/Canvas/KV binding lifecycle |
| Conformance and cases | `tests/test_mounted_grid_native_renderers.py`, `tests/test_native_component_matrix.py`, `tests/test_native_component_capabilities.py` | `tests/test_qt_native_component_lifecycle.py`, `tests/test_pyside6_native_layout.py` | `tests/test_kivy_native_layout.py`, `tests/test_kivy_renderer.py` |

All paths above were verified in the inspected branch or linked from inspected implementation/docs. The source tree routes Kivy native Grid through the same Cinnamon math; it is **not** a separate geometry solver.

## 3. Component-by-component capability inventory

This table distinguishes a code/test route from an executed comparison of native visual output. Component combinations marked P are explicitly bounded by the existing component inventory or contract. Native `Input`/editing widgets also have backend-specific behavior even when their state contract is shared.

| Component / family | Qt source/test route | Kivy source/test route | Parity result and missing evidence |
| --- | --- | --- | --- |
| `Text`, `span`, `p`, headings | E: QFont/QTextDocument, native CSS tests | E: Label, font/texture measurement, native CSS tests | **P/U** text raster, baseline, line wrapping, font fallback, 100–900 weight |
| `Button` / `button` | E: QPushButton/QSS state, typography, radius | E: native Button, owned canvas round fill/stroke | **P/U** actual pixel comparisons; hover/pressed/focus, reset and clipping |
| `Input` / `input` | E: QLineEdit-like native editing and CSS tests | E: TextInput, selection/edit callback tests | **P/U** native caret, selection, focus, height-for-width, border/padding |
| `TextArea` / `textarea` | E: editable multiline, measured text | E: Kivy TextInput, reflow/update tests | **P/U** real text wrapping/leading, scroll internal/editor states |
| `Checkbox` | E: Qt native control | E: Kivy CheckBox + native styling path | **P/U** Kivy checkbox has no portable text color; checked indicator theme differs |
| `Radio` / `RadioGroup` | E: native radio group/selection | E/P: radio group tests; inventory notes specific SFLE intrinsic limitations | **P/U** group layout, label styling and click/keyboard state equivalence |
| `Select` | E: native combobox and selection | E: Kivy Spinner and callbacks | **P/U** native popup and selection states, content shape and keyboard |
| `Slider` | E: native value and geometry routes | E: Kivy Slider and value route | **P/U** track/thumb painting and value readback across resizes |
| `Switch` | E: Qt switch adapter | E: `psx/renderers/kivy/switch.py` | **P/U** states and CSS surface compared visually |
| `SpinBox` | E: Qt spinbox adapter | E: `psx/renderers/kivy/spinbox.py` | **P/U** edited value/keyboard and native paint |
| `ProgressBar` | E: Qt progress adapter | E: Kivy progressbar adapter | **P/U** color/track/progress geometry in actual screenshots |
| `Image` | E: Qt image adapter and resource invalidation | E: Kivy image adapter and image revision/intrinsic tests | **P/U** decoding/scaling/aspect/alpha and late invalidation |
| `Divider` | E: Qt divider adapter | E: Kivy divider adapter | **P/U** thickness/positions/label and responsive bounds |
| `Spacer` | E: native geometry path | E: Kivy native geometry test | **P/U** allocation under different constraints |
| `Link` | E: Qt link adapter, state styles | E: Kivy Link adapter and click paths | **P/U** keyboard/click affordance, visual foreground and enabled |
| `Badge` | E: custom Qt paint; general QSS border excluded | E: Kivy Badge/native foreground and owned stroke | **P/U** bounded border semantics, pixel mask; no Badge click event |
| `Box`, semantic `div` | E: QWidget/semantic local QSS | E: Kivy native host/canvas `before` surface | **P/U** paints behind arbitrary descendants, corners, transparent parent |
| `Flex` / row/column contexts | E: Cinnamon native SFLE adapter | E: Kivy native SFLE adapter | **P/U** nested intrinsic wrapping/readback, 100% units and feedback loops |
| `Grid` / `GridItem` | E: 12-column Cinnamon placements | E/D: Kivy Grid commit with strict negative-Y rejection | **D** owner-observed `GridPackingError` on resize, stage 1 blocker |
| `Scroll` | E: Qt scroll host and offset tests | E: Kivy ScrollView, offset/edge chaining, rollback tests | **P/U** clipping, nested overflow under repeated resize, restoration |
| `Native`, custom `@native_adapter` | E: owned/borrowed external geometry port routes | E: Kivy borrowed/native ownership tests | **P/U** only framework-compatible native instances; external intrinsic and teardown |
| `Fragment`/functional components | E: reconciler/native root tests | E: corresponding native mounted tests | **P/U** keyed identity, multi-root behavior at exact SHA and widget hierarchy |

**Important inventory reconciliation:** older 2026-10-27 Qt/Tk/Kivy audit described Kivy side borders as a gap; the current branch's `tests/test_mounted_grid_native_renderers.py` contains `test_native_css_bottom_border_matches_qt_tk_and_kivy_without_other_sides`, `test_rounded_bottom_only_border_updates_without_painting_other_sides`, and `test_rounded_side_border_without_opaque_fill_preserves_backend_bounds`. That is **newer source evidence for a tested operation**, not independent proof of visible native pixels. Mark **E/U**, not categorically absent. Preserve exact supported subset and inspect implementations when debugging.

## 4. Property-by-property CSS and geometry inventory

| Property/feature | Shared contract or path | Qt projection | Kivy projection | Stage-0 assessment |
| --- | --- | --- | --- | --- |
| class/id, cascade, specificity, inherited color | Shared resolver tests `tests/css/`, `tests/test_markup_css_binding.py` | computed → QSS/native | computed → native/canvas | **E/U** same author input expected; fresh case-by-case computed-style diff absent |
| `display`, block/inline/Flex and `gap` | CSS geometry and Cinnamon | native commit | Kivy SFLE commit | **E/U** complex mixed nesting not visually certified |
| `width/height`, min/max, percent, viewport units | CSS geometry with definite constraints | Qt native readback | Kivy native readback | **E/U** owner-reported viewport problems require targeted stage-1 tests |
| `padding`, `margin`, `border-width` box geometry | canonical box-style in Cinnamon | applied logical boxes | applied logical boxes | **E/U** widget-specific intrinsic conflicts not exhausted |
| `color` | `foreground_rgba/hex` | native foreground/QSS | Label/TextInput/etc. native color | **P/U** alpha and component exceptions |
| `background-color` | `background_rgba/hex` | semantic QSS and some controls | `canvas.before` / owned control fill | **P/U** full controls and actual pixels not guaranteed |
| `border-{side}`, thickness/color | `native_side_border_paint` | QSS sides | canvas/owned edges in applicable hosts | **E/U** new tests exist, native screenshot fidelity unmeasured |
| `border-radius` | bounded positive/zero px radius | QSS rounded surface | rounded canvas fill/stroke | **P/U** per-corner/percent radius and child clipping excluded |
| `font-family` | native typography/provenance | QFont native stack | available Kivy font resource | **P/U** fallback differs by installed fonts |
| `font-size` | positive-px native subset | Qt font | Kivy `font_size` | **E/U** native font metrics/DPR not normalized |
| `font-weight` | bounded native typography | more nuanced QSS where supported | binary bold/normal in shared path | **P/U** do not promise 100–900 visual equivalence |
| `line-height` | bounded native text measurement | document/native metrics | Kivy ratio/texture | **E/U** Kivy multiline tests exist, comparison absent |
| `text-align` | left/center/right subset | native alignment | `halign`/native alignment | **P/U** justified text excluded |
| CSS remove/reset, inherited update | keyed reconciler reapplication | QSS/style reset | canvas instructions/unbinding | **E/U** native teardown tests exist; live screenshot diff not supplied |
| hover, focus, disabled, selected | per-component native state | Qt native/QSS states | Kivy native event/texture | **P/U** not a single universal CSS pseudo-state contract |
| `overflow`, clipping/Scroll | approved restricted subset | Qt clip/scroll hosts | Kivy ScrollView/clip | **P/U** arbitrary universal browser CSS overflow not supported |
| image resource/Font DPI update | intrinsic/cache invalidation | Qt measurement reflow | Kivy texture reflow | **E/U** device-specific timing and font metrics not compared |

The bounded native CSS certification in `docs/architecture/css-core-integral-certification-matrix.md` explicitly says its prior SHA **did not certify cross-OS screenshot parity**. Do not elevate previous CI or a passing unit test into the stage-3 visual acceptance gate.

## 5. Confirmed failure evidence versus hypotheses

### G-01 — Kivy Grid parent-height/Y inversion failure (**confirmed observed; root cause unresolved**)

Owner's Arch Linux/SDL2 native run previously reported:
`GridPackingError: Grid rectangle exceeds Kivy parent content height.`
Call chain: `KivyRenderer._sfle_flush_viewport_resize` → `commit_kivy_sfle` → `MountedMixedGrid.commit` → `commit_grid_native_geometry`.

Current source computes `local_height - placement.y - placement.height` for Kivy and raises for **any negative resulting Y**, even though bottom-left coordinates and overflowing content can legitimately require an off-parent negative Y. Separately, `grid_native_composition.py::compose_geometry_batch` propagates `parent_height` and `placement.used_height` through nested structures. **Neither the inversion check nor parent-height selection is proven to be the sole root cause.** The stage-1 work must reproduce and identify whether the position is invalid, overflow is legitimate, or the wrong containing block/height was used. Do not remove checks globally or clamp Y to zero as a cosmetic workaround.

### G-02 — Kivy responsive layout visual discrepancy (**owner observed; not numerically characterized**)

Prior screenshots showed unusable/blank or overlapping Kivy content and white areas; Qt is the requested reference. No paired identical-state, same-size, fixed font/DPR raster data or native readback ledger is in this stage-0 audit. File a **visual mismatch requiring measurements**, not a quantitative pixel-parity score.

### G-03 — Native CSS geometry/paint equivalence (**partial and unverified**)

The current tests include native border sides, CSS controls, scrollbar, font state and invalidation. Contract scope remains bounded. Specific native differences in typography, control backgrounds, inherited font resources and clipping require stage 2/3/4 evidence. Avoid asserting every CSS property renders identically because a single source resolver feeds both renderers.

### G-04 — Benchmark harness failures (**confirmed tooling defects; not engine regressions**)

User-provided 2026-10-29 logs show **all 12** repeat cells failed before any valid sample was produced. Qt failed at scene creation because `Scroll.width` conflicts with `layout_width`. Kivy's own argument parser intercepted `--adapter`. The `report.json` contains no successful cell or geometry result. The former failure paths were corrected in `benchmarks/kivy_qt_mixed_resize.py` at `24a9a25`; **there is no new successful native output proving the fix**. Neither errors nor report support a Qt-vs-Kivy performance conclusion.

### G-05 — Kivy retained heap growth (**historically measured; owning leak unresolved**)

`docs/architecture/P0_KIVY_THREE_ARM_FINDINGS.md` records 500→5,000-cycle RSS deltas of 15,659,008 B direct Kivy, 15,720,448 B PSX without Cinnamon and 52,834,304 B PSX with Cinnamon. These are **historic run-specific measurements**, not current-HEAD benchmarks, and they do not prove that the Rust solver is leaking. Attribution to retained ownership graphs is pending for stage 7.

## 6. Existing tests and executable verification map

| Surface | Concrete tests already in repository | Still missing to certify this particular parity effort |
| --- | --- | --- |
| Grid nesting, responsive breakpoints, native commit and rollback | `tests/test_mounted_grid_native_renderers.py`: `test_nested_grid_survives_a_tiny_viewport`, `test_grid_inside_scroll_flex_preserves_native_offsets_and_reflows`, `test_mixed_flex_grid_transaction_failure_restores_all_native_geometry`, `test_native_grid_root_late_resource_invalidation_is_atomic` | Reproduction of owner exact failing Grid + repeated live resize at Arch/Kivy/Rust and Python; per-rect diagnostics |
| Kivy root/SDL2 geometry and resize | `tests/test_kivy_native_layout.py`: `test_native_root_and_sdl2_window_resize_automatically_reflow_sfle`, `test_real_kivy_native_bottom_left_geometry_and_reconciliation` | Paired identical Qt/Kivy geometry vectors across multiple viewport thresholds |
| Kivy native control and keyed operations | `test_all_ported_builtin_lifecycles_keep_native_widget_handles`, `test_all_callback_controls_rebind_without_native_remount`, `test_external_ownership_owned_native_and_custom_adapter_cleanup` | Shared scenario observable value/event/focus comparison and unmount leakage check |
| Scroll and nested offsets | `test_native_kivy_wheel_and_nested_edge_chaining`, `test_scroll_native_kivy_failure_restores_offsets`, `test_scroll_overflow_native_extent_and_logical_offsets` | Same viewport, scroll position, clipping screenshot sequence |
| Native CSS paint and state | `tests/test_mounted_grid_native_renderers.py` covers CSS foreground, background reset, rounded strokes, one-sided borders, controls, textarea/select and font updates | Actual native capture with pixel/color/geometry overlays |
| Public component matrix | `tests/test_native_component_matrix.py`, `tests/test_native_component_capabilities.py` | Exact-SHA executed per-backend receipts and confirmation of unsupported/NA cells |
| Resize performance probes | `benchmarks/grid_resize_interactive.py`, `benchmarks/native_resize_scaling.py`, `benchmarks/kivy_qt_mixed_resize.py`, `benchmarks/kivy_qt_resize_matrix.py`, `benchmarks/kivy_qt_paced_resize.py` | Valid native results for Kivy and Qt; rendered-frame data not obtainable from event-to-commit timers |

Suggested commands when an appropriate native UI host is available, in **separate GUI processes**, after recording the exact SHA:

```sh
# Existing native Kivy regression tests (real SDL2 window provider required).
python -m pytest -q tests/test_kivy_native_layout.py tests/test_kivy_renderer.py

# Shared mounted native Grid/Flow tests; set one renderer per process.
PSX_GRID_BACKEND=kivy python -m pytest -q tests/test_mounted_grid_native_renderers.py
PSX_GRID_BACKEND=qt PSX_QT_BINDING=pyside6 python -m pytest -q tests/test_mounted_grid_native_renderers.py

# Confirm published selector behavior (not a substitute for native execution).
python -m pytest -q tests/test_ci_impact.py tests/test_native_component_matrix.py
```

For Kivy subprocesses pass `KIVY_NO_ARGS=1`. On Ubuntu CI provision SDL2 native window dependencies + Xvfb as needed, but remember offscreen event-loop timings **do not validate compositor FPS**. Record actual toolkit version, driver, display server, DPI, fonts, OS and physical device, rather than just operating-system name.

## 7. Reproducible parity fixture (stage-1 input contract, not a passing test)

Use one immutable scene with deterministic keys and user-authored colors, using the same authored PSX markup/styles on both adapters:

- **Geometry:** root sidebar + main page; nested Flex → Grid → Flex → Grid; columns and breakpoints, intrinsic text wrapping and explicit widths/height, Scroll containing long content, 0–2px borders and radius; seeded content to ensure overflow is exercised.
- **Controls:** one instance of each portable native family from table 3, enabled/disabled and selected/unselected, with `Native` only where the respective Qt/Kivy extension is genuinely compatible.
- **CSS:** explicit and inherited foreground, background, font size/weight/family, border radius, side-specific edges, dimensions and padding; do not rely on native default theme colors to prove authored fidelity.
- **Viewport:** fixed height 680 logical px; widths `480,560,640,700,820,900,760,600,510` in that order; add 1px steps across responsive breakpoints and abrupt reversals to reproduce native resize races.
- **Snapshots:** full resolved style fields plus provenance; all Cinnamon border/content rects, measured intrinsic dimensions, native widget rects normalized to top-left, one screenshot per width/state/font/DPR plus explicit snapshot metadata.
- **Invariants:** geometry readback ≤1 logical px when contracted; no stale generation/parent-height mismatch; no loss of mounted identity, callbacks, scroll offsets or event subscriptions on unchanged keyed widgets. Full native visual score requires **same authored state** and OS-specific antialiasing tolerance documented beforehand.

This is a **specification of the common fixture**; the present source audit does not claim the fixture already runs. Keep high-load 1,000-item tests as supplemental performance/scale probes, not a substitute for this smaller diagnostic layout.

## 8. Stage-0 disposition and prioritized handoff

**Source inventory completed (this document).** All 22 component/family rows and 18 property/behavior rows have explicit code/test routes and truthful limitations. The previous Qt/Tk/Kivy CSS audit, historical CSS certification and Kivy memory evidence were reconciled without upgrading old results to current-HEAD PASS.

**Evidence gate is OPEN, not closed:** no fresh Qt/Kivy native pair, pixel proof or same-SHA CI ran during this inventory. The immediate next engineering deliverable is the **stage-1 minimal Kivy Grid parent-height/Y reproducer**, with a Qt/Rust and Python control case, on `fixes/psx-issues`. Start from G-01, obtain geometry vectors and only then correct the actual owner of inconsistent coordinates/overflow. Stage 2 CSS and stage 3 native paint follow geometry; stage 6 60 FPS and stage 7 memory must not displace geometry fixes.

**No public capability added; public behavior census: N/A.** This is docs-only: no runtime behavior changed by this file, and CI impact selection must remain documentation-only. No merge to `develop`.

## Reference inventory

- `AGENTS.md`; `docs/architecture/velto-master-execution-plan.md`; `docs/architecture/CONTRACTS_INDEX.md`; `docs/architecture/ARCHITECTURE_APPROVAL.md`.
- `docs/architecture/qt-reference-css-visual-parity-audit.md`; `docs/architecture/css-native-component-capability-inventory.md`; `docs/architecture/css-native-visual-paint-contract.md`; `docs/architecture/css-core-integral-certification-matrix.md`.
- `docs/architecture/canonical-geometry-integration-contract.md`; `docs/architecture/cross-platform-support-audit.md`; `docs/architecture/P0_KIVY_THREE_ARM_FINDINGS.md`.
- Current-branch sources and tests shown throughout tables 2 and 6, inspected against the pinned read-only head.
