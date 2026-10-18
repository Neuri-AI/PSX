# Universal Box Model and CSS Core — Architectural Contract Proposal

> **Status:** DRAFT — OWNER REVIEW REQUIRED; NOT APPROVED
> **Scope:** The single phase branch `feature/universal-box-model-and-styling`.
> **Decision authority:** Project owner. This document records proposals, not inferred approvals.
> **Implementation status:** No runtime implementation is authorized by the existence of this proposal.

## 1. Objective and boundaries

Velto must provide a consistent, web-familiar box model and an extensible CSS Core inside PSX, while Cinnamon remains the **sole authoritative layout engine** and Qt, Tkinter and Kivy remain **native renderers**. PSX Markup is markup; declarative use is optional. Existing PascalCase components and their documented properties remain supported.

This is **not** an HTML browser, CSSOM or promise of complete browser CSS compatibility. Existing 12-column `Grid` is **not** CSS two-dimensional Grid. The existing internal `Box` must not silently become a public HTML/CSS `div`.

### Required invariants

1. Source PSX VNodes and keyed component state retain their identity; style resolution never rewrites keys or component-owned data.
2. Native widget properties and styling/layout properties are distinct namespaces and validate before reaching adapters.
3. The same normalized style input produces equivalent Rust/Python Cinnamon geometry; only the renderer projects that geometry into native coordinates.
4. A renderer capability is either implemented and verified, explicitly not applicable, or rejected/declared unsupported. No silent successful drop.
5. Native measurement occurs on the owning UI thread; layout calculation does not invoke native APIs.
6. Existing `Text`, `Button`, `Flex`, `Grid`, input widgets and custom/Native escape hatches remain backward compatible.
7. Unresolved public decisions must not be implemented by guessing.

## 2. Verified source inventory (at proposal time)

| Area | Inspected source | Grounded current behavior |
| --- | --- | --- |
| Executive objective / delivery | `velto-master-execution-plan.md` | Web-like boxes + CSS-like styling, existing APIs retained, phased native conformance |
| Historical normative box model | `sfle-f1-box-model.md` | Distinct content/padding/border/margin boxes; namespaced item props; existing content-box default |
| Typed length grammar | `psx/sfle/lengths.py` | Immutable `Length`, px, %, supported keywords; no general `calc()` or viewport units |
| Item metadata | `psx/core/props.py` | `layout_width` and native `Image.width` are separate; `FLEX_ITEM_PROPS` is closed |
| Canonical item styles | `psx/sfle/canonical_box_style.py` | Validated immutable dimensions and four edge groups |
| Native layout bridge | `psx/sfle/native_layout_snapshot.py` | Prepared snapshots carry box styles; `canonical_snapshot()` provides explicit typed engine input, not globally enabled |
| Markup registry | `psx/core/registry.py` | Explicit PascalCase built-ins; internal `Box`; external `WebView` and `Native` |
| Pending public choices | `P0_OWNER_DECISION_PACKAGE.md` and `ARCHITECTURE_APPROVAL.md` | Overflow, sizing defaults, CSS precedence, block semantics, lowercase vocabulary and renderer ports are not formally approved |

