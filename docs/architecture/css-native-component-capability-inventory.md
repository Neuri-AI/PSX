# Native CSS visual capability census — implementation and evidence inventory

**Scope:** Qt (PySide/PyQt), Tkinter and Kivy native projection, on the universal-box-model branch. This is an **implementation inventory**, not an immutable-SHA certificate or pixel-accurate browser-equivalence claim. The full independent release certificate remains P1.4.8.

## Status vocabulary

- **Tested path:** specific native mounted regression exists; verify execution on the exact implementation SHA before calling it certified.
- **Implemented, partial:** native application path exists but operation/backend/readback coverage is incomplete.
- **Unsupported:** the portable paint subset does not guarantee this behavior; no implied browser equivalence.
- **N/A:** widget has no applicable text/paint surface, or Headless cannot provide native paint evidence.

## Property / adapter projection

| CSS property | Qt | Tkinter | Kivy | Boundary |
| --- | --- | --- | --- | --- |
| `color` | Local QSS / native foreground | Instance ttk style or widget foreground | Native label/text color | Alpha foreground rejected Qt/Tk; inherited authored color is distinguishable from defaults |
| `background-color` | Local QSS for semantic hosts | Instance `ttk.Frame` style / owned paint | Owned `canvas.before` instructions | Controls beyond semantic hosts need separate background verification; alpha supported Kivy only |
| `font-family` | Native font / local QSS | Owned `tkinter.font.Font` / ttk style | Native font resource | Kivy font must resolve; font changes can invalidate measurement |
| `font-size` | Native font / QSS | Native per-instance font | Native font_size | Positive px only in bounded native projection |
| `font-weight` | Native bold + bounded QSS | Native normal/bold | Native bold | Portable Text projection is 400/700; not all CSS numerical weights visually distinguishable |
| `line-height` | QTextDocument-based Text/Button path | Owned Text paint bridge / ttk approximation | Native line-height ratio | Explicit positive px subset; Tk integral/device font metric restrictions |
| `text-align` | Native alignment / QSS | Native anchor/justify | Native halign | Justify not supported in the bounded native projection |
| `border-color` + `border-width` | Local QSS stroke | Owned edge overlays | Owned canvas stroke | Positive pixel width and explicit color; geometry remains Cinnamon-owned |
| `border-radius` | Local QSS radius | Owned edge and corner canvases | Rounded rectangle stroke | Single nonnegative px; no universal child clipping or per-corner/percent radii |

## Component / backend projection matrix

Entries describe source-supported **bounded** native drawing paths, not browser pixel parity. `font` means `font-family`, positive pixel `font-size` and 400/700 `font-weight` where supported; `stroke` means the coupled pixel `border-color` + `border-width`, with single-pixel-unit `border-radius` when applicable.

| Component | Qt (PyQt5/6, PySide2/6) | Tkinter | Kivy | Excluded / special contract |
| --- | --- | --- | --- | --- |
| HTML-like semantic hosts (`div`, `span`, `p`, headings) | Local background, foreground, typography, stroke/radius | Instance-local background, foreground, typography, owned edge/corner paint | Owned canvas background/stroke + native text properties | Flow and native geometry belong to Cinnamon; clipping/browser-composited pixels not promised |
| `Text` | Native foreground and typography, QTextDocument leading | Native typography, owned multiline leading, edge paint | Label typography and owned stroke | Qt `Text` is not a generic CSS border painter; backend line-height bounds differ |
| `Button` / `button` | Foreground, font, alignment, QSS stroke/radius | Local ttk typography/foreground and edge/corner paint | Native text properties and owned canvas stroke | Text leading has backend-specific constraints |
| `Input` / `input` | Foreground, font, alignment, stroke | Foreground, local font, alignment, owned stroke | TextInput foreground/font/selection and stroke | Existing native controlled value/caret contracts retained |
| `Checkbox` | Foreground/font and stroke | Instance-local ttk foreground/font and owned stroke | Owned stroke only | Kivy CheckBox has no portable CSS text foreground; do not advertise it |
| `Radio` inside `RadioGroup` | Foreground/font and stroke | Instance-local ttk foreground/font and stroke | Label foreground and owned stroke | Kivy Radio does not project the general native font stack; native-group test uses the supported non-SFLE host until Block intrinsic group measurement is separately implemented |
| `Select` | Foreground/font and stroke | Native combobox foreground/font and stroke | Spinner foreground/font and stroke | Selection remains controlled; alignment support varies |
| `TextArea` / `textarea` | Foreground/font and stroke | Foreground/font, tag-based alignment, stroke | TextInput foreground/font and stroke | Read-only, selection, focus and live edit callbacks belong to the existing control adapter |
| `Link` | Foreground/font, native QSS-preserving stroke | Tk Label foreground/font and stroke | Button-based foreground/font and stroke | Tk Label has no state option; enabled is enforced by the Link adapter and cursor |
| `Badge` | Custom foreground painter | Custom foreground painter and owned stroke | Native foreground and owned stroke | Badge has no portable click/selection event; Qt Badge does **not** apply general QSS stroke |
| `Flex`, `Grid`, `GridItem`, `Scroll`, custom `Native` | Resolution/layout only unless a specific paint host is declared | Resolution/layout only unless a specific paint host is declared | Resolution/layout only unless a specific paint host is declared | No blanket CSS paint support for arbitrary native widgets |

