# Kivy ↔ Qt CSS Core projection: stage 2 verification

**Verification date:** 2026-10-29
**Implementation SHA:** `96046c5e6ca412211ea980440e813245191a4774`
**Branch:** `fixes/psx-issues`
**Reference renderer:** PySide6 / Qt
**Scope:** Stage 2 CSS Core (source parsing, cascade, immutable computed values, geometry/paint partition and supported Kivy projection). This is **not** stage 3 cross-platform screenshot or font raster parity.

## Architecture and source contract

- PSX resolves CSS through the shared `psx/css/parser.py`, `cascade.py`, `properties.py` and `geometry.py` pipeline. Kivy and Qt receive the same immutable `ComputedStyle` metadata; neither renderer owns an independent cascade.
- CSS width, height, min/max, padding, margin and border-width are translated into typed Cinnamon input by `css_layout_overrides()`. Percent and viewport values must be resolved by the shared layout stage, rather than toolkit-specific heuristics.
- `psx/renderers/qt/pyqt.py::apply_css` and `psx/renderers/kivy/kivy.py::apply_css` consume the native subset of shared projected values. Renderer-local appearance, resource availability and typography are separate stage-3/native obligations.
- The Kivy CSS typography reset now refreshes its component-prop baseline on subsequent native updates instead of restoring the first mounted Button size; regression is in `tests/test_kivy_renderer.py::test_css_button_font_reset_respects_updated_component_prop`.
- Shared CSS acceptance cases cover source precedence, explicit zero values, two-value padding, CSS dimensions, margin/border content boxes, viewport units, and dynamic geometry identity in `tests/css/test_geometry_handoff.py`. Kivy mounted tests additionally cover authored heights, font size, padding, resize and widget identity.

## Executed exact-SHA CI

Workflow run [40989226919](https://github.com/Neuri-AI/PSX/actions/runs/40989226919) **completed successfully on SHA `96046c5`**. These are executed jobs, not only test paths:

| Job | Result | Relevant execution |
| --- | --- | --- |
| Native layout core and registry | PASS | `tests/css/*`, geometry handoff, inheritance, CSS markup, capability registry |
| Native layout Kivy native components | PASS | Xvfb/SDL2 `tests/test_kivy_renderer.py`, `tests/test_kivy_native_layout.py`, shared mounted native grid renderer tests |
| Native layout Qt native components | PASS | PySide6 native layout, QSS background and semantic border regression |
| Native layout SFLE geometry contracts | PASS | `tests/sfle` |
| Native layout Rust and Python differential | PASS | Differential geometry regression |
| Native layout change-router regression | PASS | CI path-impact selection |
| Native layout public behavior evidence aggregate | PASS | Required public capability evidence gate |
| Native layout required CI conclusion | PASS | Workflow aggregate gate |

The same SHA also passed [Native reactive contract](https://github.com/Neuri-AI/PSX/actions/runs/40989226929) and [Pydux coordinated hot reload regression](https://github.com/Neuri-AI/PSX/actions/runs/40989226913).

## Stage disposition and exclusions

**Stage 2 CSS Core acceptance: PASS for the implemented, bounded CSS subset and the executed Linux native test configurations above.** The source and tests establish a shared computed-style and geometry pipeline and verify native application of the test-covered subset, not pixel identity.

**Not certified by this stage:** OS/theme/DPR screenshot fidelity, custom font availability and raster metrics, selected/hovered/focused controls, unsupported paint on arbitrary external Native widgets, clipping, full CSS browser coverage, 60 FPS scaling, and multi-OS visual equality. These remain in stages 3–8. Kivy-native and Qt-native tests are separate processes; there is no paired screenshot oracle in this stage. The prior stage-1 geometry issue must not be silently declared solved solely from this CSS gate.

**Public behavior census:** N/A for the new correction, which repairs the preexisting Button CSS reset contract rather than advertising a new property. Existing public behavior certification jobs were run and passed.

This document is a record of tests at the exact implementation SHA; do not transfer its PASS status to another commit without rerunning the required validation. No merge to `develop` is authorized by this stage-specific evidence.
