# P0 Contract Review — Batch 1: Public Semantics and Compatibility

**Review date:** 2026-10-18  
**Status:** TECHNICAL REVIEW COMPLETE; OWNER DECISIONS NOT APPROVED  
**Scope:** AD-01, AD-02, AD-03, AD-04, AD-06, AD-08, and their corresponding C01/C02/C03/C05/C06 requirements.  
**Branch:** `Neuri-AI/PSX:develop`.  
**Basis:** Direct source-file reads and current architecture contract reads; source SHAs recorded below. No native application/test execution in this review.

**Must read:** [Contract index](CONTRACTS_INDEX.md) → [Proposed deltas](P0_CONTRACT_DELTAS.md) → [Owner decision package](P0_OWNER_DECISION_PACKAGE.md) → [Verification](P0_VERIFICATION_REPORT.md) → [Approval gate](ARCHITECTURE_APPROVAL.md).

## 1. Source evidence and immutable file anchors

The following **blob SHAs** correspond to files fetched from `develop` during this review. These are file-level anchors, **not proof of a single newly pinned repository HEAD or passing CI**.

| Source | Blob SHA | Review use |
| --- | --- | --- |
| [`psx/core/registry.py`](../../psx/core/registry.py) | `900a9d477a7b01fdd9cc2ef6126c10d76efcd4ba` | Existing component registry and built-in names |
| [`psx/markup/compile.py`](../../psx/markup/compile.py) | `50785bbe29ebcaef5bd1f390cbe253fb55d75297` | Markup tag resolution, registry-scoped template cache |
| [`psx/core/vnode.py`](../../psx/core/vnode.py) | `d016645f1818552e21112d81e13e5f61a3d9f445` | Immutable VNodes, constructors, internal Box and Grid child policies |
| [`psx/sfle/lengths.py`](../../psx/sfle/lengths.py) | `c382cdc9c3451ed4c57ecaaef670e24c5dffb752` | Typed `Length`, `px` and percent parsing limits |
| [`psx/core/contracts.py`](../../psx/core/contracts.py) | `cbfe46523f1390fffefc3acf14f4402a551d06ac` | Closed portable-property contracts and flex-item partition |
| [`sfle-f1-box-model.md`](sfle-f1-box-model.md) | `82ae43542b2467031e87e979bf83363d5d3e80c5` | Approved box model, length and percentage rules |
| [`responsive-grid-contract.md`](responsive-grid-contract.md) | `2a75a71abb19d368986473a7a6dac47422139392` | Twelve-column Flexbox-style Grid contract |

Frozen decisions prevail over review suggestions. Mark all new behavior **PROPOSED** until the owner chooses a documented alternative.

## 2. AD-01 — Overflow and scroll semantics

**Verdict: READY FOR OWNER CHOICE, not technically closed.**

**Evidence:** F1 box model explicitly separates CSS scrollable-overflow intrinsic minimum from the native PSX `Scroll` viewport and requires a real renderer capability classification. Current `Scroll` is a public component; no generic `overflow: auto` parity has been certified in the reviewed inputs.

**Recommended decision:** retain current Scroll semantics; initially support only explicitly certified overflow/clipping subsets. Adding a new CSS overflow property MUST NOT silently change `Scroll` dimensions or input/focus mechanics. Unsupported combinations fail with a deterministic capability error.

**Required decision detail:** enumerate accepted values (potentially `visible` and `hidden` first) and supported backends; distinguish clipping-only from scroll-container semantics. Approving the *direction* without a finite allowed-value matrix is insufficient.

**Tests after approval:** overflow viewport with content larger than window; scroll offset and wheel handling; nested Scroll; clipping with border radius; tear-down and focus restoration. No implementation claims.

## 3. AD-02 — Box sizing defaults and compatibility

**Verdict: READY FOR OWNER CHOICE.**

**Evidence:** F1 distinguishes `layout_width`/`layout_height` from existing component-owned size props and accepts both content-box and border-box. The length parser does not implement arbitrary viewport units or `calc()`. Existing builder and registry contracts already prescribe defaults.

**Recommended decision:** preserve all PascalCase builder and markup defaults. New lowercase tags obtain **per-tag explicit defaults**, not a global default flip; only a separately approved migration permits changing currently supported values.

**Tests after approval:** one legacy Button/Image/Scroll, explicit `layout_box_sizing`, padding/border constraints, percent references; same logical output before and after alias addition for identical old inputs.

**Open review point:** the owner must choose the default for *each new box-like tag*; this review does not invent one.

## 4. AD-03 — Styling precedence, inheritance and cascade

**Verdict: READY FOR OWNER CHOICE WITH FEATURE-SCOPE CAVEAT.**

**Evidence:** `ComponentContract._validate` handles existing Flex item metadata and native-component props separately; CSS-style parsing is intentionally limited in `psx/sfle/lengths.py` to tagged lengths. `psx/markup/compile.py` builds VNodes through a component registry without a browser CSS engine.

