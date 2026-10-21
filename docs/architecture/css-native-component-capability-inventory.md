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

## Component-family inventory

These are **source dispatch observations**, not blanket support assertions. Relevant source: `psx/renderers/{qt/pyqt.py,tkinter/tkinter.py,kivy/kivy.py}` and `psx/css/native_paint.py`.

| Component family | Qt | Tkinter | Kivy | Required additional evidence |
| --- | --- | --- | --- | --- |
| HTML-like semantic hosts (`div`, `span`, `p`, headings) | Native host paint/typography | Native host paint/typography | Native host paint/typography | Composited pixels, external theme/stylesheet coexistence |
| `Text` | Native QLabel/Text-document routes | ttk.Label / owned multiline Text | Label | DPI, wrapped measurement, removal/reflow across fonts |
| `Button` / `button` | Native control foreground/type/border | Per-instance ttk type/foreground/border | Native Button/color/stroke | State transitions, focus and active theme behavior |
| `Input` / `input` | Native input type/foreground/border | ttk.Entry type/foreground/border | TextInput foreground/stroke | Selection/caret/disabled/read-only and intrinsic sizing |
| `TextArea` | Control-specific native route | Control-specific native route | TextInput route | Multiline/selection/scroll and style removal |
| `Checkbox`, `Radio`, `Select` | Control-specific branches | Control-specific branches | Some branches only support text color or paint stroke | Per-control per-property acceptance; states and theme invariants |
| `Badge`, `Link` | Specific control paths | Specific control paths | Specific control paths | Original paint restoration and capability negatives |
| `Flex`, `Grid`, `GridItem`, `Scroll`, `Box` | Cascade/layout participation | Cascade/layout participation | Cascade/layout participation | Do **not** equate computed CSS with every native paint property |
| Arbitrary `Native` / custom adapters | Not implied | Not implied | Not implied | Explicit opt-in/capability contract required |

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

## Open verification gaps (do not certify yet)

- Full per-component native state and event matrix for Checkbox, Radio, Select, TextArea, Link, Badge and themed widgets.
- External manual Qt stylesheets and Tk/Kivy theme coexistence, pixel clipping and platform-specific rounded background differences.
- Cross-platform native visual snapshots/readbacks and DPI/font/resource variations.
- Exact-SHA receipts for newly added coverage (including the inherited color/disabled transition test) are pending workflow execution.

The **P1.4.6 functional-integration gate remains open** until the above applicable advertised combinations have direct executed native evidence. P1.4.8 separately owns the exhaustive immutable-SHA cross-platform release matrix.