### Native-state and theme evidence

- **CSS updates:** keyed instances are checked by native handle identity; `color` and border paint update and reset without replacing the control.
- **Events:** actual native checkbox toggles, radio selection, Select selection, Link activation and TextArea modification are exercised with updated event callbacks. Old `EventSlot` objects become inert after teardown.
- **State:** enabled/disabled is checked through each backend's real state representation; readonly and selection through native editors; focus is checked when the headless toolkit permits acquiring it, and focus *capability* is always preserved.
- **Qt QSS:** existing Link selector blocks and later manually installed QSS are recomposed as valid widget-local rules and restored on CSS removal; the unstyled sibling is unaffected.
- **Tkinter theme:** css-derived ttk styles remain per-widget; `TButton` global theme lookups and unstyled siblings are unaffected. Tk rounded overlays still cannot promise transparent clip edges on every theme.
- **Kivy Canvas:** owned instruction groups and position/size bindings are restored on CSS reset and unmount; unstyled sibling Canvas state is unchanged.
- **Headless:** structural/source and geometry tests are applicable, but native paint readback is **not applicable**.
## Existing executable coverage

- `tests/css/test_native_paint.py`: typed conversion and fail-closed/alpha/border/typography projector rules.
- `tests/test_mounted_grid_native_renderers.py`: native-mounted font, inherited input style, HTML-like heading changes, PascalCase/HTML-like foreground, disabled Button, border update/reset, radius update/reset, backgrounds, incremental font revisions, line-height and lifecycle.
- `tests/test_css_markup_census.py`: style resolution and public markup census; **does not constitute native paint readback**.
- `tests/test_ci_impact.py` and `scripts/ci/impact.py`: native CSS changes and native-grid-mounted tests route to backend validation.

## Functional verification checklist

For **each advertised combination** of property, component and backend, require:
1. Mount and inspect the actual native paint/typography property or owned drawing primitive.
2. Change a style or inherited ancestor rule on the same key: assert widget-handle identity, new style and no stale old value.
3. Toggle applicable native enabled/focus/edit/selection state before and after CSS updates: assert state, callbacks and ownership.
4. Remove the style and assert correct native-prop/theme restoration; unmount and verify callbacks, overlays, fonts and canvas instructions are released.
5. For font changes, assert Cinnamon remeasures where necessary; for paint-only changes, assert no unnecessary measurement.
6. Record negative support (value/unit/renderer) as a verified explicit rejection rather than silently skipping the combination.

## Functional execution mapping and exclusions

The following behavior-specific tests run in the native layout workflow for the supported Qt bindings, Tkinter and Kivy (not generic parser-only substitutes):

