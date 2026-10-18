# P0 Architecture — Owner Decision Package

**Date:** 2026-10-18 · **Revision:** 0.1 · **Status:** REVIEW REQUIRED — NO APPROVAL IMPLIED  
**Canonical branch:** `Neuri-AI/PSX:develop`  
**Target audience:** project owner, architecture reviewer, implementation agents.

**Read first:** [Contract index](CONTRACTS_INDEX.md), [C01–C12 proposals](P0_CONTRACT_DELTAS.md), [Verification evidence](P0_VERIFICATION_REPORT.md), [Approval gate](ARCHITECTURE_APPROVAL.md).

This document turns the twelve unanswered architecture decision IDs into **explicit, bounded choices**. Recommendations are draft technical proposals, **not owner decisions**. If a choice conflicts with an already-ratified more-specific F1–F5 decision, the ratified decision wins until the owner explicitly supersedes it.

## Snapshot — implementation readiness

- **Allowed now:** evidence gathering, API mapping, isolated reproductions, source-backed design discussion, and writing tests/fixtures in a nonproduction worktree.
- **Not allowed yet:** modifying public API semantics, introducing CSS cascade, removing existing components, widening supported OS/backend claims, or shipping P1 geometry changes.
- **Hard blockers:** H-PKG-01 package graph, H-MEM-01 exception-path teardown characterization, current executable native/CI coverage, approval of decision set.

## The decisions

