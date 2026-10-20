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

Full general-component foreground/typography coverage, unrestricted font weights,
percentage font sizes, justified text, border widths and radii **as paint**,
mixed composition with manually installed native
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

**Uncertified boundaries:** the portable native Text font-weight projection accepts only 400 and 700,
rejecting other numerical weights rather than misrepresenting their appearance.
Kivy font-family requires a resolvable native font resource. Percentage font
sizes and justified text alignment are rejected by the bounded projection.
Explicit `line-height` is supported in Kivy Label for positive pixel
values through its native line-height multiplier. Qt QLabel and Tkinter
ttk.Label still fail closed rather than pretending exact text leading support. These are active implementation
gaps, **not** supported typography parity.

Renderer-level native typography tests and native font metric/reflow receipts
must pass before advertising or closing this capability. The broader
cross-platform matrix remains tracked by P1.4.8.

## Fixed pixel line-height in native Text (implementation and certification scope)

Qt's native `Text` uses a QLabel-compatible host with a `QTextDocument`,
`QTextBlockFormat.FixedHeight` and QTextDocument painting/height-for-width
measurement when authored CSS `line-height` is present. Removal restores
QLabel's ordinary native painting and measurements. Native font, foreground
and paragraph alignment are reflected in the Qt document.

Tkinter retains the public Text handle as `ttk.Label`, and creates a
lifecycle-owned, non-editable `tk.Text` paint child only while explicit
`line-height` is active. Native `tk.Text` spacing2/spacing3 projects extra
interline leading. The native Tk font's linespace and a same-font Tk wrapping
probe supply the intrinsic heights consumed by Cinnamon; removal destroys
the child and restores ttk.Label rendering. Style-only font updates notify
Cinnamon's coalesced, per-widget `font` measurement invalidation; pure
foreground/alignment changes do not trigger unnecessary native remeasurement.

The accepted subset is positive px line-height. Tk requires **integer device
pixels** and a value no smaller than its font's native linespace; unsupported
smaller/fractional lines fail explicitly rather than silently changing the
value. This limitation is not equivalent to universal browser CSS text layout,
and remains documented until a more capable native renderer is certified.

Executed native tests must verify width-sensitive wrapped text, matched
intrinsic heights, keyed style changes, style removal, native identity and
resource teardown. Do not claim certification from source presence alone;
require successful relevant native and Grid CI jobs for the immutable code SHA.
