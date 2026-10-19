# Canonical box geometry — scoped implementation evidence

> Status: **SCOPED IMPLEMENTATION COMPLETE; global architecture/release certification NOT CLAIMED**
> Evidence baseline: commit `0023a8cbd8d915cec7ff5674d1fdc84ff97415b3` (2026-10-19).
> Branch: `feature/universal-box-model-and-styling`, draft PR #48.
> This records implementation evidence for canonical box geometry, not an independent architecture or release approval.

## Closed scope: representation, normalization and basic geometric consumption

- `psx/sfle/canonical_box_style.py`: typed immutable canonical item representation and `layout_*` normalization.
- `psx/sfle/native_layout_snapshot.py`: explicit `canonical_snapshot()` conversion without rewriting VNode props.
- `tests/test_p1_canonical_box_style.py`: immutability, namespace/legacy width partition, validation, identity.
- `tests/test_native_layout_snapshot.py` and `tests/test_headless_native_layout.py`: native layout snapshot consumption and representative geometry.
- CI receipts for the exact baseline SHA: **8/8 success**, including `Canonical box geometry certification`, `Flex layout contract certification`, `Grid integral certification` and `Native layout selective validation`.

## Deliberately NOT certified by the P1.1 closure

The canonical geometry integration contract contains **broader end-to-end acceptance criteria**, which cannot be inferred from 8 passing workflows alone. These remain open and must not be described as passed:

- Exhaustive same-SHA Rust/Python differential geometry vectors and diagnostics.
- Complete Qt/Tkinter/Kivy native readback and unsupported-combination matrix.
- Full indefinite-percentage, height-for-width, commit-failure and lifecycle stress evidence.
- Incremental subtree computation and its selective invalidation: **P1.2**.
- Global `ARCHITECTURE_APPROVAL.md` gate and public CSS/tag defaults: still separately pending.
- Final per-backend conformance and release matrix: **P1.7/P4**.

## Handoff

The canonical representation's intentionally narrow goal—*canonical representation and representative mounted consumption*—may be tracked as **implemented with passing scoped CI**. Do not relabel that as full geometric, cross-backend, Rust/Python or release certification. Subsequent layout work may proceed on independent internal code only where the global gate permits; any unresolved approval-dependent behavior stays blocked.

The next technical increment is a **real partial Flex solver**, with unchanged output versus full compute, safe fallback for unresolved constraints/measurement, explicit cache ownership, cross-backend and Rust/Python verification.
