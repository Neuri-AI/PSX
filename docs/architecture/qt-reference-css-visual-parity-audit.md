# Qt-reference CSS visual parity audit — Qt, Tkinter and Kivy

**Audit date:** 2026-10-27  
**Repository:** `Neuri-AI/PSX`  
**Source branch:** `fixes/psx-issues` ONLY  
**Read-only source baseline:** `cbbc455650ad251efbe6ae125cfab22547dc035f`  
**Disposition:** **Open — observed Qt/Tk style disparity; Kivy device parity unverified.**  
**Nature of evidence:** source review, existing tests and contracts, and owner-provided Qt vs. Arch Linux/X11 Tk screenshots. **No new native screenshots, test executions or device measurements were performed in this audit.**

## Scope and non-negotiable constraints

- **Qt is the visual acceptance reference** for equivalent authored PSX Markup and CSS; it is **not** permission to hardcode a Qt palette, font, dimensions or application colors in other backends.
- Cinnamon inside PSX remains the sole native layout/box-geometry authority (Rust primary, Python fallback). The renderer paints the *computed CSS* within the committed boxes; it must not independently invent layout sizes.
- Preserve existing `Button`, `Text`, `Flex`, `Grid`, `GridItem`, native controls, callbacks, keyed identity and teardown.
- Distinguish **source/cascade equivalence**, **computed-style equivalence**, **measured geometry**, **paint output**, **interaction/state** and **lifecycle**. Passing one does not certify the others.
- Honor `AGENTS.md`, the master execution plan, the native visual contract, capability policy and CI impact routing for every future implementation.
- This does **not** claim all platforms render fonts with identical glyph rasterization or offer complete browser CSS. Unsupported values must be explicit, rather than silently substituting theme defaults.

## Visual evidence from owner-provided screenshots

| UI feature | Qt reference screenshot | Arch/X11 Tk screenshot | Assessment |
| --- | --- | --- | --- |
| Layout structure | Sidebar, four statistic cards, activity card, content area | Same broad structure and card placement | Similar, **not measured geometry parity** |
| Navigation/button paint | Blue filled active item with rounded corners, unselected items blend into dark sidebar | Blue selected rectangle; unselected buttons painted light gray | **Visible paint mismatch** |
| Typography | Clear hierarchy, larger headings and statistic values | Much smaller/visually different text and weights | **Visible font/metric mismatch**; font availability/DPI must be recorded |
| Cards | Thin outlines and smooth corners | White/irregular borders, different corner treatment | **Visible border/background mismatch** |
| Content surface | Consistent light gray outer area with white cards | Different background shades and white artifacts | **Visible paint mismatch** |
| Activity rows | Clean separators and aligned text | Similar division, different typography and spacing | **Paint mismatch; geometry requires readback** |

**Capture limitation:** the Qt screenshot has `Reportes` selected and the Tk screenshot has `Resumen` selected. Future image-diff tests MUST fix the same navigation state, content, window client size, CSS, installed fonts and DPR. These screenshots do not allow a valid numerical pixel-difference score.

## Source path and certified boundary

```text
PSX Markup / linked CSS / inline CSS
  → psx/css/parser.py, properties.py, cascade.py, markup.py
  → immutable ComputedStyle (+ authored/specified provenance)
  → psx/core/reconcile.py invokes renderer.apply_css
  → geometry: psx/css/geometry.py / Cinnamon bridges
  → native paint: psx/css/native_paint.py
       ├─ psx/renderers/qt/pyqt.py
       ├─ psx/renderers/tkinter/tkinter.py
       └─ psx/renderers/kivy/kivy.py
```

The CSS Core and historical 2026-10-21 certification expressly support a **bounded subset**, not universal widget background support or screenshot equivalence. See `docs/architecture/css-native-visual-paint-contract.md`, `css-native-component-capability-inventory.md` and `css-core-integral-certification-matrix.md`.

### Identified cross-backend gaps (source-backed)

