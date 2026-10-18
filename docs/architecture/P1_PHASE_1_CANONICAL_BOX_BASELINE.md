# P1 / IM-01 — Canonical item box style: first isolated slice

**Date:** 2026-10-18  
**Branch:** `Neuri-AI/PSX:develop`  
**State:** **IMPLEMENTED AS A NON-INTEGRATED PURE MODULE; CI PENDING**  
**Authority:** Ratified [F1.6/F1.7 box model](sfle-f1-box-model.md), [master P1 sequence](velto-master-execution-plan.md); pending [P0 owner decisions](P0_OWNER_DECISION_PACKAGE.md).

## Why start here

The owner asked to defer the still-observed excess **Kivy + PSX/Cinnamon memory growth** and begin the first remaining implementation phase. The deferred risk is recorded as **P2-MEM-KIVY-SFLE-01 (OPEN)** in [P0.9 closure candidate](P0_9_CLOSURE_CANDIDATE.md). This does not establish that C07 passed or imply formal P0 architecture sign-off.

P1's first scheduled work item, **IM-01**, is a single normalized, renderer-neutral style/box representation. The current runtime already has ratified `Length`, `BoxEdges`, `BoxRect`, `LayoutNode`, native item metadata and layout snapshot adapters. Creating another solver or public API without inventorying these structures would duplicate them.

## Implementation in this slice

- [`psx/sfle/canonical_box_style.py`](../../psx/sfle/canonical_box_style.py) provides `CanonicalItemBoxStyle`, `normalize_item_box_style`, and `partition_item_box_style`, a **frozen, slotted snapshot** of existing `layout_width/height/min/max` and explicit `layout_margin_*`, `layout_padding_*`, `layout_border_*` F1 item metadata.
- The representation **reuses** existing typed `Length` and `BoxEdges`, delegates validation to the current `validate_flex_item_props` contract, keeps percentages unresolved, prohibits unsupported expressions through the existing length grammar and does not modify the input mapping.
- Native/component-owned fields such as `Image.width` and `Scroll.width` survive untouched in a separate component-props mapping; no case-folding, lower-case aliases, CSS cascade, automatic `div`, box model defaults or rendering behavior is introduced.
- [`tests/test_p1_canonical_box_style.py`](../../tests/test_p1_canonical_box_style.py) characterizes defaults, percent preservation, negative margins vs padding errors, unknown units, isolation of native fields and lack of shared mutable defaults.
- [P1 characterization CI](../../.github/workflows/p1-canonical-box-style.yml) is configured to test this small pure contract under Python 3.10 and 3.13. Its results must be checked separately. **No run receipt is asserted here.**

## Not yet integrated

The new module is deliberately **not wired into** `VNode`, PSX Markup, the `native_layout_snapshot` translator, Cinnamon geometry engine, or Qt/Tk/Kivy. The next development step is differential characterization of the existing snapshot translator and choosing the P0-approved representation/precedence policy. Backward compatibility remains the dominant acceptance criterion.

## Still requiring explicit owner decisions

The owner has approved **deferring the Kivy/Cinnamon memory investigation**, *not* all twelve technical choices in the P0 owner decision register. These unresolved choices must be settled before changing public style semantics or cross-backend geometry:

- AD-01/02/03/04: overflow, lowercase sizing default, styling precedence and block scope.
- AD-06/08: finite lowercase tag aliases and identity/root boundaries.
- AD-09: capability ports for native geometry.
- AD-07: package release scheme (separate C05 resolver CI still needs to pass).
- Remaining AD-05/10/11/12 safety, F6 and final certification policies.

**Scope boundary:** pure internal scaffolding and tests are permissible now; do not label the overall P0→P1 architecture gate APPROVED or advertise P1 as live in public documentation.

## Follow-up increment: typed styles travel with prepared snapshots

**Scope:** the native snapshot adapter now supplies a `box_styles` tuple on
`PreparedNativeLayoutSnapshot`. Each entry pairs the exact stable node ID with
a validated, immutable `CanonicalItemBoxStyle`. This includes nested
participating hosts and retains source percentages unresolved. The former
`PreparedF3Snapshot` name remains an internal compatibility alias.

**Preserved invariant:** `LayoutInput` nodes and their specified style values
remain unchanged; neither Python nor Rust geometry calculation is modified by
this increment. Existing widget-native width/height remain in the originating
VNode. Invalid recognized box metadata is rejected while preparing the snapshot
rather than being forwarded to an engine.

**Tests added:** snapshot identity/order, typed percent/margin/padding/border,
builder/markup consistency, malformed metadata rejection. Shared adapter changes
route to core and all native consumers through the impact selector.

**Verification:** committed code has not been executed in CI or a local PSX
checkout in this session. Treat all test outcomes as **pending**, not passing.
This is an internal snapshot boundary, not public style API coverage; public
behavior census is N/A for this slice.

**Next:** run the tests and inspect differential Rust/Python geometry on the
same exact commit before changing actual layout consumption. No CSS parser,
cascade, lowercase tags, default box sizing, or renderer modifications here.

## Next step

1. Validate pure IM-01 CI on the committed code.
2. Compare existing snapshot translation vs canonical item metadata for tested Flex/Image/Scroll controls without changing its output.
3. Ask the owner to ratify bounded public semantics before implementing lowercase markup tags, cascade or container defaults.
4. Integrate via feature-tested adapters and cross-backend geometry fixtures, preserving PascalCase components.
