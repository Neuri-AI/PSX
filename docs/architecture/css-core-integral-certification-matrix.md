# CSS Core integral certification — property × renderer × operation matrix

**Stage:** P1.4.8. **Revision:** 2, 2026-10-21. **Disposition:** **CERTIFIED for the explicitly bounded native CSS Core support subset** at implementation SHA `fcaef8b7abb34bffefaa74cddb0f910864f8d52a`; 13/13 repository workflows and 20/20 required native jobs succeeded. Release-wide screenshot/device/theme equivalence and cross-OS native paint are **not advertised or certified**. New functionality requires separate operation-level evidence.

**Code baseline:** PSX PR #48, `feature/universal-box-model-and-styling`. Current implementation includes P1.4.6 functional native visual projection and P1.4.7 invalidation/performance certification. Those receipts are prior evidence, **not** a substitute for independent P1.4.8 acceptance.

## Operations and proof standards

- **M:** initial mounted native projection and observable readback (not merely computed CSS).
- **U:** keyed or equivalent in-place update preserves native identity and correct paint.
- **R:** explicit CSS removal restores native defaults and releases previous paint ownership.
- **S:** state, focus, selection, event callback and disable interactions retain behavior.
- **L:** layout/measurement invalidation or paint-only no-op honors Cinnamon's authority.
- **N:** invalid and unsupported value is explicitly rejected, or is documented as outside the claimed subset with an exercised diagnostic.
- **E:** evidence executed at the immutable certification SHA on the target backend/platform.

In the table below, `T` means a named test implementation exists; `C` means a *scoped earlier-phase* native certification exists; `G` means P1.4.8 independent operation-specific final evidence is **missing**. `—` is a documented feature exclusion, not a PASS. No row marked `T/C` should be read as final P1.4.8 certified until E and applicable operations have been audited.

| CSS property / family | Native scope | Qt / four bindings | Tkinter | Kivy | Operations requiring final signoff |
| --- | --- | --- | --- | --- | --- |
| `color` | text-bearing native controls and semantic hosts | T/C | T/C | T/C, excluding Checkbox text | M U R S N E |
| `background-color` | semantic formatting hosts only | T/C | T/C | T/C | M U R N E |
| `font-family` | controls with font support and available resources | T/C | T/C | T/C, loadable font restriction | M U R S L N E |
| `font-size` | positive pixel-native typography | T/C | T/C | T/C | M U R S L N E |
| `font-weight` | native 400/700 subset | T/C | T/C | T/C, control-specific exclusions | M U R L N E |
| `line-height` | supported native Text and Button cases | T/C | T/C | T/C | M U R L N E |
| `text-align` | left, center, right on supported text widgets | T/C | T/C | T/C | M U R N E |
| `border-width` + `border-color` | explicit colored stroke with positive px width | T/C | T/C | T/C, excluding Qt Badge border | M U R S N E |
| `border-radius` | one nonnegative px radius, no clipping guarantee | T/C | T/C | T/C | M U R N E |
| `padding`, `margin`, `min/max`, `width/height` | Cinnamon layout (not platform-native geometry control) | T/C | T/C | T/C | M U L N E |
| CSS class/id, cascade, specificity, inheritance | shared resolver + projection | T/C | T/C | T/C | M U R N E |
| `<link>` stylesheets / `@import` / frozen resources | shared resolver + Qyro resource adapter | T/C | T/C | T/C | M U N E |
| Font/theme/DPI/resource invalidations | native measurement + Cinnamon incremental solve | T/C | T/C | T/C | U R S L E |
| Native teardown / keyed ownership | all native controls and semantic hosts | T/C | T/C | T/C | U R S E |

### Explicit N/A or excluded capabilities

- **Headless:** CSS computed-style, geometry and validation can be certified; native foreground/background/pixel paint is not applicable. Never count Headless as a native pixel rendering pass.
- **Native arbitrary control backgrounds:** not publicly advertised; semantic host background is in scope.
- **Kivy Checkbox foreground, Qt Badge generic border, universal CSS text justification, all-native percent/per-corner radius, clipping of nested children:** not supported. Review negative test evidence before marking N=PASS.
- **RadioGroup inside an unmeasured Cinnamon Block:** not certified; currently the supported native group test mounts through a non-SFLE group host.
- **Browser-identical font shaping / pixel snapshots on all DPI/theme/platform combinations:** not advertised as browser equivalence. Native device readback and documented tolerance are nevertheless required wherever the public visual contract claims a paint operation.
- **Advanced position/float/overflow/margin collapse:** deferred to separate layout-extension backlog; not P1.4.8 gates for the currently advertised bounded CSS Core.