The prior exact-SHA CI receipts certify **the existing typed snapshot increment**, not the behaviors proposed below:
- [Canonical geometry](https://github.com/Neuri-AI/PSX/actions/runs/39154194843)
- [Native layout](https://github.com/Neuri-AI/PSX/actions/runs/39154194753)
- [Grid integral](https://github.com/Neuri-AI/PSX/actions/runs/39154194774)

**Source discrepancy to resolve:** Historical `sfle-f1-box-model.md` specifies `layout_box_sizing` and certain shorthand fields that do not appear in the presently inspected `FLEX_ITEM_PROPS` and `CanonicalItemBoxStyle` implementation. Treat normative scope and available runtime as different; characterize and implement only after approval. Existing documentation that still says all snapshot CI is unverified is stale relative to the linked receipts.

## 3. Proposed CSS Core boundaries and data flow

CSS Core is an **internal PSX subsystem**, not a separate layout engine or required WebView:

```text
PSX Markup / Python component constructors
  -> VNode + widget-specific props + explicit style sources
  -> style parsing and declaration validation
  -> selector matching + cascade + scoped inheritance (where supported)
  -> immutable ComputedStyle (geometry | visual | interaction)
      -> Cinnamon (Rust primary / Python fallback): geometry
      -> Native capability adapter: painting, state, focus, semantics
  -> keyed reconciliation and native commit/readback
```

**Module responsibilities (proposed, not source paths):**

- **Tokenizer/parser:** parse an explicitly bounded CSS subset into structured declarations and rules, without Python or JS evaluation.
- **Registry:** typed property definitions: initial value, inherited flag, applicable target kinds, accepted units, normalization, dependency and invalidation type.
- **Selector matcher:** component/tag, class and ID selectors (subject to approval), with stable specificity calculation.
- **Cascade:** deterministic ordering across defaults, stylesheets, inline styles and explicit component props.
- **Resolver:** immutable specified/computed style snapshots; separate intrinsic/percentage resolution into Cinnamon's layout phase.
- **Capability partition:** geometry flows only to Cinnamon, visual/interaction props flow only to supported native adapters. Metadata and widget props remain separate.
- **Cache:** keyed by stylesheet version, component style identity, relevant ancestor dependencies and theme/state; bounded, invalidated on edits/unmount, and never retains dead component trees.

Do not claim any of these modules already exists simply because the architecture names them.

## 4. Proposed geometry and box-sizing rules

### 4.1 Box geometry

Use four nested rectangles: content, padding, border, margin. The layout engine computes the rectangles from *specified* sizes and intrinsic constraints. Margins may be negative if the property contract permits; padding and border-width cannot be negative.

- Percentages remain symbolic until a known containing-block dimension exists.
- `auto`, `min-content`, `max-content` and `none` remain typed, property-specific values; do not force unknowns to zero.
- Explicit min/max constraints must compose with intrinsic measurement according to the approved Cinnamon contract.
- Geometry uses logical pixels; physical device scaling belongs to native projection, not to repeated layout calculation.

### 4.2 Existing PascalCase components — recommended compatibility policy

Preserve existing `layout_*` item props and their current `content-box` behavior. Preserve native `Image.width`/`height`, `Scroll.width`, `Flex.width`, and similar component/container-specific meanings. Do not globally alias every `width` to `layout_width`. A native-facing `width` and a layout-facing `layout_width` may coexist.

### 4.3 New lowercase elements — owner decision needed

**Recommended:** choose an explicitly documented default per new element family, preferably **`border-box` for new generic layout containers only** if parity fixtures demonstrate this behavior. Do **not** retroactively change old PascalCase defaults. Record the conversion of CSS `width` and `height` into canonical dimensions per tag.

**Open choice:** should all new lowercase elements default to `border-box`, or should some use `content-box`? The historical owner package recommends per-tag contracts rather than a universal migration; it does not ratify a particular default.

## 5. Proposed CSS cascade and precedence contract

We previously agreed to **design an extensible CSS engine**, not merely a dictionary of inline style props. The owner package's earlier recommendation was a more limited initial subset without general selectors. The proposed resolution is:

**Complete architectural seams; staged feature support.** Define a parser, typed registry, selector engine, cascade, computed-style resolver and native capability boundary now. Implement only the subset explicitly included in each certified release.

Proposed precedence among style sources, from lower to higher priority (subject to final owner approval):

1. Built-in/tag initial style.
2. Inherited supported properties from the nearest applicable ancestor.
3. Scoped stylesheet declarations, ordered by specificity and source order.
4. Inline `style` declarations.
5. Explicit *layout* arguments supplied by existing PascalCase constructors, **only for their existing, named semantic slots**, to preserve backward compatibility; these do not automatically override unrelated native properties.

**Important:** Existing `width` native/widget props are not CSS declarations. No magic transfer of values between namespaces.

Supported declaration conflict resolution (proposed):
- Later declaration wins only within the same specificity tier and origin.
- Specificity values are compared lexicographically; selectors tie by final source order.
- `!important`, animation origin, browser UA/user origins and shadow DOM are deferred unless separately approved.
- CSS custom properties (`--token`, `var()`), pseudo-classes and complex combinators are proposed extension points; not automatically supported in the first release.
- Invalid or unknown properties produce a diagnostic rather than silently changing native behavior. An entire stylesheet need not be rejected for one malformed declaration **only if** a documented recovery policy and line/column diagnostics are accepted.

**Unresolved owner choice:** Do direct markup `style` declarations override legacy `layout_*` when both target the same geometry? Recommended answer: **no for existing PascalCase components**, with an explicit conflict diagnostic or deterministic legacy precedence, not a silent coercion. For new lowercase tags use the conventional CSS cascade. This decision affects public behavior and requires sign-off.

## 6. Proposed first CSS vocabulary and exclusions

Each published property must have a typed grammar, initial/inherited rule, target applicability and backend capability matrix; a CSS-looking name alone is not a capability claim.

| Capability | First implementation proposal | Deferred or limited |
| --- | --- | --- |
| Sizing | `width`, `height`, `min-*`, `max-*`, `box-sizing` | `calc()`, viewport-relative lengths, fractional units |
| Edges | `margin`, `padding`, border *width* | arbitrary border images; paint style/color require renderer proof |
| Flex | `display: flex`, `flex-direction`, `flex-grow`, `flex-shrink`, `flex-basis`, `gap`, supported alignment | browser-complete flexbox parity |
| Text | `color`, `font-size`, `font-weight`, `text-align` when native adapters prove them | full font shaping/typography parity |
| Paint | `background-color`, `border-color`, `border-radius` only when backend-specific paint is verified | arbitrary filters, transforms, shadows without contracts |
| Overflow | `visible`, `hidden`/clip only with verified clipping; preserve existing `Scroll` for scrolling | implicit web overflow scroll ownership |
| Grid | Preserve existing responsive twelve-column `Grid` | CSS grid tracks, areas, auto-placement |
| Position | In-flow layout only as baseline | `absolute`, `fixed`, `sticky` without separate model |

First-release selection is an **approval task**, not a shipping commitment.

## 7. Proposed HTML-like PSX Markup contract

Use a **finite, explicit, versioned alias registry**, not arbitrary HTML parsing or generic capitalization. Keep PascalCase names supported and separate user component namespace collisions.

**Low-risk initial aliases to review:** `button` -> `Button`, `input` -> `Input`, `textarea` -> `TextArea`, `img` -> `Image` after checking source/src and value/label mappings. Mapping must preserve VNode identity, keys, events and semantics; aliases are not automatically permitted until tested.

**Dedicated semantic/layout design required:** `div`, `span`, `p`, headings `h1`–`h6`, `section`, `main`, `header`, `footer`, `form`, `label`, `ul`, `li`. A tag name does not grant a browser's block/inline formatting context, form submission, accessibility tree or text-flow behavior. Define semantic fallbacks and what is genuinely native.

- `display: block` and `inline` **must not** be aliases for `Flex` without a deliberate block/inline contract.
- Do not publish lowercase `box` as an alias to the internal `Box`.
- Respect PSX Markup's existing expression/literal syntax; sample markup below is **proposed and not executable today**.

```python
# PROPOSED SYNTAX ONLY — not verified runnable public API.
return psx("""
    <div class="panel">
        <h1>Welcome</h1>
        <input value={name} on_change={set_name} />
        <button class="primary">Save</button>
    </div>
""")
```

The stylesheet attachment API (`class` vs `class_name`, scoped `css` or file import, default style origin, runtime theme updates) remains **UNDECIDED**.

## 8. Layout and renderer integration contract

- **Cinnamon:** sole authority for sibling placement, box geometry, resolved percentage dimensions and constraints. Rust and Python consume the same normalized snapshot schema.
- **Qt/Tkinter/Kivy:** provide intrinsic measurements and implement only renderer-supported visual/native interactions; commit boxes generated by Cinnamon. No toolkit manager concurrently owns those same child rectangles.
- **Native/custom widgets:** style their *container boundary* by default. Internal native widget paint styles require an explicit adapter capability, not an assumption of CSS support.
- **Measurement:** run native hints on the owning UI thread; negative size hints may be invalid; zero may be intentional. Track resource/theme/DPI revisions.
- **Invalidation:** distinguish geometry-affecting changes from paint-only changes; coalesce resize and external native updates; prevent reentrant commits and feedback loops.
- **Lifecycle:** dispose stylesheet listeners/state selectors with the owning tree, clear cache entries on unmount, preserve focus and key identity when the node is reused.
- **Errors:** unsupported property on a backend must identify property, target and backend; no silent success. Do not convert an unsupported CSS property to a zero dimension.

## 9. Migration and backward compatibility matrix

| Existing surface | Preserve | New capability cannot silently do |
| --- | --- | --- |
| `Text`, `Button`, `Input`, etc. | Existing direct props, events and return values | Reinterpret native props as CSS |
| `Image.width` + `layout_width` | Different meanings | Overwrite image dimension with container width |
| `Flex` | Existing layout props, nesting and constraints | Change its sizing default globally |
| `Grid`/`GridItem` | 12-column responsive model | Pretend CSS Grid track syntax is supported |
| `Scroll` | Native viewport semantics | Add implicit browser scrollbars without ownership contract |
| `Native` and custom adapters | Existing port and owner policies | Promise internal widget CSS painting |
| Component `key`, hooks, ref | Stable reconciliation identity | Reassign keys during style resolution |
| Rust/Python fallback | Same typed input and equivalent geometry | Introduce engine-specific style rules |

## 10. Required acceptance fixtures (design-time test vectors)

All fixtures need initial dimensions, style sources, expected computed properties and exact geometry before production changes.

1. **Legacy width coexistence:** `Image(width=80, layout_width="25%")`; native width stays 80, item width resolves at layout against a definite parent.
2. **Border sizing:** known content width, horizontal padding and border; compare specified content-box vs border-box with min/max constraints.
3. **Percentage and intrinsic:** definite versus indefinite containing block; no artificial zero for unresolved values.
4. **Cascade:** default, class selector, ID selector, inline style and legacy explicit layout prop conflict; expected winner and diagnostic are documented.
5. **Inheritance:** text color inherited across semantic containers, padding and geometry never implicitly inherited.
6. **Invalid values:** negative padding, NaN, unknown property, malformed selector or unsupported unit yield deterministic errors.
7. **Backend applicability:** known paint property must either pass each backend fixture or be marked unsupported; no all-backend automatic green.
8. **Resize:** repeated native resize/theme/DPI invalidations do not cause an unbounded commit loop.
9. **Reconciliation:** stable keys retain component state and no stale style selectors/handlers after unmount.
10. **Native escape hatch:** CSS controls the external container geometry, not undocumented native subtree internals.
11. **Alias mapping:** lowercase and original PascalCase map to the intended widget behavior while preserving keys and callbacks.
12. **Grid/Scroll compatibility:** nested Grid/Flex/Scroll readback remains within accepted geometry tolerances.

Tests are **planned, not executed**. CSS source parser, computed style or new lowercase APIs require functional tests, impacted-backend CI routing, and public behavior census receipts. Snapshot-only internal changes may justify census N/A.

## 11. Proposed delivery order on the same phase branch

1. **Owner resolves contract choices** in §12; update architecture approval log and specific F1–F5 contract deltas with explicit supersession where required.
2. Connect existing canonical box snapshots to Cinnamon's normal computation path behind a safe compatibility rollout, with identical Rust/Python fixtures.
3. Introduce CSS Core typed style registry and computed-style pipeline, then parser, finite selectors and cascade under explicitly certified subsets.
4. Adapt existing PascalCase controls to shared geometry/style contract without breaking native props.
5. Register reviewed lowercase tag aliases, then introduce new block/inline semantics only after geometry contracts and tests exist.
6. Finish Qt, Tkinter and Kivy capability support, paint behavior and full exact-SHA native conformance.

**Phase exit:** old API examples continue to work; new claimed markup/styles behave according to approved contracts; backend-specific evidence, public census and no confirmed high-severity layout loops; unresolved platform gaps are explicit. Full memory-leak resolution is a separate phase and is not falsely claimed here.

## 12. Decisions requiring explicit project-owner approval

The following are **PROPOSALS**, never assumed ratified by this file:

| Decision | Recommended choice | Current status |
| --- | --- | --- |
| CSS engine scope | Extensible parser + selector matcher + cascade + computed style, deployed incrementally | PENDING |
| Styling precedence | Scoped stylesheet < inline; retain legacy explicit layout precedence on existing components | PENDING |
| First supported selectors | Type, class and ID; no combinators/pseudo-states initially | PENDING |
| First CSS property subset | Geometry/Flex first, verified paint properties later | PENDING |
| New lowercase box sizing | Per-tag defaults, proposed border-box generic containers, old component semantics untouched | PENDING |
| Block and inline semantics | Dedicated contract; no fake Flex implementation | PENDING |
| Overflow | Existing Scroll ownership, fail closed for unsupported overflow | PENDING |
| Lowercase aliases | Finite registry, no generic HTML fallback | PENDING |
| Class/style declaration API | Decide `class` vs other spellings; stylesheet attachment API and security grammar | PENDING |
| Native renderer ports | Optional typed geometry/style capabilities; no blanket breaking Renderer protocol | PENDING |
| Unsupported declarations | Deterministic diagnostic/fail-closed; parser recovery rules separately specified | PENDING |

**Required review outcome:** Mark each choice APPROVED, DEFERRED (with non-impact justification), or REJECTED and record the date/revision and owner's evidence. Keep the existing `ARCHITECTURE_APPROVAL.md` global gate separately blocked until its outstanding conditions are actually disposed. Approval of this style proposal is not automatic approval of unrelated memory, packaging or hot-reload decisions.

## 13. Current implementation authorization

**Documentation/design only.** This draft does not authorize changes to public style semantics, HTML-like tags, native widget layout ownership, or global cascade. The certified canonical snapshot groundwork may remain on the phase branch. The next runtime increment starts only after the relevant owner decisions have been explicitly approved and the implementation's exact baseline is rechecked.