- `test_native_css_control_border_updates_and_owned_paint_cleanup` — border readback, keyed update and reset for Checkbox, Select, Badge, Link and TextArea.
- `test_native_radio_group_css_keeps_selection_callbacks_and_child_identity` — actual native RadioGroup selection and updated callback under an explicitly supported non-SFLE group host.
- `test_native_css_style_updates_keep_live_control_callbacks` — real native Checkbox toggle and Link activation, in-place callback retargeting, inert slots after unmount.
- `test_native_select_css_retains_selection_and_latest_user_callback` — native Select choice, keyed CSS transition, callback and teardown.
- `test_native_textarea_css_preserves_selection_readonly_and_edit_callbacks` — native editor selection, readonly transition, live edit and CSS removal.
- `test_native_editor_css_keeps_focus_capability_and_active_focus_when_available` — focus capability and retained actual focus when the virtual display grants it.
- `test_native_css_updates_preserve_control_state_and_owned_styling` — enabled/disabled transitions and identity on Checkbox, Select, Link and TextArea.
- `test_native_css_visual_paint_is_instance_scoped_and_cleans_up`, `test_qt_css_merges_manually_installed_native_stylesheets` — local Qt QSS / ttk styles / Kivy canvas state and native/manual stylesheet coexistence.
- `test_native_css_teardown_releases_active_control_paint` — active styled widgets release owned edges, canvases and Kivy instruction groups on unmount, even without an explicit CSS reset.
- Existing `test_native_badge_css_foreground_is_applied_and_restored`, `test_native_css_typography_updates_text_without_replacing_widget`, `test_native_control_font_measurement_revisions_are_incremental` and related tests certify the other advertised paint/font/invalidation paths.
- `tests/css/test_native_paint.py` exercises CSS source conversion and rejection of alpha on Qt/Tk, percentage radius/leading, unrepresentable weights and unsupported alignment.

**Bounded exclusions (not advertised):** arbitrary control backgrounds; arbitrary native/custom widget styling; universal justified text, percent/elliptical/per-corner radius, child clipping and native browser pixel parity; Kivy Checkbox text coloring; Qt Badge CSS border paint; cross-device visual snapshots and DPI/font/theme pixel identity. An unprojected CSS property may still resolve in CSS Core; do not conflate its computed value with a native rendering guarantee. Unsupported values *within a projected property* fail closed where the projector validates them.

**Remaining independent certification:** P1.4.8 owns release-wide exhaustive property × backend × supported OS/Python matrix, screenshot/pixel regressions, DPI/font/theme sweeps and immutable-SHA release acceptance. P1.4.7 owns generalized dependency-aware invalidation/performance. Neither substitutes for the native functional tests listed above.

## Functional certification receipt — implementation SHA