## Existing direct tests to review

**Native mounted, same executable in Qt bindings, Tkinter, Kivy:** `tests/test_mounted_grid_native_renderers.py` includes `test_native_css_typography_updates_text_without_replacing_widget`, `test_native_multiline_css_line_height_follows_cinnamon_measurement`, `test_native_button_css_typography_is_applied_and_reset`, `test_native_input_css_inherits_font_and_alignment_without_remount`, `test_native_heading_paragraph_css_cascade_and_keyed_font_update`, `test_native_css_foreground_applies_to_pascal_and_html_controls`, `test_native_css_border_on_pascal_and_html_controls`, `test_native_rounded_border_pascal_and_html_controls`, `test_native_semantic_rounded_border_and_background_updates`, `test_native_css_control_border_updates_and_owned_paint_cleanup`, `test_native_css_style_updates_keep_live_control_callbacks`, `test_native_select_css_retains_selection_and_latest_user_callback`, `test_native_textarea_css_preserves_selection_readonly_and_edit_callbacks`, `test_native_css_teardown_releases_active_control_paint`, and `test_native_css_paint_burst_does_not_commit_cinnamon_geometry`.

**CSS source and rejected values:** `tests/css/test_native_paint.py`, `tests/css/test_parser_and_cascade.py`, `tests/css/test_effects.py`, `tests/test_css_markup_census.py`, `tests/test_markup_css_binding.py`; frozen and linked resource paths must also be checked against executed Qyro Engine/CLI integration artifacts, not inferred from mock resolvers.

**Incremental geometry and resource lifetime:** `tests/test_incremental_result_reuse.py`, `tests/test_native_measurement_invalidation.py`, `tests/test_native_resource_invalidation.py`, `tests/test_native_intrinsic_cache.py`, and native renderer rollback/ownership suites.

## Independently retrieved per-backend native receipts