| Priority | Property / surface | Qt path | Tk path | Kivy path | Consequence / required disposition |
| --- | --- | --- | --- | --- | --- |
| P0 | **Styled button background and radius** | Widget-local QSS applies authored `background-color` and `border-radius` | Linux/Windows `ttk.Button` uses instance `ttk.Style` plus state maps; theme may ignore paint. macOS uses classic `tk.Button` and owned Canvas | `Button` owns a rounded `canvas.before` paint and suppresses default texture | **Confirmed architectural reason for gray Tk buttons**; require deterministic instance-owned surface where ttk theme cannot comply, retaining native handle, keyboard focus, mouse activation, disable state and original unstyled appearance |
| P0 | **Rounded fills and corners** | QSS controls and semantic hosts | ttk frames are rectangular; opaque Canvas corner masks sample parent color; masking cannot clip arbitrary children | RoundedRectangle paint for semantic hosts and Button | Transparent corners/overlays and clipping require explicit tests against patterned/different-color parents, resize, descendants and reset |
| P0 | **Card and layout surface color** | Scoped QSS semantic background | ttk.Frame style + raised child Canvas; separate Aqua-specific ancestry pass | Owned `canvas.before` background | Theme-dependent overpaint/ancestor changes and Grid track surfaces can expose wrong fills; test exact user-supplied colors, never theme hardcoded palette |
| P1 | **Text family, size and weight** | QFont/QSS; weights may use numeric QSS on semantic hosts | Retained Tk Font for Text; numerical `font-weight` mapped to `bold` above threshold, otherwise `normal` | Kivy font resource / `bold` threshold | Shared value validation is broader than native weight representation; ensure available-font resolution and pixel metrics; document unsupported weights rather than claim full 100–900 fidelity |
| P1 | **Font family lists** | Semantic QSS can preserve comma-separated CSS family stack | `native_text_typography` chooses only the first face | Same first-family behavior; requires resolvable native resource | Missing first font must use deterministic supported fallback; parity cannot depend on arbitrary local defaults |
| P1 | **Side-specific border** | `native_side_border_styles` emits QSS border sides | Tk paints explicit sides on formatting hosts only with `tk.Frame` overlays | Kivy semantic/control paint primarily uses uniform `Line.rounded_rectangle` | A styled `border-bottom` is not automatically equivalent on Kivy; add owned side-stroke support or reject before rendering |
| P1 | **Control backgrounds beyond Button** | Qt control path emits CSS backgrounds for multiple controls | Tk control path principally guarantees a styled Button and semantic hosts | Kivy explicit background shape is added for Button and semantic hosts; other controls mostly retain native texture/background | Cross-adapter advertised coverage must be exact per component; avoid silently accepting declarations that cannot be projected |
| P1 | **Text line-height / alignment / padding** | Qt text document and QSS Button padding in supported paths | Tk Text overlay for explicit leading; ttk.Button padding includes native theme handling | Kivy `line_height` multiplier and Button padding | Native metrics, control insets, clipping and wrapping are not provably equal; read back geometry and native surface |
| P2 | **Interaction and reset** | Widget-local QSS, native states | ttk state maps / per-instance styles, optional Canvas overlays | Owned canvas groups and binding cleanup | Verify keyboard, hover/press, focus, enabled/disabled, keyed updates, removal, parent CSS refresh and unmount |
| P2 | **Per-platform DPI/theme/font** | Qt scaling varies with binding/OS | ttk themes and actual Tk build vary, including Aqua on macOS | Kivy DPI/font assets and graphics pipeline vary | Must record actual toolkit/build/theme/font/DPR; a single Linux CI pass is insufficient |

**Traceable source points:** Tk `_adapter_create` creates a `tk.Button` only on `darwin` and `ttk.Button` elsewhere; Tk `apply_css` uses `ttk.Style` / `style.map` on its standard Button path, while classic Button uses Canvas paint; Qt `_apply_css_projected` emits control-local QSS `background-color`, `border`, `border-radius` and `padding`; Kivy `apply_css` has a specifically owned rounded Button background; shared `native_text_typography` extracts the first font-family and allows numeric weights which Tk/Kivy project to binary bold/normal. Consult the corresponding functions in the code paths above.

