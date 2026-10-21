# CSS native visual paint — bounded functional projection contract

**Milestone:** P1.4.6, bounded native functional subset closed at the certified implementation SHA. The initial-increment notes below are historical; this final closeout supersedes their former pending statements.
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


## Native rounded border paint (P1.4.6 incremental scope)

The shared CSS projector accepts a **single nonnegative px** value for
`border-radius`. Percentage, corner-specific, elliptical, and negative
values are not in this portable native subset. Border paint remains tied to
an explicitly colored, positive-width CSS stroke (except Qt's semantic QSS
radius, which can also round a styled background).

* **Qt**: semantic hosts retain QSS radius; interactive Text-host controls
  add local `border-radius: Npx` alongside their current native typography
  and `border-color`/`border-width`. Keyed changes rebuild local QSS,
  and removing the style restores the original widget stylesheet.
* **Tkinter**: themed controls retain their original native widget and
  event behavior. Four instance-owned `Frame` edges shorten around four
  instance-owned, small `Canvas` arc corners; old canvases are destroyed on
  radius changes and on CSS removal. Radius and border width must be
  **integer device pixels**, with radius at least as large as stroke width.
  Canvases sample the control's native/theme background; the clipping and
  background of custom themes are not browser-equivalent. The native theme
  may still paint its own underlying border.
* **Kivy**: each interactive control owns one `canvas.after` stroke, drawn
  as a rounded rectangle and rebound to geometry changes. Radius changes
  update the existing instruction. A zero radius produces straight corners;
  removing the CSS stroke unbinds and disposes its instruction group.
  The stroke overlays, rather than replaces, Kivy's existing background.

Tests in `tests/test_mounted_grid_native_renderers.py` cover PascalCase
`Button`/`Input` and HTML-like `button`/`input`, including radius
changes (8 to 12 px), resetting to zero, and identity preservation. This
increment is only certified when its exact commit has successful native
Qt/Tkinter/Kivy and Grid workflows.

This work intentionally does not claim arbitrary per-corner radii,
percentage radii, full clipping of child content, or exact theme-independent
browser compositing. These are separate capabilities.


## Native functional acceptance — closed bounded CSS Visual subset

**Evidence implementation/test SHA:** `a3b1301ae76e421f8920cff6a76ef37d996d6131` ([commit checks](https://github.com/Neuri-AI/PSX/commit/a3b1301ae76e421f8920cff6a76ef37d996d6131/checks)). All **13 of 13** applicable PR workflow families concluded successfully, including [native selective validation](https://github.com/Neuri-AI/PSX/actions/runs/39636509512) and [integral Grid certification](https://github.com/Neuri-AI/PSX/actions/runs/39636509785). Native test jobs ran for Qt (PySide6, PySide2, PyQt5, PyQt6), Tkinter and Kivy; this is executed toolkit evidence, not parser-only assertions.

The bounded certified functional implementation covers projected properties on `Checkbox`, `Radio`, `Select`, `TextArea`, `Link` and `Badge`, plus the existing HTML-like semantic hosts, Text, Button and Input. Tested cases include actual native selection/editing, maintained focus capability and acquired focus when supported by the test display, read-only and enabled state changes, latest callback dispatch, keyed native identity, inherited foreground, border/radius and typography changes and resets, unmount while painted, and teardown of owned Tk borders/Kivy Canvas instructions and event subscriptions. Qt recomposes widget-local CSS in valid QSS selector rules while preserving native Link stylesheets and subsequently installed manual QSS. Tk instance styles do not mutate global ttk theme definitions; Kivy owned Canvas paint does not alter unstyled siblings.

**Defined exclusions remain unsupported rather than silently implied:** Qt Badge is not a general CSS border painter; Kivy Checkbox has no CSS text foreground; Radio selection belongs to RadioGroup; its standalone native test uses the supported non-SFLE grouping host rather than claiming intrinsic measurement under Cinnamon Block; generic native/custom widgets do not automatically receive CSS paint; theme-dependent pixel clipping, per-corner/percent radius, exact text justification, all platform fonts and browser screenshot parity are not part of this bounded projection.

The exact per-component/backend capability table, functional tests and evidence are in [the native CSS component capability inventory](css-native-component-capability-inventory.md). This closeout satisfies **P1.4.6's bounded functional native visual gate** without claiming **P1.4.7** general dependency-aware invalidation or **P1.4.8** independent exhaustive device/theme/platform release certification. The feature PR remains draft and must not be merged without owner approval.