**Recommended decision:** version 1 is an explicitly scoped, deterministic style/property normalization layer and individual props; no selector specificity, global stylesheet engine, arbitrary CSS functions, or CSS custom properties until separate decisions. Keep style source/priority explicit and fail on unsupported values.

**Tests after approval:** normalized builder vs markup output, property collision handling, source priority, invalid CSS tokens, update vs remount parity, cache invalidation and retained-object bounds.

**Open review point:** define whether a public `style` mapping is supported now or staged; specifying only `no cascade` is not enough to implement normalization.

## 5. AD-04 — Block/inline semantics and internal Box collision

**Verdict: READY FOR OWNER CHOICE; IMPLEMENTATION MUST WAIT.**

**Evidence:** `psx/core/vnode.py` defines `Box` as an *internal passthrough container* for Qyro integration without portable props/guarantees. `builtin_component_registry()` registers `Box`, but this does not make it a CSS block container. The F4 Grid contract defines twelve-column Flexbox Grid and **not** full CSS Grid.

**Recommended decision:** explicitly decline HTML-compatible `div`/`span`/block semantics in the initial release, unless a standalone block/inline formatting contract is approved and tested. Never repurpose the internal `Box` implementation by a case-insensitive alias.

**Tests after approval:** `Box` internal behavior remains stable, `<box>` (if proposed) is not accidentally mapped to `Box`, `<div>` fails predictably if not in certified vocabulary; nested GridItem only accepts one component root.

## 6. AD-06 — Lowercase PSX Markup registry

**Verdict: READY FOR OWNER CHOICE, not final alias table.**

**Evidence:** `builtin_component_registry()` explicitly registers PascalCase builtins. `psx/markup/compile.py` uses resolver lookup; unknown tags raise a syntax error unless they match an explicit component in scope. The compiler's cache limit is 128 and registry cache identity includes the version.

**Recommended decision:** define a closed **explicit alias mapping** to existing portable constructors, with case-sensitive names and rejection of ambiguous custom-registry collisions. Preserve existing PascalCase and builder APIs and current error behavior. Use the existing resolver, do **not** implement a second parser.

**Candidate aliases for design review ONLY:** `text → Text`, `button → Button`, `flex → Flex`, `grid → Grid`, `grid-item → GridItem`, `input → Input`, `scroll → Scroll`. No candidate is certified; spelling (notably kebab-case vs parser grammar) and VNode equivalence must be verified before inclusion. `box → Box` is explicitly excluded due to internal-Box semantics. No blanket HTML tag mapping.

**Tests after approval:** parse grammar for every candidate spelling; alias collision in custom registry; same VNode type/key/child policy; cache version isolation; no invented attributes; unknown tag diagnostics; prop casing consistency.

## 7. AD-08 — Single-root semantics and mixed keyed children

**Verdict: READY FOR OWNER CHOICE.**

**Evidence:** `MountedInstance.native_handle()` currently enforces exactly one effective native root for a component. `Reconciler._reconcile_children()` matches keyed siblings by key, unkeyed by index and unmounts unmatched previous nodes.

**Recommended decision:** preserve the single-root native contract in P1; document how mixed keyed/unkeyed siblings behave and test state identity before altering it. Treat multi-root native component placement as an explicit future contract, not an incidental side effect of HTML-like tags.

**Tests after approval:** mixed keyed/unkeyed insertions/removals, duplicate-key errors, keyed reorder with local state, component root replacement, renderer native move/remove paths, fragment path diagnostics.

## 8. Batch 1 reviewer decision matrix

| ID | Contract(s) | Technical review | Owner approval | Code change authorized |
| --- | --- | --- | --- | --- |
| AD-01 | C01 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |
| AD-02 | C01/C05 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |
| AD-03 | C02 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |
| AD-04 | C03/C05 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |
| AD-06 | C05 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |
| AD-08 | C06 | REVIEWED / RECOMMENDATION RECORDED | PENDING | NO |

**Progress metric:** 6/12 owner decision items have completed an additional **static technical review** in this batch; **0/12 are approved**. This is *not* a claim that 6/12 normative contracts are closed, nor that 50% of implementation is complete.

## 9. Review blockers and next batch

**Batch 2 (AD-05/AD-07/AD-09):** exception-safe teardown, distribution-version alignment and renderer measurement/invalidation optional capability port. Source mapping is possible now, but owner sign-off should be paired with reproducible execution of H-PKG-01/H-MEM-01 and native adapter tests.

**Batch 3 (AD-10/AD-11/AD-12):** F6 classifier, native/platform certification policy, and F5.5 G6 status. No release claims without exact-SHA CI evidence.

**Architecture Gate: BLOCKED.** This document records review work and options, not owner consent. Implementing agents MUST continue only evidence collection and tests until the applicable decisions are signed in [the approval record](ARCHITECTURE_APPROVAL.md).
