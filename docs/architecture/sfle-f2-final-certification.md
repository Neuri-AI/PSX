# SFLE F2 — formal final exit certification

**Signed decision (2026-10-11): F2 CLOSED, effective only after all five mandatory workflows complete successfully on the final documentation-only commit.**

Scope: the user-approved *frozen alpha CSS subset*, not universal CSS Flexbox, complete public capability manifest publication, or the F3 production renderer migration. The five user-approved workstreams are independently closed; the seven literal F1 §6 exit criteria have now been reconciled against executed tests instead of historical incomplete B1/F2.1 notes.

## Independent verification: same technical source SHA

Prior certified source and point-5 documentary baseline: [c2fce1ddb161a8ff4a168e94b1ba124592a0e92e](https://github.com/Neuri-AI/PSX/commit/c2fce1ddb161a8ff4a168e94b1ba124592a0e92e). All five runs show **status=completed / conclusion=success / identical head_sha**, confirmed 2026-10-11:

| Mandatory workflow | Actual run | Outcome |
| --- | --- | --- |
| SFLE Core (Python 3.10–3.13, Rust, differential, native PyO3, inventory) | [#38139119169](https://github.com/Neuri-AI/PSX/actions/runs/38139119169) | **GREEN**, 9/9 jobs |
| Chromium / Headless comparison | [#38139119157](https://github.com/Neuri-AI/PSX/actions/runs/38139119157) | **GREEN** |
| Live Qt/Kivy/Tkinter native UI | [#38139119160](https://github.com/Neuri-AI/PSX/actions/runs/38139119160) | **GREEN** |
| Windows + macOS Intel/ARM64 native wheels and frozen Python fallback | [#38139119156](https://github.com/Neuri-AI/PSX/actions/runs/38139119156) | **GREEN**, 3/3 OS jobs |
| PSX Alpha | [#38139119158](https://github.com/Neuri-AI/PSX/actions/runs/38139119158) | **GREEN**, 7/7 jobs |

**Final commit requirement:** this sign-off itself is a docs-only change on the F2 branch. The decision remains conditional until **5/5 mandatory workflows are completed/success on the identical final documentation head SHA**. Do not treat queued/in-progress runs or a prior commit as final approval. The final CI run URLs and SHA are reported in the release audit handoff, not fabricated in advance.

## Seven literal F1 §6 normative F2 exit requirements

| # | Exact normative requirement | Final disposition | Execution and evidence |
| --- | --- | --- | --- |
| 1 | a renderer-neutral, deterministic engine contract | **PASA** | Immutable normalized v1 snapshots; single pure SFLE result and bounded UI-thread measurement; `test_f2_acceptance_contract_red.py`, `test_remeasurement.py`, `test_f2_a01_active_remeasure_red.py`, Core #38139119169, real native UI #38139119160 |
| 2 | Rust primary with load-time Python fallback | **PASA** | Rust primary PyO3, missing/unloadable-native fallback, no retry after runtime failure; `test_f2_a08_missing_native_fallback_red.py`, `test_f2_a08_runtime_no_retry_red.py`, `test_sfle_f2_native_wheel.py`; cross-OS/frozen #38139119156 |
| 3 | matched capabilities and geometry | **PASA for frozen alpha corpus** | Identical Rust/Python admitted/rejected classes, four rectangles in 1/64px steps, stable diagnostic code/node; `test_sfle_f2_point2_capability_parity.py`, `test_sfle_f2_point2_final_certification.py`, `test_sfle_f2_point5_deferral_boundaries.py`; Core #38139119169 |
| 4 | headless/browser comparisons within the approved computational tolerance | **PASA for admitted CSS** | Chromium/Headless <=0.01 logical CSS px; Qt/Kivy/Tkinter native application <=1px; `test_sfle_f2_headless_oracle.py`, `test_sfle_f2_seeded_fuzz_red.py`, `test_sfle_real_toolkit_geometry.py`; Chromium #38139119157, native UI #38139119160, [point-3 certificate](sfle-f2-point3-final-certification.md) |
| 5 | documented deviations | **PASA** | Precise fixed alpha scope and unsupported CSS taxonomy, RED/GREEN history, native limitations and post-F2 approved CSS deferrals; [point 3](sfle-f2-point3-final-certification.md), [point 4](sfle-f2-point4-final-certification.md), [point 5](sfle-f2-point5-final-certification.md), [roadmap](../roadmap.md) |
| 6 | no unsupported-feature silence | **PASA for explicit alpha taxonomy** | Unknown declarations and known unsupported dependency graphs fail with matching Rust/Python diagnostics; two point-5 deferred negative classes fail closed, valid indefinite-percent cases preserved; `test_sfle_f2_negative_fuzz_red.py`, `test_sfle_f2_unsupported_taxonomy.py`, `test_sfle_f2_point5_deferral_boundaries.py`; Core #38139119169 |
| 7 | Native full integration and migration completion may be scheduled under F3, but the final design must enforce SFLE as the sole portable layout authority. | **PASA, F3 implementation reserved** | Typed geometry commit and readback/rollback, host-to-content identity, native Scroll viewport vs immutable SFLE content, nested scroll and coordinate transforms; `test_f2_point4_authority_red.py`, `test_f2_point4_cross_backend_contract.py`; [point-4 certificate](sfle-f2-point4-final-certification.md) |

These are the seven *literal* norms: the two following deferrals are separate **user-approved scope decisions**, not invented eighth/ninth exit criteria. The formerly listed FALLA rows described earlier evidence and are superseded by the final approved scope and later executed proofs. The normative **current table** is [sfle-f2-implementation.md](sfle-f2-implementation.md).

## Explicitly deferred CSS additions (not F3 work)

- **SFLE-CSS-01:** full aspect-ratio/replaced native intrinsic transfer — approved written deferral; retains certified definite-axis transfers.
- **SFLE-CSS-02:** fully intrinsically auto-sized multi-line Flex wrapping without a definite main-axis sizing constraint — approved written deferral; retains fixed-main-axis and capped wrapping cases.

Both remain in [docs/roadmap.md](../roadmap.md) without a scheduled later milestone. Rust/Python negative diagnostics were added RED first and confirmed GREEN. Neither item is claimed complete or silently added to F3.

## Explicitly excluded from F2 signoff

- Universal CSS Flexbox or full arbitrary CSS dependency coverage; this is an *alpha subset* certification only.
- Rewriting the production Qt/Kivy/Tkinter/Headless renderers, deleting Row/Column public APIs, retiring legacy native layout algorithms or migrating native Scroll events and offsets. These are F3.
- Publishing the currently closed public engine capability manifest; public release gating is separate from internal normalized alpha engine computation.
- Exhaustive live Windows/macOS native GUI readback or universal HiDPI validation; wheels/frozen fallbacks are cross-OS, whereas real widget geometry is tested under Linux/Xvfb.
- Relaxing LayoutUnit raw signed 32-bit saturation, 1/64px grid, <=0.01px logical and <=1px native tolerance thresholds.

## Decision

**All five workstream points CLOSED; all seven F1 §6 normative criteria PASA; both post-F2 CSS features explicitly DEFERRED. F2 CLOSED upon same-final-SHA mandatory CI success. F3 is the next implementation phase, not yet started.**