## Acceptance policy proposed for fixing this branch

1. **Shared fixture:** one PSX Markup page and one stylesheet, deterministic dataset and selected navigation item. Cases should include dark sidebar, ordinary and active buttons, four cards, text, borders and activity separators, both 0 and nonzero radius, nested colored parents, and disabled/focused states.
2. **Source and computed-style checks:** compare the full resolved property maps and specified/declaration provenance for each component **before** native projection. No runtime backend may rewrite CSS into theme or platform constants.
3. **Cinnamon geometry:** compare exact logical box vectors, intrinsic measurements, border/padding/content rectangles, and Rust/Python parity. On native devices record DPR and justified device-pixel rounding differences; select tolerances explicitly before asserting them.
4. **Native paint readback:** assert user-authored color values from actual native styles or owned graphics instructions; then capture widget/client screenshots for independent color, corner mask, border, text and clipping inspection. Reading `ttk.Style.lookup` **alone** is insufficient: the active theme may paint differently.
5. **Lifecycle:** mount → keyed CSS update → ancestor CSS change → hover/press/focus/disabled → resize → CSS reset → unmount; assert widget identity, state and callbacks; check cleanup of Canvas, bindings, fonts and styles.
6. **Platforms:** Arch Linux X11 (Tk, Qt, Kivy), Ubuntu X11/Xvfb (same three), Windows (same three), macOS (same three when supported). Use all supported Qt Python bindings on suitable OS/Python environments. Record Python, Tk patch level/theme, Qt binding, Kivy version, OS, display server, DPI, device pixel ratio, fonts and snapshot hashes.
7. **Gating:** `scripts/ci/impact.py` and `tests/test_ci_impact.py` must route code or regression tests to all affected consumers. Native UI test jobs must actually run, not skip. Run exact-head-SHA CI and assess the screenshot/per-property matrix separately; only then close visual parity work. Do not merge to `develop` before owner review and green certification.

### Suggested implementation sequence (separate, independently testable changes)

- **First:** address styled `ttk.Button` background/radius on Linux and Windows with an instance-owned paint solution that does not alter the native appearance of *unstyled* widgets, keyboard interaction or accessible state. Remove any invented state colors; use only computed CSS.
- **Second:** deterministic semantic surface/border painting on Tk across themes; test parent background refresh, corners and scrollbar/child stacking.
- **Third:** native typography fidelity and font fallback/weight semantics, with measured text baselines and deliberate unsupported-value handling.
- **Fourth:** expand the explicitly supported visual capability matrix for Kivy and Tk side strokes/controls as separate contract-approved increments.
- **Fifth:** publish pinned visual baselines per OS/theme/DPR and enforce cross-backend visual regressions with reportable tolerances. Do not claim equivalence until hardware/OS evidence exists.

## Current CI is not a screenshot-parity certificate

At source SHA `cbbc455650ad251efbe6ae125cfab22547dc035f`, GitHub reports success for native-layout selective validation run [40371963482](https://github.com/Neuri-AI/PSX/actions/runs/40371963482), among other workflows. That validates **the jobs that actually ran**, not all three native backends across all four target OSes or screenshot similarity. The existing CSS certification matrix explicitly notes that Windows/macOS wheel/ABI checks do not constitute native visual equivalence.

**Current conclusion:** Qt/Tk screenshots substantiate a **visual fidelity regression**. Code inspection explains several mechanisms capable of producing it, most clearly native themed button painting. No Kivy screenshot or executable full-platform visual equivalence evidence was supplied, so no Kivy pixel-level PASS/FAIL claim is justified. All fixes belong on `fixes/psx-issues`; this audit documents the work and makes **no production change**.
