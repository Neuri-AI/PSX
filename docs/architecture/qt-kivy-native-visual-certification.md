# Qt-reference Kivy native visual certification — Stage 3

**Source branch:** `fixes/psx-issues` (do not merge before full acceptance)
**Current disposition:** **OPEN — bounded Linux paint gates pass, cross-platform visual certificate blocked.**
**Reference:** PySide6 native Qt/QSS. Cinnamon remains the only layout authority.

## Implemented native paint work

- Authored CSS backgrounds now replace native Kivy textures for Button, Input,
  TextArea, Select and Link without changing unstyled controls. Input and
  TextArea suppress both normal and focused textures; style removal restores
  native backgrounds.
- Checkbox and Radio paint an owned host background without replacing their
  native indicators or selection state.
- Native controls receive separate authored border-side strokes, not a
  fabricated full rectangle from one specified edge. Stroke width and radii
  follow the display pixel ratio; callbacks and canvas instructions are
  removed on CSS reset and unmount.
- Button, Select and Link use a measured content-width text texture for
  authored text alignment; this is rebound on resize and restored after CSS
  removal. CSS foreground updates both normal and disabled paint where the
  Kivy native control exposes those properties.
- Kivy Badge scales its typography/geometry using observed display density,
  instead of the previous unconditional fixed 2x multiplier.
- Added paired native **QSS QWidget, QPushButton vs SDL2/OpenGL Widget, Button**
  screenshots with light/dark styles, source colors, strokes and corner
  classification receipts in
  `tests/certification/qt_kivy_css_native_raster.py`.
- Added same-font Qt/Kivy native text metric receipts, a targeted CI impact
  route, and Windows/macOS native visual jobs.

## Evidence and unsupported inferences

Successful actual Linux Xvfb/SDL2 Qt↔Kivy paired native paint runs include
[40994124962](https://github.com/Neuri-AI/PSX/actions/runs/40994124962)
and [40995166918](https://github.com/Neuri-AI/PSX/actions/runs/40995166918).
Their comparison outputs are real captured framebuffer pixels, not synthetic
reference images. The bounded gate tolerates measured anti-alias differences
and intentionally does **not** claim universal pixel equality.

The attempted full-platform run
[40996468094](https://github.com/Neuri-AI/PSX/actions/runs/40996468094)
found actual blockers:

- macOS Apple Silicon and Intel hosted runners: Kivy 2.3.1 SDL2 failed to
  create an OpenGL pixel format; `Window` was unavailable. These are not
  Retina visual captures. Successful macOS **scale-math** jobs do not resolve
  this environmental blocker.
- Windows hosted runner: the Kivy screenshot subprocess failed to present
  the first native paint within the 90-second bounded wait. The test now
  produces an explicit 30-second diagnostic instead of an opaque timeout.
- A prior head SHA
  [4b6e381e](https://github.com/Neuri-AI/PSX/commit/4b6e381e)
  failed Kivy public Badge lifecycle certification. No later unexecuted
  changes may be assumed to have cleared this failure.

**Release/stage exit remains blocked** on actual native macOS and Windows
rendering, paired representative typography and interaction states, visual
reference acceptance on physical 1x/2x displays, and entire exact-HEAD
selective CI. A green parser/geometry/scale-math suite or a Linux raster
sample must not be relabeled as full stage 3.

## Acceptance requirements

1. Install the test app on actual macOS Retina and standard-density monitors
   (Apple Silicon and Intel if supported), plus Windows and Linux.
2. Run the same PSX Markup/CSS state on PySide6 and Kivy, with matching actual
   font files and client dimensions. Capture native drawable sizes, device
   density, Cairo/Qt/Kivy or Cocoa provider, Cinnamon Rust/Python geometry,
   screenshots and event readbacks.
3. Quantify component-by-component fill/border/corner metrics, glyph baselines,
   line-height, padding, hover, focus, pressed, disabled, selected, CSS reset,
   keyed identity, native painting on resize, and teardown.
4. Establish pre-approved tolerances for font rasterization and screenshot
   differences; fail if test environment cannot provide real graphics.
5. Re-run all required CI and public census jobs on the final immutable SHA.
   Do not integrate this branch into `develop` without that evidence.

**No known native OpenGL limitation may be replaced with a skipped test,
synthetic screenshot, hardcoded theme color, or false certification PASS.**


## Latest representative native border parity evidence (2026-10-30)

The dashboard audit exposed a concrete Kivy OpenGL stroke raster coverage error:
a CSS 2px border was visibly four pixels wide (and leaked one pixel outside
the Qt border box) at native 1x Linux resolution. The CSS geometry was not
the source of this difference; Kivy's `Line` rasterizer covered a wider
pixel footprint than its nominal numeric width.

The visual gate now independently classifies straight border edges and
rejects width errors even when rounded-corner tolerance is met. We calibrated
the **Kivy line painter only**, leaving CSS values, Cinnamon geometry, and
Qt/Tk renderers unchanged. Paired native Qt/QSS and SDL2/OpenGL screenshots
from [run 41007052598](https://github.com/Neuri-AI/PSX/actions/runs/41007052598)
show **0.0% straight-edge classification disagreement** in all four
light/dark box/button fixtures. Corner disagreement is **14.0625% light**
and **7.4219% dark**; pixel-perfect fidelity is not asserted. The gate has
been tightened to 15% for corners and 15% for straight edges.

These are Linux Xvfb/SDL2 results. They neither certify a full real-world
dashboard nor substitute for the user's macOS Retina and Windows GPU
screenshots. Hosted macOS runners fail to create the necessary SDL2/OpenGL
context, and hosted Windows reports the Microsoft GDI Generic OpenGL 1.1
renderer. Both remain explicit native-graphics blockers, not silently
skipped tests. Before Stage 3 closure, verify the same border width, sidebar
spacing, header greeting, card padding and right-aligned activity dates in
real macOS/Windows UI screenshots with both Cinnamon engines.
