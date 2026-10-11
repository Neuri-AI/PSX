# SFLE F2 / Point 4 — final single-authority and Scroll boundary certification

**Decision:** CLOSED on 2026-10-11 for the user-approved **F2 point-4 gate**. **F2 itself remains OPEN:** point 5 and the final seven normative exit checks still require their own disposition.

**Certified immutable code SHA:** [`33261d50e6585a3c21c91e32664a90705e77b938`](https://github.com/Neuri-AI/PSX/commit/33261d50e6585a3c21c91e32664a90705e77b938), branch `fix/sfle-f2-b53b3aa`.

## RED-first evidence (no contract edits beforehand)

- [RED-only test commit `73c0b6e`](https://github.com/Neuri-AI/PSX/commit/73c0b6e994b44721f38c39b5c870429de6c2fdf4) added `tests/sfle/test_f2_point4_authority_red.py` **before** modifying the contract.
- [SFLE Core RED #38136156613](https://github.com/Neuri-AI/PSX/actions/runs/38136156613): **536 passed / 10 failed** in Python 3.12. Failures reproduced missing independent host/content binding, nested Scroll scoping, reversible transforms and worker ownership port. Some tests failed on one missing interface; they are not counted as ten distinct implementation defects.
- Only after observing RED, [contract fix `321dd28`](https://github.com/Neuri-AI/PSX/commit/321dd28422634c9a178e8fcfd42096d302f1a57b) added the missing invariants. Subsequent changes connected the worker's port and preserved the existing precise non-Flex diagnostic. No renderers or layout engines were changed.

## Coverage by required finding

| Finding | Positive executable evidence | Adversarial executable evidence | Contract enforced |
| --- | --- | --- | --- |
| **A: trusted Scroll host/content identity** | Two nested native host IDs resolve to their correct `Flex` content root IDs and pass `validate_adapter_commit`. | Crossed/swapped roots, duplicate root claims and host mismatch fail before mutation with `SFLE_INVALID_SNAPSHOT`; non-Flex content retains `SFLE_UNSUPPORTED_FEATURE`. | `SFLEAdapterPorts.scroll_content_root` independently resolves host→root from reconciler-owned data. Absence of the resolver is a fail-closed Scroll transaction. |
| **B: viewport/offset separation** | Read-only projections clamp horizontal/vertical offsets for three viewport sizes while keeping all source `LayoutResult.boxes` unchanged. | Oversized nested Scroll descendants cannot increase the outer native host's scroll extent; inner overflow belongs to the inner host. | `derive_scroll_content_metrics(..., scroll_viewports=...)` scopes nested content to its native viewport footprint; no new Flex sizing occurs. |
| **C: coordinate-frame reversibility** | Nested top-left SFLE→viewport→SFLE point transforms round-trip to within **0.01 logical CSS px**, with no rectangle mutation. | Using another Scroll host's origin/offset is demonstrably not an equivalent coordinate frame (>1px mismatch in the fixture). | `scroll_to_viewport_point` and `scroll_to_sfle_point` are exact inverse frame conversions; native 1px application tolerance is unchanged. |
| **D: instrumented native ports and nested hosts** | A genuine Python engine result is passed unchanged to the native worker transaction with two Scroll host bindings and verified readback ≤1px. | Simulated second-source native layout changes the inner Flex width by 5px; readback rejects the transaction and restores original geometry. | `start_native_worker_layout` routes the independent binding through `validate_adapter_commit` and retains current-generation validation, exact SFLE result forwarding and rollback. |

**New mandatory coverage:** `tests/sfle/test_f2_point4_authority_red.py` contributes **10 parametrized pytest cases** (A: 4; B: 2; C: 2; D: 2). The existing `tests/sfle/test_f2_adapter_authority_certification.py` fixture now supplies the independent ownership port. The suite executes as part of mandatory `tests/sfle` with no skip policy.

## Five mandatory workflows — single certified source commit

| Workflow | CI run | Result |
| --- | --- | --- |
| SFLE Core — Python 3.10–3.13, Rust, Rust/Python differential and F2.4 inventory | [#38136448907](https://github.com/Neuri-AI/PSX/actions/runs/38136448907) | **GREEN**; 546 Python SFLE tests passed on 3.12, zero failures |
| Chromium / Headless comparison | [#38136448876](https://github.com/Neuri-AI/PSX/actions/runs/38136448876) | **GREEN** |
| Real Qt / Kivy / Tkinter UI certification (Linux/Xvfb) | [#38136448931](https://github.com/Neuri-AI/PSX/actions/runs/38136448931) | **GREEN** |
| Windows / macOS ARM64 / macOS Intel wheels, frozen runtime and fallback | [#38136448938](https://github.com/Neuri-AI/PSX/actions/runs/38136448938) | **GREEN**; all three OS jobs succeeded |
| PSX Alpha validation | [#38136448955](https://github.com/Neuri-AI/PSX/actions/runs/38136448955) | **GREEN** |

All five workflow run records have **the identical `head_sha = 33261d50e6585a3c21c91e32664a90705e77b938`**. The documentary sign-off follows that established evidence. No tolerance increase, skipped test, unsupported CSS acceptance or silent fallback was used.

## P4.6 — Four-backend contract certification (supplement, 2026-10-11)

The original point-4 certificate above proved renderer-neutral authority, but not a *single explicit four-backend parametrized matrix*. This supplement closes that precise coverage gap **without any F3 integration**.

**Test-only code commit:** [`390de326082d71731abb71e2fdf9a4b217136c9d`](https://github.com/Neuri-AI/PSX/commit/390de326082d71731abb71e2fdf9a4b217136c9d).

**New file:** `tests/sfle/test_f2_point4_cross_backend_contract.py`: **20 parametrized tests** across `qt`, `kivy`, `tkinter` and `headless`. They cover:

1. **4 positive backend projections:** a single immutable Python SFLE result is validated using `SFLEAdapterPorts` and both nested `ScrollViewport` bindings, projected by the existing `NativeGeometryCommitter` for Qt/Tk/Kivy widget doubles and by direct immutable logical output for Headless. Backend coordinates are checked against the SFLE parent-relative origin (with Kivy's bottom-left Y conversion) under the unchanged **≤1.0px native tolerance**; reversible Scroll transforms are checked under **≤0.01px logical tolerance**.
2. **4 adversarial crossed-root rejects:** each backend must fail closed before any native application when two Scroll hosts claim each other's content roots.
3. **4 offset/resize invariance cases:** viewport sizes, clamped offsets and nested overflow scope may change while the original `LayoutResult.boxes` remains bit-identical.
4. **8 worker transactions:** each backend's instrumented port is tested with a correct SFLE result **and** a simulated second-source native width override (+5px). The correct transaction commits with ≤1px readback deviation; the override rejects and rolls back. This exercises the actual `start_native_worker_layout` generation/authority/readback boundary.

The four-backend matrix uses **real F2 contracts with intentionally instrumented widget doubles**, **not** real toolkit `Scroll` widgets or migrated product renderers. The existing live-toolkit CI independently verifies native widget projection/measurement; combining them into a production `Scroll` integration is **F3**, not this acceptance gate.

**Mandatory CI on one immutable code SHA `390de326082d71731abb71e2fdf9a4b217136c9d`:**

| Mandatory workflow | Actual GitHub Actions run | Conclusion |
| --- | --- | --- |
| SFLE Core (Python 3.10–3.13, Rust and differential) | [#38137436410](https://github.com/Neuri-AI/PSX/actions/runs/38137436410) | **GREEN**, **566 passed** on Python 3.12, no test failures |
| SFLE Chromium / Headless | [#38137436332](https://github.com/Neuri-AI/PSX/actions/runs/38137436332) | **GREEN** |
| SFLE real Qt / Tk / Kivy UI | [#38137436417](https://github.com/Neuri-AI/PSX/actions/runs/38137436417) | **GREEN** |
| SFLE native wheels/frozen fallback (Windows, macOS Intel/ARM) | [#38137436303](https://github.com/Neuri-AI/PSX/actions/runs/38137436303) | **GREEN** |
| PSX Alpha | [#38137436381](https://github.com/Neuri-AI/PSX/actions/runs/38137436381) | **GREEN** |

All five workflows reported **completed/success** with the *same head SHA*, above. There is no change in CSS conformance, Rust/Python computation, point-3 precision or any production renderer. The final documentary commit is separately rechecked in mandatory CI before user handoff.

**P4.5 remains CLOSED. P4.6 is now CLOSED. Overall F2 point 4 remains CLOSED.**

## Scope boundary: not an F3 migration claim

The F2 contract demonstrates that SFLE alone is authoritative **when the typed port is used**, including a native Scroll viewport boundary and nested hosts. The trusted host→content resolver must come from the actual reconciler when F3 wires production renderers; a caller cannot claim Scroll authority merely by supplying an unverified root ID. These tests do **not** assert that current production Qt/Kivy/Tkinter/Headless adapters already use this new contract, nor do they remove native QBoxLayout/BoxLayout/pack code, delete Row/Column, or migrate Scroll events and offset semantics. That integration remains **F3-G1–G5**.

No production renderer file, CSS capability implementation, Rust engine, Python layout algorithm or point-3 certificate was modified. The requirement to certify backend-neutral enforceable contracts is satisfied; completion of renderer migration remains explicitly out of scope.

**Final decision: F2 point 4 CLOSED; proceed to point 5.**