### AD-01 — Overflow and scrolling scope (C01)
**Facts:** [ratified box-model contract](sfle-f1-box-model.md#4-css-box-model--committed-semantics) explicitly distinguishes scrollable overflow semantics from PSX `Scroll` adapter behavior. Native scroll ownership is backend specific.

- **Option A (recommended for initial P1):** Preserve `Scroll` as the existing viewport primitive. Add box overflow vocabulary *only* for modes whose geometry, clipping, events and backend support can be tested. Reject unsupported values.
- **Option B:** Implement all CSS `overflow` values before P1.
- **Decision tests:** content size beyond viewport; clipping vs scrolling; nested Scroll; pointer/keyboard focus; native owned/borrowed cleanup; errors for unsupported mode.
- **Risk:** mixing declarative overflow with native scroll without defined ownership creates feedback loops.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-02 — New lowercase element box-sizing (C01/C05)
**Facts:** F1 uses `layout_box_sizing` and namespaced dimensions for compatibility; existing component props may already own `width` and `height` with different meanings.

- **A (recommended):** Introduce no global semantic default change. Declare explicit per-tag default and conversion rule; existing PascalCase components retain identical behavior.
- **B:** Globally switch to border-box and migrate all existing components.
- **Tests:** `layout_width` and component `width` coexist; min/max; padding/border sum; old example snapshots remain unchanged.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-03 — Styling, cascade and precedence (C02)
**Facts:** [ComponentContract](../../psx/core/contracts.py) applies a closed prop partition; [Length.parse](../../psx/sfle/lengths.py) supports `px`, `%`, keyword lengths, but not `calc()`, viewport units or CSS arbitrary expression syntax. No full browser cascade has been certified.

- **A (recommended):** Start with scoped style declarations/props and deterministic precedence, no general selector cascade. Establish a future extension point, but reject unknown styles.
- **B:** Implement selector specificity, inheritance, pseudo-states and browser CSS parsing in P1.
- **Tests:** normalization parity for builder/markup; unknown properties; precedence; style mutation; no eval.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-04 — Block formatting context and HTML-like elements (C03/C05)
**Facts:** Current registered portable layout is Flex plus twelve-column responsive Grid; [Grid contract](responsive-grid-contract.md) expressly rules out bidimensional CSS Grid. [Builtin registry](../../psx/core/registry.py) already registers an **internal** `Box`, and [Box source](../../psx/core/vnode.py) says it is an internal Qyro passthrough without public props or portability guarantees.

- **A (recommended):** Lowercase `flex`, `grid` and selected portable control tags can be mapped only with explicitly documented semantics. Defer `div`, `span`, `block` until a block/inline layout contract exists.
- **B:** Promise HTML-like block/inline layout immediately.
- **Critical collision:** Existing `Box` must not be repurposed into a public CSS box merely by adding lowercase `box`. The registry already exposes `Box` as a private host type.
- **Tests:** registry collision, unsupported tag diagnostic, preservation of `Box` internal behavior, single-root and GridItem child policy.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-05 — Cleanup failure propagation (C04/C06/C07)
**Facts:** [`Reconciler._unmount`](../../psx/core/reconcile.py) runs sequential unsubscribe → hooks → children → native destroy with no apparent global finally; a user cleanup that raises may interrupt later steps. This is *source-confirmed risk*, not an executed leak.

- **A (recommended):** Every independent safe disposer is attempted exactly once, failures recorded and reported after cleanup, preserving defined exception precedence; fatal toolkit corruption may have separate handling.
- **B:** Fail-fast at first exception.
- **Tests:** one hook throws, one event unbind throws, child destroy throws, other children still receive disposal, no double destroy; Qt event-loop drain.
- **Proposal:** A. **Owner choice: PENDING.** No implementation without fault injection.

### AD-06 — Lowercase markup namespace (C05)
**Facts:** [`builtin_component_registry()`](../../psx/core/registry.py) registers PascalCase names; [PSX compiler](../../psx/markup/compile.py) resolves tags through a registry and raises for unknown tags. Current compiled-template cache is bounded to 128 entries and cache keys include registry identity/version.

- **A (recommended):** Publish a finite lowercase alias table for verified components. Use the **same existing constructors** with explicit mapping and no automatic case folding. Add aliases in a versioned registry; preserve custom component name collision checks.
- **B:** Generic transformation of any lowercase HTML tag to a matching PascalCase name.
- **Tests:** stable default registry/cache key, explicit unknown tag failure, custom registry override, same VNode output/keys/props, no alias change to existing public constructor.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-07 — Canonical package/version graph (C05/C11/C12)
**Facts:** Observed source manifests presently differ in distribution name/version compatibility; [H-PKG-01](P0_VERIFICATION_REPORT.md#2-h-pkg-01--dependency-resolver-compatibility) documents it, and an **executed local PEP 440 specifier comparison** found three tested source-version/range pairs incompatible (this is *not* a successful pip resolver run).

- **A (recommended):** Pick an explicit canonical distribution namespace and coordinated versions across PSX/Velto/Pydux/Qyro. Verify wheel METADATA, fresh local wheelhouse install, public index resolution and smoke test. Maintain legacy imports via reexports rather than package forks.
- **B:** Leave independently versioned packages and rely on manual developer installation until a future release.
- **Tests:** clean `pip install` with intended extras on Python 3.10–3.13, import API, native mount and framework availability diagnostics.
- **Proposal:** A. **Owner choice: PENDING** on exact names/versions; do not guess release tags.

### AD-08 — Multi-root and mixed-key identity (C06)
**Facts:** [`MountedInstance.native_handle()`](../../psx/core/instance.py) raises unless a component has one effective child; [`Reconciler._reconcile_children()`](../../psx/core/reconcile.py) treats keyed and unkeyed children separately.

- **A (recommended):** Preserve single-root mounted native semantics in P1. Make mixed keyed/unkeyed reuse deterministically testable; defer multi-root native placement until an explicit anonymous-box/fragment proposal.
- **B:** Introduce full multiple-root native placement and state identity in P1.
- **Tests:** reorders, removal, mixed insertion and old-key retention, fragment diagnostics, no state migration across identity.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-09 — Measurement/invalidation adapter boundary (C04/C08/C09)
**Facts:** [Base Renderer protocol](../../psx/renderers/protocol.py) does not require `measure`, `commit_layout` or `invalidate_layout`; actual Qt/Tk/Kivy renderers implement layout commit/invalidation. [F1 final](sfle-f1-final-architecture.md) requires UI-thread intrinsic measurement and 1/64px pure geometry.

- **A (recommended):** Introduce an optional, typed capability port for measurement/commit/invalidation with a feature flag and explicit errors. Keep existing protocol working during migration.
- **B:** Add compulsory methods to `Renderer` in one breaking change.
- **Tests:** standard builtin renderer, existing third-party adapter mock, pre-mount custom widget hint `(-1,-1)`, intentional `(0,0)`, theme/DPI and resize coalescing.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-10 — Hot reload classification (C10)
**Facts:** [M8 document](../m8-hot-reloading.md) describes limited dev-only module refresh plus restart, with remaining F6 work postponed and Qyro dependency.

- **A (recommended):** Compatible component edit → fast refresh; changed hook structure/local incompatibility → remount only when cleanup is certified; bootstrap/native/third-party change → process restart.
- **B:** Attempt best-effort reload for all Python imports and native extensions.
- **Tests:** 100 edits watcher count stable; hook mismatch; versioned JSON snapshot; syntax error recovery; production/frozen disabled.
- **Proposal:** A. **Owner choice: PENDING.** Implementation remains after ownership hardening.

### AD-11 — Backend/soak certification (C11/C12)
**Facts:** Pure layout F1 tolerances, historical F2/F3/F4 CI and actual renderer-specific behavior are not interchangeable.

- **A (recommended):** Use explicit supported/not-tested/unsupported cells, existing logical/native tolerances, and measured memory/time baselines on matched environments. Native tests required for native claims.
- **B:** Declare parity from headless tests alone.
- **Tests:** Qt families and PySide2 markers, Tk, Kivy; reflow on resize/theme/font, cleanup, images, installation; full unsupported-cell diagnostics.
- **Proposal:** A. **Owner choice: PENDING.**

### AD-12 — F5.5 G6 closure and documentation truth (C12)
**Facts:** [F5.5 progress ledger](f5-5-public-documentation-progress.md) shows G6 in progress; earlier owner discussions describe F5.5 as closed.

- **A (recommended):** Track **historical closure claim** separately from **current release/doc readiness**. Do not overwrite ledger status without immutable CI artifact and explicit owner approval.
- **B:** Update all docs to CLOSED based solely on the historical conversation.
- **Tests:** owner sign-off citation, same-SHA CI receipt, examples reproducibility and independent page review.
- **Proposal:** A. **Owner choice: PENDING.**

## Source-backed additional findings for implementers

1. **Private `Box` is a name collision**, not a ready-made public universal box; see [`vnode.py`](../../psx/core/vnode.py) and [builtin registry](../../psx/core/registry.py).
2. **Lowercase aliases can use existing registry machinery** rather than inventing a second parser or VDOM. The compiler's resolution step and versioned cache exist; semantic compatibility and security still require tests.
3. **Current `Length` representation is immutable and typed**, supporting px/percentage and some keywords, not viewport units/calc. New CSS syntax must go through explicit capability gates.
4. **Current `VNode` immutable description and `MountedInstance` mutable lifetime are separate**; preserve this boundary in the new box system.
5. **A real Python PEP 440 comparison was run**, but clean installations/CI still need execution; don't label the packaging conflict fully reproduced.

## Suggested approval order

| Owner review batch | Decisions | Why |
| --- | --- | --- |
| Batch 1 — P1 public semantics | AD-01, AD-02, AD-03, AD-04, AD-06, AD-08 | Unblocks the bounded design language without breaking existing components |
| Batch 2 — P1 safety and integration | AD-05, AD-07, AD-09 | Unblocks lifecycle protocol and clean packaging once executable evidence exists |
| Batch 3 — follow-on phases | AD-10, AD-11, AD-12 | F6 and release certification require stable P1/P2 baseline |

**No agent can infer approval by following the recommended column.** Record actual owner selections and immutable source/test evidence in [`ARCHITECTURE_APPROVAL.md`](ARCHITECTURE_APPROVAL.md) before permitting changes.

## Task acceptance packet

For each decision, attach a small ADR at the point of approval containing: owner, date, selected option, rejected alternative, applicable component/backend, source SHA, old API behavior, new API behavior, negative cases, migration, test vector IDs, CI routing and unresolved limitations. If an ADR supersedes an earlier F1–F4 decision, cite the exact clause being amended.

**Current outcome:** twelve decision proposals are review-ready; **none are approved here**. P1 implementation remains blocked.