**Receipt source:** [successful native layout workflow run 39664256939](https://github.com/Neuri-AI/PSX/actions/runs/39664256939), implementation SHA `59046cab35adaa3953f6ef88dbcaf0aeba16063a`. Six distinct `public-native-*.xml` artifact sets were downloaded and independently parsed (not inferred from the success checkmark). The CSS/typography/border/stylesheet family filter yields the following **318 individually identified test/backend records**:

| Backend | Passed | Skipped | Failed | Scope |
| --- | ---: | ---: | ---: | --- |
| PySide6 | 53 | 0 | 0 | 53 named native CSS/visual testcases |
| PyQt6 | 53 | 0 | 0 | Same tests on independent Qt 6 binding |
| PySide2 | 53 | 0 | 0 | Same tests on Qt 5 binding |
| PyQt5 | 53 | 0 | 0 | Same tests on independent Qt 5 binding |
| Tkinter | 52 | 1 | 0 | One Qt-specific QSS test explicitly N/A |
| Kivy | 51 | 2 | 0 | Qt-specific QSS N/A; multiline leading test skipped |
| **Total** | **315** | **3** | **0** | **318 retrieved XML records** |

Skips are **not** successes. The Kivy multiline `line-height` skip is a material uncovered cell if native multiline leading is advertised as implemented and must be either covered by a separate actually executed Kivy-specific test or explicitly narrowed in the public support contract. Per-backend public JUnit is **one evidence layer**, not a substitute for verified font/theme/DPI and screenshot sweeps; some separately executed geometry/native DPI jobs have no per-property paint readback. This audit does not establish coverage on every supported operating system/Python/binding combination.

Exact artifact IDs at the same SHA: [PySide6 12375318668](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12375318668), [PyQt6 12376796439](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12376796439), [PySide2 12376606831](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12376606831), [PyQt5 12376481945](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12376481945), [Tkinter 12375173775](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12375173775), [Kivy 12377172109](https://github.com/Neuri-AI/PSX/actions/runs/39664256939/artifacts/12377172109).

**Reproducibility:** Download each ZIP, parse `public-native-*.xml` `testcase` elements, and cross-check `failure`, `error` and `skipped` child nodes. Filter names containing `css`, `font_measurement`, `line_height`, `rounded_border` or `stylesheet`. The exact name/backend/result rows are also exported as a machine-readable CSV in the current certification conversation. Never silently upgrade earlier-SHA receipts into later-SHA acceptance.

## Remaining independent exit blockers

1. Compile **per-property × component × backend × operation** tested cases from public capability inventory, not just family-level named tests. Audit coverage for CSS removal/defaults, state-driven styling, invalid property values and every advertised renderer.
2. Attach **executed**, same-SHA CI JUnit or equivalent receipts proving those specific test cases ran (no skipped/cancelled), including supported Python versions, Windows/macOS/Linux applicability and any explicit exclusions.
3. Verify CSS visual readback, DPI/theme sweeps, unsupported diagnostics and resource frozen-mode pathways in their real supported environments. Track remaining gaps instead of treating unexecuted screenshot comparisons as evidence.
4. Validate `scripts/ci/impact.py` and selector tests for any newly discovered suite, obtain clean exact-SHA product gates and full independently reported P1.4.8 certification.
5. Obtain explicit owner signoff on the versioned matrix and release-bound limitations before marking the stage closed. Do not merge PR #48 without separate authorization.

## Current decision

**Scoped certification ACCEPTED:** the supported native CSS property subset is explicitly mapped to behavior-specific executed tests at `fcaef8b7abb34bffefaa74cddb0f910864f8d52a`; failed/omitted/out-of-scope combinations are not represented as successes. Cross-platform release certification, pixel-equality, unsupported CSS extensions, and exhaustive physical-device/theme sweeps remain excluded from this *bounded* support promise and are tracked separately under P4 or the CSS extension backlog. No PR merge is authorized by this certificate. **P2 may be planned or audited in parallel**, but do not present P1/P1.4 as formally closed until the above gates are resolved.


## Executed P1.4.8 native cross-backend verification (2026-10-21)

**Exact executable revision:** `fcaef8b7abb34bffefaa74cddb0f910864f8d52a`. [View immutable commit checks](https://github.com/Neuri-AI/PSX/commit/fcaef8b7abb34bffefaa74cddb0f910864f8d52a/checks).

**Workflow result:** 13/13 successful; no failed or pending workflows. The native-layout workflow executed all 20 jobs successfully, including per-binding PySide6/PyQt6/PySide2/PyQt5 Qt tests, Tkinter, Kivy, Headless, Rust/Python differential, browser geometry oracle, Windows ABI, macOS ABI and artifact aggregation. These independent successful CI jobs do not prove native CSS painting on Windows/macOS; the binding-specific painted-widget readback runs on its configured Linux native display environment.

**Additional per-property native smoke tests:** `test_native_css_certified_background_update_and_reset` executes three colors (`#123456`, `#abcdef`, `#ff0000`) for every applicable Qt, Tkinter and Kivy native backend, verifying initial native CSS/ttk/canvas readback, keyed update with unchanged widget identity, and removal/reset. Kivy reads the renderer-owned `_psx_css_paint[2]` Color instruction rather than an invented `_psx_css_paint_color` attribute. The first attempt detected the incorrect assumption and failed Kivy; the corrected exact SHA above passed the complete workflow. The `test_kivy_multiline_css_line_height_keeps_native_measurement_revision_and_identity` path separately proves Kivy line-height ratio, font-revision update, keyed identity and restoration of the default. The Qt/Tk multiline test remains inapplicable to Kivy; its skip is not counted as a pass.

### Direct per-operation test mapping (certified bounded subset)

| CSS property and operation | Backend | Executed native testcase(s) | Verified observable |
| --- | --- | --- | --- |
| `background-color`, M/U/R | All six native bindings | `test_native_css_certified_background_update_and_reset`; `test_native_semantic_named_red_rounded_background_without_border` | Qt QSS, Tk instance-scoped theme background, Kivy owned canvas Color; in-place update and removal |
| `color`, M/U/R/S | All six | `test_native_css_foreground_applies_to_pascal_and_html_controls`; `test_inherited_css_color_survives_native_disabled_state_transitions`; `test_native_text_controls_css_foreground_change_and_style_removal` | Native foreground, inheritance, enabled state, update and reset |
| `font-family`, `font-size`, `font-weight`, M/U/R/L | All six subject to documented component exclusions | `test_native_css_typography_updates_text_without_replacing_widget`; `test_native_button_css_typography_is_applied_and_reset`; `test_native_control_font_measurement_revisions_are_incremental` | Native font ownership, keyed updates, reset and remeasurement |
| `line-height`, M/U/R/L | Qt/Tk | `test_native_multiline_css_line_height_follows_cinnamon_measurement`; `test_native_text_line_height_and_content_measurement_revision` | Actual native multiline readback and Cinnamon revision |
| `line-height`, M/U/R/L | Kivy | `test_kivy_multiline_css_line_height_keeps_native_measurement_revision_and_identity`; `test_native_text_line_height_and_content_measurement_revision` | Native ratio 36/18 and 45/18, resets on style removal |
| `text-align`, M/U/R | Bounded text-bearing native controls | `test_native_input_css_inherits_font_and_alignment_without_remount`; `test_native_button_css_typography_is_applied_and_reset` | Native alignment and identity |
| `border-color` / `border-width`, M/U/R | All six subject to Qt Badge exclusion | `test_native_css_control_border_updates_and_owned_paint_cleanup`; `test_native_css_border_on_pascal_and_html_controls`; `test_native_css_teardown_releases_active_control_paint` | QSS, owned Tk edges, owned Kivy stroke lifecycle |
| `border-radius`, M/U/R | All six for documented box/control subset | `test_native_rounded_border_pascal_and_html_controls`; `test_native_semantic_rounded_border_and_background_updates` | Native per-backend radius update; clipping excluded |
| CSS sources, cascade and linked stylesheet operations | Shared CSS resolver (native projection separate) | `tests/test_css_markup_census.py`; `tests/test_markup_css_binding.py`; `tests/css/test_parser_and_cascade.py` | class/id, stylesheet import, precedence and invalid values |
| Measurement and layout context invalidation, U/L | All applicable renderers | `test_native_css_paint_burst_does_not_commit_cinnamon_geometry`; `test_native_control_font_measurement_revisions_are_incremental`; `tests/test_incremental_result_reuse.py` | Paint-only skips Cinnamon commits, font/size changes commit, unrelated contexts reused |
| Native state/teardown, S/R | All applicable renderers | `test_native_css_updates_preserve_control_state_and_owned_styling`; `test_native_select_css_retains_selection_and_latest_user_callback`; `test_native_textarea_css_preserves_selection_readonly_and_edit_callbacks`; `test_native_css_teardown_releases_active_control_paint` | Selection, focus-capability, callbacks, cleanup |
| Unsupported CSS values, N | Shared projector; backend errors depend on applicability | `tests/css/test_native_paint.py` | Deterministic explicit diagnostics for percent radius, unsupported alpha, weights, text justification |

### DPI, theme and supported-platform evidence interpretation

- The native Qt SFLE parity job runs a **fresh process** with `QT_SCALE_FACTOR=1.5` as well as default device-pixel settings. CSS tests on semantic hosts and controls are executed on that Qt scale environment, including radius, background, typography, geometry and update/teardown assertions.
- Tk, Kivy and Qt native CI executes under their respective toolkit theme/font defaults. Existing semantic style/theme invalidation tests distinguish external changes from self-generated paint changes. There is **no evidence for all OS/system-theme combinations**, so cross-OS pixel parity is explicitly *not certified*.
- macOS (including Intel) and Windows workflow jobs verify distribution wheel/native-Python ABI compatibility, **not Qt/Tk/Kivy native visual equivalence**. Those claims must remain separate.
- The portable advertised CSS Core is **bounded native property projection**; full browser-matching font rasterization, arbitrary system-theme colors, universal color-alpha control backgrounds, hardware-specific screenshot equality and universal DPI sweeps are *outside that supported contract*. Do not label them as PASS.
- Full cross-platform smoke/release sign-off, long-lived process memory safety and broader system themes remain P4/P2 release criteria. These do not change the bounded Linux native CSS property implementation demonstrated at this SHA.

**Certification rule:** this table records the directly executed **bounded CSS Core operations** and their exclusions. It does not license a statement that every OS/theme/device pixel has been screenshot-verified. Owner authorization to complete P1.4 applies to this documented subset only; any enlargement of public advertised support requires new executable tests and updated receipts.
