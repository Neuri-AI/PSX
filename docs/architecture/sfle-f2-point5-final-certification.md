# SFLE F2 — Point 5 final scope-decision certificate

**Decision:** P5 CLOSED as of 2026-10-11. F2 remains OPEN pending independent
seven-gate F1 §6 normative closeout. No previous point 1–4 is reopened.

## Written approvals (2026-10-11)

The user expressly approved two **separate post-F2 CSS enhancements**:

- **SFLE-CSS-01:** full `aspect-ratio` and replaced-element transferred
  intrinsic sizing (images and media); **DEFERRED — APPROVED**.
- **SFLE-CSS-02:** intrinsically `auto`-sized Flex `flex-wrap`
  with multi-line intrinsic sizing; **DEFERRED — APPROVED**.

Durable entries and requirements live in [PSX roadmap](../roadmap.md#pending--sfle-css-extensions-after-the-f2-alpha-scope).
Their future milestone is not yet scheduled; they are **not** part of
F3's Qt/Kivy/Tk/Headless renderer migration.

## Approved F2 capability boundary

Do not silently accept out-of-scope CSS, fabricated coordinates or
unmeasured sizing. The two explicit deferred negative families are:

1. **Unmeasured replaced aspect-ratio leaf:** both specified dimensions
   auto, no native intrinsic data and no parent/item cross-axis stretch
   to establish a valid transfer. Report `SFLE_UNSUPPORTED_FEATURE`
   with that leaf's node ID in Rust and Python.
2. **Unbounded intrinsic auto-wrap:** wrapped row/column (including
   reverse variants), main axis unresolved and no definite pixel
   max-size cap. Report `SFLE_UNSUPPORTED_FEATURE` at the wrapping
   Flex node in Rust and Python.

**Preserve bounded already-certified support:** definite-axis ratio
transfers, definite-main-axis wrap, and `width:auto` with a definite
`max-width` wrap cap. No blanket `aspect_ratio` or `wrap` ban.
Remaining unlisted CSS graphs must obey the established fail-closed
capability taxonomy, without pretending this narrowly scoped test
matrix certifies universal CSS conformance.

## Real test evidence

- **Independent RED-first test commit:**
  [`8ce11c5`](https://github.com/Neuri-AI/PSX/commit/8ce11c5a6922423269026be01fc066875d4eb2e0);
  [RED SFLE Core #38138393455](https://github.com/Neuri-AI/PSX/actions/runs/38138393455)
  proved **8 invalid deferred graphs** were silently accepted, with
  563 existing differential cases passing. These failures were
  observed **before** the engine guards were added.
- **Guard changes:** `psx/sfle/compute_alpha.py` and
  `rust/sfle-core/src/compute_layout.rs` now reject both unsupported
  classes with matching `SFLE_UNSUPPORTED_FEATURE` and source node IDs.
  The first guard exposed a legitimate existing max-width-bounded
  wrapped case; it was narrowed, not deleted or xfailed.
- **Mandatory differential tests:**
  `tests/interop/test_sfle_f2_point5_deferral_boundaries.py`
  (8 unsupported cases and 3 positive support cases) is included in
  `.github/workflows/sfle-core.yml`; no skip/xfail.

## Mandatory CI on one immutable code commit

**Certified code SHA:**
[`296d1a2e5228166de0aa3954da957c8488f5780c`](https://github.com/Neuri-AI/PSX/commit/296d1a2e5228166de0aa3954da957c8488f5780c).

| Workflow | Run | Result |
| --- | --- | --- |
| SFLE Core (Rust, Python 3.10–3.13, 572 differential tests, 566 SFLE Python tests on 3.12) | [#38138829826](https://github.com/Neuri-AI/PSX/actions/runs/38138829826) | **GREEN** |
| Chromium / Headless geometry | [#38138829818](https://github.com/Neuri-AI/PSX/actions/runs/38138829818) | **GREEN** |
| Real Qt / Tk / Kivy UI | [#38138829840](https://github.com/Neuri-AI/PSX/actions/runs/38138829840) | **GREEN** |
| Native wheel/frozen fallback on Windows, macOS Intel and ARM | [#38138829846](https://github.com/Neuri-AI/PSX/actions/runs/38138829846) | **GREEN** |
| PSX Alpha | [#38138829823](https://github.com/Neuri-AI/PSX/actions/runs/38138829823) | **GREEN** |

All five workflows completed with `conclusion=success` and identical
`head_sha=296d1a2e5228166de0aa3954da957c8488f5780c`. The subsequent documentation-only sign-off
commit requires its own same-head CI verification before final delivery.

No renderer production integration, Row/Column removal, F3 work,
point-3 tolerance change or redefinition of points 1–4 was performed.

**P5 CLOSED. F2 normative final exit still OPEN.**
