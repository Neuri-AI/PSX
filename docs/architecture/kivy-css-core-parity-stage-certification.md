# Kivy ↔ Qt CSS Core parity — Stage 2 evidence

**Date:** 2026-10-29
**Branch:** `fixes/psx-issues`
**Last validated implementation SHA:** `5cbf46156578bbc2662d19e7606a3df6fa0182a4`
**Qt reference:** PySide6 (logical CSS pixel coordinates)
**Scope:** shared CSS Core, typed Cinnamon geometry, bounded native Kivy projection and device-pixel scaling. Visual screenshot identity is a separate native-paint acceptance gate.

## The Retina problem

On Kivy/Cocoa/SDL2, `Window.size` is the drawable backing-store size in pixels while `Window.system_size` is the size in window coordinates. At ratio 2, a CSS `height:38px` rendered as 38 drawable pixels would look half-size relative to Qt's logical 38px.

PSX now samples the **observed** drawable/window ratio through `psx/sfle/kivy_display_scale.py`; it does not hardcode 2, override global `Metrics.density`, mutate `Window.size`, or install a second native layout manager. For a native Kivy viewport, *authored* `LengthKind.PX` values are converted before the viewport-unit resolution stage; `100vw`, `100vh`, and percentages must not be scaled twice. The shared Cinnamon engine retains authority for native rectangles.

The Kivy renderer projects portable component text sizes and CSS `font-size`, `line-height`, button padding, native control/semantic border widths, and border radii at this observed ratio. It refreshes mounted widgets on a 1x↔2x display change without discarding their identity. The Cocoa/SDL resize callback selects drawable dimensions only when the callback reports the current `Window.system_size` on a high-density window. Synthetic/explicit resize notifications remain supported.

`dp()` and `sp()` are Kivy-specific unit conversions; blindly introducing both into the CSS pipeline could double-convert values or decouple font metrics from Cinnamon's box model. Here the mapping uses actual drawable/window dimensions and tests `Metrics.density` separately from authored CSS pixels.

## Executed verification on exact SHA

- [Native layout selective validation — 40992288185](https://github.com/Neuri-AI/PSX/actions/runs/40992288185): **PASS**, including native Qt, Kivy, Tkinter, deterministic Headless, SFLE core, differential Rust/Python, geometry, public behavior evidence and required CI conclusion.
- [Kivy Retina CSS parity — 40992288239](https://github.com/Neuri-AI/PSX/actions/runs/40992288239): **PASS**, four jobs:
  - macOS ARM (`macos-15`): pure CSS/scale geometry tests.
  - macOS Intel (`macos-15-intel`): pure CSS/scale geometry tests.
  - Linux: pure CSS/scale geometry tests.
  - Linux SDL2/Xvfb: **real mounted** Kivy native widgets with simulated 2x Retina ratio, verifying `height:38px` → 76 drawable px, `font-size:15px` → 30, `padding:0 10px` → 20 horizontal drawable px, CSS viewport units unchanged, and 2x→1x→2x transitions without remounting.
- Native Kivy resize and event regression also exercises drawable backing dimensions against potentially point-based Cocoa events while preserving manually dispatched SDL2 resize behavior.

## Disposition

**Stage 2 bounded CSS Core and deterministic Retina projection: PASS on the exact implementation SHA above.** This means the contract and implementation paths covered by those tests are accepted, including live Kivy SDL2 rendering under Xvfb with a simulated 2x backing ratio, plus pure geometry/scale checks on both macOS architectures.

**Physical macOS Retina/Cocoa rendering is NOT certified.** GitHub-hosted macOS runners failed to create an SDL2 OpenGL pixel format (`RuntimeError: Failed creating OpenGL pixel format`). The macOS CI jobs therefore verify geometry and scale mathematics *without a native OpenGL window*. An actual Mac Retina + standard-density pair, Kivy/PySide6 side-by-side screenshots, native font raster and input hit-target comparison, desktop display migration, nested Grid/Scroll and physical pointer coordinates remain explicit native-visual acceptance work. Do not cite green macOS CI as a native Cocoa screenshot test.

No changes have been merged into `develop`; no approval for such a merge is implied. A future change to native geometry, scale behavior or CSS presentation requires new exact-SHA CI and appropriate real-display evidence.
