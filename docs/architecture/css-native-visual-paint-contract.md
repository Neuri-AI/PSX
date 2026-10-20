# CSS native visual paint — initial bounded dispatch contract

**Milestone:** P1.4.6, initial implementation slice (not full closure).
**Branch:** `feature/universal-box-model-and-styling`.

The CSS Core computes immutable styles independently of the toolkit. The
reconciler invokes the optional `apply_css(handle, computed)` renderer
capability after a successful native creation, and when computed CSS changes
during keyed reconciliation. CSS is not injected into native widget `props`;
the native event, state, intrinsic measurement and lifecycle contracts remain
unchanged.

## Implemented initial visual slice

- `background-color` with an explicitly authored opaque hex CSS color
  on lowercase semantic formatting hosts (`div`, `span`, `p` and similar).
- Qt uses a QWidget-local stylesheet; it does not change the global palette.
- Tkinter uses a unique `ttk.Frame` style name per widget, not the global
  `TFrame` style. Actual theme rendering may differ across native themes.
- Kivy attaches an owned `canvas.before` color/rectangle group, binds the
  rectangle to native `pos` and `size`, and removes both native callbacks
  and instructions on style removal or widget destruction.
- Removal of the CSS background resets only the styling owned by that
  native semantic host. A keyed CSS-only update preserves widget identity.

Partial-alpha native backgrounds are *rejected* in Qt and Tkinter instead
of being silently painted as opaque; Kivy can paint alpha directly.
Inherited defaults never trigger painting of an unstyled widget.

## Not yet certified or advertised by this slice

Portable `color` foregrounds, native font-family/font-size/font-weight and
font measurement invalidation, line height/text alignment, border widths and
radii **as paint**, mixed composition with manually installed native
stylesheets, translucent backgrounds on Qt/Tkinter, and image backgrounds.
These require separate adapter contracts and end-to-end native readback.
CSS border width already has a distinct geometry contract through Cinnamon;
its native stroke appearance must not be inferred from geometry alone.

The initial paint dispatch covers native **semantic formatting hosts only**,
not arbitrary custom widgets or all PascalCase component props. Native
`Qt/Tkinter/Kivy` widgets remain responsible for drawing their own content.

## Certification

Tests: `tests/css/test_native_paint.py` for native-independent typed
conversion; native PySide6, Tkinter and Kivy layout integration tests for
background update, keyed widget identity and teardown. Closure requires
selected native jobs, exact-SHA GitHub CI, and public capability census for
every newly advertised visual operation. P1.4.6 stays open until its implemented visual subset has required functional and native evidence. The comprehensive cross-property/native visual matrix, cross-platform regression receipts, and immutable-SHA release gate are explicitly assigned to **P1.4.8**, as recorded in `docs/roadmap.md`. This does not defer testing of new P1.4.6 behavior.


## Follow-up: bounded border-color registry and Qt paint

The CSS registry now validates non-inherited `border-color` hex values.
The Qt semantic-host adapter emits an opaque solid border only when an
explicit border color and positive pixel `border-width` coexist; the width
still belongs to Cinnamon geometry. Partial transparency is rejected rather
than discarded. This is **not** a native cross-backend border certificate:
Tkinter and Kivy stroke rendering, pixel/readback tests, optional stroke
styles and native component application remain open in P1.4.6. Its final
cross-backend evidence matrix remains P1.4.8.

## Native Text typography projection (implementation in progress)

An authored `color`, `font-family`, positive pixel `font-size`,
`font-weight`, or `text-align` may be projected onto a mounted native
`Text` handle. The adapters reapply the original Text properties before
CSS overrides so keyed style changes and removal do not permanently retain
former CSS font/color values. Qt uses QLabel font/alignment, Tkinter owns an
instance-local retained Font on ttk.Label, and Kivy updates its Label
properties. Qt/Tkinter reject alpha foreground instead of discarding it;
Kivy retains RGBA.

**Uncertified boundaries:** the current font-weight adapters project the
native bold/normal distinction rather than all nine CSS numerical weights.
Kivy font-family requires a resolvable native font resource. Percentage font
sizes and justified text alignment are rejected by the bounded projection.
Explicit `line-height` currently fails closed rather than pretending
QLabel/ttk.Label support exact text leading. These are active implementation
gaps, **not** supported typography parity.

Renderer-level native typography tests and native font metric/reflow receipts
must pass before advertising or closing this capability. The broader
cross-platform matrix remains tracked by P1.4.8.