**Implementation SHA:** `a3b1301ae76e421f8920cff6a76ef37d996d6131`  
**Evidence:** [Actions at the exact implementation SHA](https://github.com/Neuri-AI/PSX/commit/a3b1301ae76e421f8920cff6a76ef37d996d6131/checks), [PR #48](https://github.com/Neuri-AI/PSX/pull/48).  
**Result:** 13/13 repository workflows completed with `success`; zero failures or pending workflows for this SHA.

The `Native layout selective validation` workflow completed successfully. Its actual job matrix includes Qt native components; PySide6, PySide2, PyQt5, PyQt6 SFLE parity; Tkinter native components; Kivy native components; native wheel/fallback jobs for macOS, macOS Intel and Windows; public behavior receipt aggregation; and the required CI conclusion job. These jobs have `success`, not `skipped`, in GitHub Actions.

**P1.4.6 functional scope:** verified mounted native CSS foreground/border/radius and typography subsets; six-control projection inventory including Radio within RadioGroup; keyed style updates, inherited color, original paint restoration, enabled/disabled, user selection, editor readonly/selection and focus capability, live event-slot rebinding, native QSS/ttk/canvas coexistence, and paint disposal on unmount. Both supported behavior and **explicit exclusions** above are part of this bounded certification. This closes the **functional native-visual increment**; it is not a claim of browser pixel parity, exhaustive device/OS/DPI tests or generalized invalidation, which remain scoped to P1.4.8 and P1.4.7 respectively.

The repository must not treat later changed implementation commits as covered by the above SHA until their own workflows finish. Any downstream release gate still requires the independent full property/backend matrix and owner acceptance.


## Rounded one-sided card borders (bounded implementation)

Qt QSS remains the visual reference for `border-bottom`, `border-top`, `border-left` or `border-right` combined with a positive pixel `border-radius`. The authored side, thickness and color are never copied to other sides. This is a *bounded functional paint projection*, not a pixel-perfect screenshot certificate.

- **Qt:** per-side QSS remains unchanged.
- **Kivy:** each specified side owns a centered polyline whose endpoints span the appropriate half of its two rounded corners. The path is recomputed after position, size or radius changes; normal CSS updates preserve widget identity, and style reset/unmount removes owned instructions and bindings. Corner radius is clamped to the mounted box for paint purposes without changing Cinnamon geometry.
- **Tkinter:** for semantic formatting hosts with an explicitly authored opaque `background-color`, border-side frames stop at the rounded corners. The existing owned quarter-circle background canvases draw only the corresponding half-corner arcs, above their own fill. CSS updates rebuild the arcs without introducing globally hardcoded colors. Only integer pixel stroke widths and radii are currently supported. A rounded side stroke without an explicitly painted opaque background or with a radius smaller than half the width is rejected rather than inaccurately rendered.
- **Scope:** this increment covers semantic formatting hosts such as cards and activity rows, not per-side border behavior for every native control. Blended semi-transparent Tk surfaces, arbitrary background images, complex per-corner radii, and pixel-perfect raster/antialiasing correspondence are not certified.
- **Evidence path:** `tests/css/test_native_paint.py` tests corner-path bounds and validation, while `tests/test_mounted_grid_native_renderers.py::test_rounded_bottom_only_border_updates_without_painting_other_sides` mounts the same card in Qt, Tkinter and Kivy and asserts paint instructions/overlays, keyed updates, radius revision and cleanup. This extends an existing authored CSS combination; there are no new public props, events or methods to add to the component public API census. Platform screenshot comparison is still pending.


## Unified Tkinter rounded-card surface (bounded compositor)

For a semantic formatting host with a positive pixel `border-radius` and an authored opaque CSS fill or border, Tkinter now owns **one Canvas** to paint the background and **all authored border sides together**, including their rounded corners. No independent edge frames or four separate corner canvases are required for this path. The existing widgets remain the interactive/layout children; Cinnamon retains the only box geometry. The bitmap corner patches are antialiased with four-by-four subpixel coverage per pixel, encoded via Python's standard library (no Pillow runtime dependency), and retained only until repaint.

The outer corner pixels visually reveal the nearest **solid** CSS/native ancestor color. This is a native Tk composition workaround, **not** true backdrop alpha: arbitrary background images, gradients, video, sibling overlap and translucent ancestors are not certified. No platform/theme/application palette is hardcoded. Border colors and widths come from computed CSS. An unfilled rounded host with an authored side border is supported over a solid parent paint.

A keyed change to border color, radius, parent solid background or committed box size repaints the same Canvas and keeps child widgets/handlers stable; removing the rounded style destroys the layer and its PhotoImages. Flat/unrounded widgets, native controls and unsupported partial-alpha CSS remain on their existing bounded pathways. Full-device visual parity with Qt/QSS still requires screenshot testing.

**Evidence:** `tests/test_tkinter_renderer.py` checks one paint layer, raster corner values, parent-only updates, rounded side-only painting and reset. `tests/test_mounted_grid_native_renderers.py` compares existing rounded semantics across Qt, Tkinter and Kivy; `tests/test_ci_impact.py` checks routing. No new public props, methods or events were introduced, so additional public behavior census cells are not applicable.


## Native Qt/QSS ↔ Tkinter rounded-corner visual matrix

The executable native-visual check `tests/test_native_rounded_card_visual.py` renders **16 real Qt/QSS and Tk/Xvfb card pairs**: radii `4, 8, 12, 20px`, borders `1, 2px`, and contrasting light/dark CSS palettes. It captures Qt by `QWidget.grab()` and the Tk Canvas from the Xvfb framebuffer using `PIL.ImageGrab`, not an analytic substitute. For every case, it saves `-qt.png`, `-tk.png`, `-difference.png` and a metrics JSON under the **qt-tk-rounded-card-visual** CI artifact. This is executed by the native Qt job, and impact routing makes a change to the Tk rounded painter select both Qt and Tk.

The initial bounded gate asserts rendered pixel geometry (four exterior corners, authored straight stroke on top/bottom and the interior fill) on **both** native images; it also measures corner-color classification disagreement and fails if above 35%. Three nearest authored colors (parent, fill and stroke) are used for classification, so color/AA differences are separately captured in difference PNGs, not mislabeled as exact parity. The numeric limit is a smoke/regression threshold, **not** pixel-perfect equivalence and not a calibrated perceptual tolerance. It must be revised from actual Qt/Tk evidence, rather than relaxed merely to obtain a green run.

Tk on X11, Qt offscreen and one machine's device-pixel ratio do not establish a visual certificate across Windows, Arch, Ubuntu or macOS; platform-specific screenshot comparison remains pending. No new public props/events/methods are introduced; public-behavior census update is N/A, whereas functional tests, CI selection and an artifact for inspection are required.
