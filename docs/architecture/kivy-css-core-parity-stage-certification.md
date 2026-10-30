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

## Retina/macOS review — reopening the cross-display CSS acceptance gate (2026-10-29)

**Status correction:** the PASS above is limited to the tested Linux logical-coordinate configurations. **Do not interpret it as a completed macOS Retina stage-2 CSS acceptance certificate.** The owner reported half-size Kivy interfaces on Retina displays and requested this stage be repeated for high-DPI configurations. That requirement remains OPEN pending real native/macOS evidence.

The Kivy issue [#8140](https://github.com/kivy/kivy/issues/8140) documents a `Window.size` versus widget/window-coordinate discrepancy that was addressed in upstream PR #8630, but varying Kivy versions and Cocoa/SDL providers still require verifying the current installed runtime. In Kivy the `Window.size` getter represents drawable pixels and `Window.system_size` represents window-coordinate dimensions; the ratio may be approximately 2 on Retina hardware. `dp()` and `sp()` are styling conversions, not a license to multiply already-physical coordinates or to use `Window.size` as the CSS logical viewport unconditionally.

Current PSX source paths requiring coordinated verification before modifying DPI conversions:

1. `psx/renderers/kivy/kivy.py`: `_sfle_on_window_resize`, `_sfle_on_root_size`, `set_sfle_constraints`, `apply_css`. These currently use the attached native window/root dimensions; there is no demonstrated mapping from Qt's logical CSS viewport to Kivy's drawable/window-coordinate distinction.
2. `psx/sfle/native_pixel_space.py`: `DevicePixelSpace.from_widget('kivy', ...)` currently returns scale 1 unconditionally. The existing comment treats widget `pos/size` as Kivy pixel coordinates. This may be correct for the widget API but does not prove Qt-logical-to-Kivy-drawable visual parity.
3. `psx/sfle/kivy_layout_bridge.py` and `grid_native_commit.py`: preserve Cinnamon's single geometry authority and inverse-Y projection. Native readback, paint rectangles, control strokes and touch hit-testing must agree in the same space.
4. `psx/sfle/kivy_measurement.py`: font textures, glyph/textarea metrics, and `dp`-scaled intrinsic minima must match the selected logical space. CSS `font-size`, `line-height`, padding, border and widths must scale coherently, not independently.
5. `tests/test_kivy_renderer.py::test_css_px_font_matches_cinnamon_at_all_density_settings` currently expects raw numeric font sizes even at density 2, reflecting the old assumption. Its existing pass is **not** Retina visual equivalence evidence.

**Mandatory acceptance before re-closing:** real macOS Retina and non-Retina native Kivy/PySide6 paired executions at scale 1 and 2 (plus fractional ratio if supported); capture both `Window.size` and `Window.system_size`, Metrics.density/fontscale, logical Cinnamon rectangles, widget geometry and screenshot dimensions; confirm a CSS `height:38px`, `font-size:15px`, `padding:0 10px`, `line-height` and border yield the same on-screen logical proportions; confirm unchanged event targets and continuous resize without feedback; repeat both Cinnamon Rust and Python. No implicit platform-wide `Metrics.density` override, `Window.size = Window.size`, or native BoxLayout replacement is approved. This is a blocker, not an already executed certificate.
