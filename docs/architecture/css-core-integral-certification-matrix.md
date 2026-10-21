# CSS Core integral certification — property × renderer × operation matrix

**Stage:** P1.4.8. **Revision:** 1, 2026-10-21. **Disposition:** **OPEN** until direct executed receipts cover every advertised cell, excluded cells have verified fail-closed contracts, and the owner signs off. A successful workflow alone does not close this matrix.

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

**OPEN / evidence inventory initiated.** Existing bounded CSS functional/invalidation certifications and green repository workflows show strong prior coverage, but a complete independent operation-specific native release matrix has not yet been demonstrated. **P2 may be planned or audited in parallel**, but do not present P1/P1.4 as formally closed until the above gates are resolved.
