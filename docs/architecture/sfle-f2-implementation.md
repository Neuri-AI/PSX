# SFLE F2 — consolidated implementation and acceptance register

> **Single current status table** as of 2026-10-10. Verified code baseline: `387ab3b7fa69afcd85a77b8f6239e270b5024228` on `feat/sfle-f2-core`, PR #11.  
> **F2 is NOT complete and the public SFLE capability manifest remains CLOSED.** Numerical success of a restricted fixture is not evidence that the whole CSS feature is supported. No historical 4/8 or 5/8 progress counts are accepted.

## 1. Normative authority and scope

Precedence: [F1 final architecture](sfle-f1-final-architecture.md) (D-F1.1–D-F1.12, F1-RUST, F2.0–F2.4, F2 exit), [F1 box model](sfle-f1-box-model.md) (§§5.1–5.4), [F1 contracts](sfle-f1-contracts.md) (its F2.A–D labels are NOT authoritative), [F1 props/lengths](sfle-f1-props-lengths.md), [SFLE](sfle.md) (§§5, 9, 10), and [CSS Flexbox Level 1](https://www.w3.org/TR/css-flexbox-1/).

Approved first-alpha acceptance IDs: A01–A10; CSS cyclic sizing allowlist C01–C06; negative cycle classification C99. Orthogonal automatic sizing is **in scope** (A01). Rust-primary PyO3/maturin with load-time Python fallback is **F2 exit work**, not an optional later enhancement. No feature is considered supported merely because one engine accepts it. A native Rust runtime failure must never be retried in Python during a transaction. Preserve AUTO/NONE/keyword tags and indefiniteness, prevent stale-generation commits, maintain exact box identities and line memberships, and keep `measurement_error`, `engine_error`, and `geometry_commit_error` separate. Never update Row/Column/Scroll or the public capability manifest during F2.

## 2. Acceptance table (one current table only)

Meaning of **test PASS**: the named test actually ran and passed in the referenced CI. **Acceptance FAIL**: one or more normative parts of that case still lack proof, even when a restricted test is green. **NO TEST** means the required integration/fixture does not exist. This register deliberately avoids progress-percentage metrics.

| ID | Required behavior and concrete expected numeric value | Python actual test | Rust actual test | Chromium / parity evidence | F2 acceptance |
| --- | --- | --- | --- | --- | --- |
| **A01** | Real text wraps from **2 to 3 lines** after 120→80px allocation, line-height 20px; final root/column/text **60px** | **PASS** `test_a01_compute_red.py`, active `test_f2_a01_active_remeasure_red.py[python]` | **PASS** Rust pure compute and active `[rust]` | **PASS** `test_sfle_f2_live_text_chromium.py` uses independent DOM text measurements and compares complete geometry at 0.01px; 2 calls | **PASS for bounded pure+Chromium acceptance**; production toolkit measurement/lifecycle integration remains F2 work |
| **A02** | Inline intrinsic root and leaf width **100px** | **PASS** named A02 compute test | **PASS** Rust A02 compute test | **PASS** differential and `test_sfle_f2_css_reference_matrix.py[A02]` | **PASS for listed numeric scenario**, broader intrinsic contribution matrix remains |
| **A03** | Indefinite percentage with intrinsic parent/child height **30px** | **PASS** named A03 compute test | **PASS** Rust A03 compute test | **PASS** differential and `test_sfle_f2_css_reference_matrix.py[A03]` | **PASS for listed CSS context**; other cyclic dependencies fail closed or need classification |
| **A04** | Text flex-grows 100→150px, actual 3→2 lines; parent final height **40px** (20px line-height) | **PASS** active `test_f2_a04_active_remeasure_red.py[python]` (2 measurements), plus supplied-metric geometry case | **PASS** active `[rust]` from same coordinator | **PASS** `test_sfle_f2_live_text_chromium.py[A04]`, separate measurement and geometry errors at 0.01px | **PASS for pure+browser active remeasurement**, UI-thread production adapter remains unverified |
| **A05** | Two leaves shrink **50→35px**, live text wraps 2→3 lines; parent final height **60px** (supplied-height separate scenario **120px**) | **PASS** active `test_f2_a05_active_remeasure_red.py[python]` (2 calls per leaf) | **PASS** active `[rust]` | **PASS** `test_sfle_f2_live_text_chromium.py[A05]` and static `test_sfle_f2_css_reference_matrix.py[A05]` | **PASS for pure+browser active remeasurement**, UI-thread production adapter remains unverified |
| **A06** | Obsolete generation produces **0 commits**; current generation **17** | **PASS** `test_A06_generation_is_preserved_by_pure_layout_result` and `test_A06_stale_generation_never_commits_native_geometry` | **PASS** `f2_a06_red.rs`; Rust pure compute cannot make UI commits | **PASS** differential for generation; Python lifecycle guard verifies zero stale commits | **FAIL** native production-renderer generation integration not certified |
| **A07** | Bounded fixed point root height **60px**, max iterations **8**; `A→B→A` raises explicit error | **PASS** `test_A07_convergent_auto_layout_is_finite`, `test_A07_bounded_two_step_oscillation_rejected` | **PASS** `f2_a07_red.rs` including `acceptance_a07_bounded_oscillation_is_rejected` | **PASS** pure corpus/guards; **NO TEST** full CSS dependency fixed-point coordinator | **FAIL** integrated sizing/convergence |
| **A08** | PyO3/maturin Rust-primary at load; Python fallback on missing wheel; never retry a native transaction | **PASS** `test_f2_a08_native_selector_red.py`, `test_f2_a08_missing_native_fallback_red.py`, `test_f2_a08_runtime_no_retry_red.py`, `test_f2_a08_bad_native_schema_red.py` | **PASS** optional `python` PyO3 feature, immutable v1 ABI, release wheel on Linux, 17 installed-extension tests | **PASS** process differential **27**, installed abi3 wheel **17**; optional native module is `_sfle_native`; no Windows/macOS wheel evidence yet | **PASS Linux backend contract**; F2 cross-platform packaging/test matrix outstanding |
| **A09** | Exact logical order, RTL/LTR row positions LTR **a.x=0,b.x=20**, RTL **a.x=100,b.x=70** | **PASS** `test_A09_directional_positioning_preserves_identity` (two variants) | **PASS** shared differential fixture execution | **PASS** LTR/RTL differential at 0.01px; existing Chromium cases are restricted and some assert 0.05px, not full 0.01px A09 matrix | **FAIL** full browser orientation/wrap matrix |
| **A10** | Independent max errors for measurement, engine and native commit; missing comparison is **None**, never fictitious 0 | **PASS** `test_f2_a10_quantitative_channels_red.py` (1px vs 2px vs 3px) and original result-field test | **PASS** wire result carries independent error fields | **PASS** Chromium live text A01/A04/A05 reports separate 0.01px measurement and engine errors; native commit remains **None** absent observation | **PASS pure/browser error separation**; toolkit commit calibration outstanding |
| **C01–C03** | Content-based percentage flex basis; auto basis; post-flex descendant **60px** at 50% of 120px | **PASS** `test_f2_cycle_corpus_runtime_red.py` | **PASS** `f2_cycle_corpus_runtime_red.rs` | **PASS** differential, numeric corpus | **FAIL** broader CSS cycle verification/Chromium fixtures |
| **C04** | Intrinsic percentage gap contributes **0px**, final used gap **4px**, second child **x=24px** | **PASS** real compute corpus | **PASS** real Rust compute corpus | **PASS** differential + `test_sfle_f2_css_reference_matrix.py[C04]` | **PASS listed scenario**; additional intrinsic phase probes pending |
| **C05** | Auto ancestor with percent child height: measured parent and child **30px** | **PASS** real compute corpus | **PASS** real Rust compute corpus | **PASS** differential + `test_sfle_f2_css_reference_matrix.py[C05]` | **PASS listed context**; unlisted nested dependencies must fail closed |
| **C06** | Percentage padding-top 10% of containing inline 400px = **40px** | **PASS** real compute corpus | **PASS** real Rust compute corpus | **PASS** differential + `test_sfle_f2_css_reference_matrix.py[C06]` | **PASS listed scenario**; more edge combination coverage pending |
| **C99** | Explicitly reject unsupported multi-node percent cycle with `SFLE_UNSUPPORTED_FEATURE`, node `a`; supported A01 never raises that generic error | **PASS** paired C99 positive/negative tests | **PASS** paired Rust C99 tests | **PASS** differential diagnostic parity; **N01–N03** distinct negative patterns are also executed | **PASS four known negative classes**, but no proof yet that **all** unlisted cyclic percentage graphs are rejected |
| **N01–N03** | Three unsupported indefinite percentage references: inline width, percent minimum, and nested column percent-basis/descendant cycle | **PASS** each separate `test_f2_n0*_cycle_red.py` | **PASS** each separate `f2_n0*_cycle_red.rs` | **PASS** differential matching error code, node identity and cycle kind | **PASS three tested rejection patterns**, exhaustive rejection remains an explicit open gate |

**The public alpha capability manifest remains CLOSED.** Passing individual numeric scenarios does not certify every value in a CSS feature family. Required remaining work includes native toolkit integration, exhaustive negative cycle classification and cross-platform wheel builds.

## 3. Source of truth for acceptance fixtures

Single source: `tests/sfle/fixtures/f2_alpha_acceptance.json` (schema 1, explicit IDs, normalized tree, measurement dimensions and expected numeric outcomes). Structure-only validation by `tests/sfle/test_f2_corpus.py` and `rust/sfle-core/tests/f2_acceptance_corpus.rs` is **ZERO functional acceptance coverage**. Real compute execution is provided separately by `tests/sfle/test_f2_acceptance_contract_red.py`, `tests/sfle/test_f2_cycle_corpus_runtime_red.py`, `rust/sfle-core/tests/f2_a01_red.rs`, `rust/sfle-core/tests/f2_a02_red.rs` through `f2_a07_red.rs`, and `rust/sfle-core/tests/f2_cycle_corpus_runtime_red.rs`.

The **differential runner** `tests/interop/test_sfle_f2_differential.py` compiles `rust/sfle-core/src/bin/sfle_f2_fixture_runner.rs`, serializes each identical versioned immutable snapshot, invokes Python and the actual Rust crate, and asserts identity/order and all four box rectangles (content/padding/border/margin) within 0.01px, plus case-specific numeric expectations and C99 diagnostic parity. It is a **process-level verification binary**, NOT PyO3 runtime selection. Browser `tests/browser/test_sfle_f2_engine_chromium.py`, `test_sfle_f2_live_text_chromium.py` and `test_sfle_f2_css_reference_matrix.py` are all collected by the Chromium workflow; active wrapping is measured in a real DOM with deterministic monospace font. The native wheel is additionally tested by `tests/interop/test_sfle_f2_native_wheel.py`.

### RED discipline

RED tests remain ordinary failing tests until implementation fixes them—**never** use `xfail`, skipped tests or a conditional CI exclusion. Rust A02–A07 RED cases were introduced in separate commits before fixes and all failed on the Rust placeholder in run [38079805151](https://github.com/Neuri-AI/PSX/actions/runs/38079805151) with `cargo test --no-fail-fast`. The historical A01 Rust RED before the earliest orthogonal helper fix was not witnessed; its later full Rust compute RED was added before the Rust normalized compute implementation. Tests may now be green without retroactively claiming evidence that did not exist.

## 4. Verified GitHub Actions evidence

Confirmed on **code commit `387ab3b7fa69afcd85a77b8f6239e270b5024228`**:

| Workflow / job | Actual CI result |
| --- | --- |
| [SFLE Core 38083329692](https://github.com/Neuri-AI/PSX/actions/runs/38083329692): Python 3.10–3.13 | **PASS**; Python 3.12 **357 passed, 0 skipped**, includes Qt |
| Same core: native Rust + normalized alpha integration | **PASS** |
| Same core: Rust/Python differential with active measure callbacks and four negative cycle cases | **PASS: 27 tests** |
| Same core: Linux CPython 3.12 maturin release wheel, abi3 >=3.10, installed native selector and parity | **PASS: 17 tests** |
| [Chromium 38083329696](https://github.com/Neuri-AI/PSX/actions/runs/38083329696): actual text wrapping and independent CSS matrix | **PASS: 24 tests**, A01/A04/A05 Python and Rust, A02/A03/A05 C04–C06, A10 error comparison |
| [PSX Alpha 38083329708](https://github.com/Neuri-AI/PSX/actions/runs/38083329708): original core, PySide6 offscreen, packaging | **PASS**, no main testing jobs omitted |

RED evidence: active A01/A04/A05 yielded six independent failures on both backends before the coordinator existed in [SFLE run 38081941382](https://github.com/Neuri-AI/PSX/actions/runs/38081941382); N01/N02/N03 failed on their unclassified cycles in [run 38082464002](https://github.com/Neuri-AI/PSX/actions/runs/38082464002); A10 error calibration failed on `NotImplementedError` in [run 38083245493](https://github.com/Neuri-AI/PSX/actions/runs/38083245493). No xfail/skip or excluded-red-test policy.

**Precise limit:** `compute_with_width_measurements` is a synchronous generation-scoped callback coordinator used in offscreen/browser tests. It does not yet use the production UI scheduler/adapter. Provisional measurements are explicitly noncommittable; the final call remains strict. The browser tests independently measure wrapping text in Chromium. `measurement_error` and `engine_error` are separate quantitative values; `geometry_commit_error` stays `None` without a native commit observation.

## 5. Explicit deferred-feature register

| Feature | Why deferred | Required diagnostic on both engines | Normative placement |
| --- | --- | --- | --- |
| Replaced elements with `aspect-ratio` transfer | Intrinsic transferred size suggestion, replaced-element minima and cross-axis aspect sizing are not implemented in the restricted alpha | `SFLE_UNSUPPORTED_FEATURE` (not warning/approximation) | **Pending work within F2**, not assigned a named subphase by F1. F1 final §6 defines F2.2 normative sizing and F2.3 browser conformance; adding this feature needs explicit new F2 acceptance scope, not fictional “F2.2 extension phase” |
| Intrinsically auto-sized containers with `flex-wrap` | Cyclic intrinsic main/cross sizing with line formation; fixed-size wrapped flex is separately supported by existing restricted kernels | `SFLE_UNSUPPORTED_FEATURE` | **Pending within F2.2 sizing/line formation**, then **F2.3 browser conformance**, per F1 final §6; this is not F3 migration |
| Vertical writing modes | Approved D-F1.8 requires horizontal writing LTR/RTL only | `SFLE_UNSUPPORTED_FEATURE` | Out of first F2 alpha; later architectural authorization required |
| Row/Column public removal, Scroll migration | F2 only defines inventory/adapter contracts, cannot break public PSX during pure engine phase | No F2 public mutation | F2.4 **planning**, F3 **actual removal/integration**, per F1 final §5–§6 |

## 6. Remaining mandatory F2 gates

1. **Production integration**: connect live width-dependent remeasurement to Qt/Kivy/Tkinter UI-thread adapters and atomic generation-safe native commits; validate real `geometry_commit_error` observations. The pure/browser A01/A04/A05 RED gates now pass, but not this adapter lifecycle gate.
2. **Exhaustive unsupported-cycle policy**: C99 + N01–N03 currently prove four distinct rejections and prevent global placeholder false positives. Other indefinite percentage dependency graphs still need explicit negative/property-based tests before claiming fail-closed exhaustiveness.
3. **Wheel distribution**: PyO3/maturin Linux abi3 wheel is built, loaded and tested; still require Windows/macOS CI wheel build/installation and source/frozen import validation. Python fallback is selected once only on import failure; native runtime exceptions propagate.
4. **Conformance matrix**: broaden RTL/reverse, wrapped fixed-size layouts and complete percentage/intrinsic browser comparisons beyond the checked examples.
5. **F2.4 inventory/plan** for Row, Column, Scroll adapter migration; actual removal remains F3. Keep capability manifest CLOSED until full exit parity is established.

No new architecture phase is invented: aspect-ratio remains pending within F2 sizing scope and auto-sized wrap within F2.2/F2.3, with `SFLE_UNSUPPORTED_FEATURE` in both engines and explicit approval needed before implementation.
