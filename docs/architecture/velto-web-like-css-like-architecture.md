# Velto — Web-like UI & CSS-like Architecture Specification

**Version:** 1.1 (architectural baseline; dual-level component model)  
**Status:** Approved product decisions; implementation and browser-parity certification pending  
**Scope:** PSX Markup, Cinnamon, style resolution, native renderers, component APIs  
**Date:** 2026-10-17

## 1. Normative objective

Velto SHALL offer web-like markup, CSS-like styling, and web-compatible layout behavior implemented through native Python backends. No browser DOM, WebView, browser engine, or competing geometry engine is required or permitted as the foundation of UI layout. Cinnamon remains integrated inside PSX and is the sole layout authority.

Compatibility means testable behavior for a declared subset, not a claim of full HTML/CSS support. Each supported property, tag, and behavior MUST have normative semantics, backend capability declarations, and differential tests where applicable.

### Dual-level API decision (supersedes removal plan)

Existing public Velto UI components (`Button`, `Text`, `Flex`, `Grid`, `GridItem`, `Checkbox`, `Radio`, `Switch`, `Input`, and other registered components) SHALL remain available and retain their documented public contracts. Their internals SHALL be restructured as needed to participate in the universal box model, CSS-like styling, PSX lifecycle and native backend contracts. Lowercase web-like tags SHALL be the recommended compositional syntax for new applications, **not** a replacement for the higher-level component library.

**Two public abstraction levels:**

1. **Web-like Primitives** are fundamental semantic/formatting elements (`div`, `span`, `p`, `input`, `label`, `button`, etc.). They expose web-like composition and behavior, subject to Velto's declared compatibility subset. An `<input type="checkbox" />` is a checkbox control; its label is a separately composable `<label>`.
2. **Velto Components** are portable higher-level abstractions (`Switch`, `Radio`, `Checkbox`, `Button`, `Flex`, `Grid`, etc.). They may combine primitives, supply cohesive properties (such as `label` where that component's contract supports it), encapsulate state/interaction, or specialize layout. They need not be visually complex or be composed of multiple native widgets to qualify.

This distinction is **semantic and functional**, not merely capitalization or aliasing. The two families MAY produce equivalent output for equivalent computed styles and behavior but MUST NOT be presumed to have identical public props, default styling, accessibility semantics, or internal structure. Existing components MUST NOT be deleted, automatically deprecated, or replaced with lowercase aliases.

**Decision reconciliation:** B1, B2, B5 and D5 are approved *as revised* by this dual-level model. This supersedes the prior breaking-removal decision and preserves the older component API while making web-like markup the recommended foundation for new work.

## 2. Architectural ownership and pipeline

1. **PSX markup parser/compiler** parses lowercase web-like tags, existing PascalCase Velto components, custom components, Python-backed safe expressions and event bindings. It validates tag/attribute syntax without executing arbitrary code.
2. **VNode/reconciler** maintains keyed identity, component state, mount/update/unmount lifecycle, and logical parentage across both API levels; higher-level components may expand into primitive subtrees without losing public identity.
3. **Style resolver** computes matched declarations, cascade, inheritance, custom properties, computed values and state-dependent styles; it must not calculate final box positions.
4. **Cinnamon (within PSX)** resolves box tree, formatting contexts, intrinsic measurement, line boxes, box sizing, block/inline flow, flex/grid, positioning and overflow geometry.
5. **Native renderer/paint adapter** measures native content when requested, creates controls or drawing surfaces, applies final geometry and painting, handles input/focus/accessibility and teardown. It must not override Cinnamon's geometry.

The style tree, layout box tree, accessibility tree and native widget tree need not have a one-to-one correspondence. Text runs and semantic wrappers may have no individual native widget.

## 3. Universal box model — A1

Every visual element MUST produce one or more layout boxes according to its computed `display` and formatting context. `display: none` produces no layout box, but does not by itself imply component unmount. Each box models content, padding, border and margin edges, with defined sizing constraints, writing direction and coordinate space. `box-sizing: content-box | border-box` SHALL be supported and tested. `box-sizing` defaults to `content-box` unless the product explicitly adopts a global reset; no implicit browser stylesheet reset is assumed.

Margins are outside the border box; padding and borders affect outer size according to `box-sizing`. CSS min/max constraints, auto sizes, percentage resolution and negative margins require normative algorithms, not ad-hoc renderer interpretations. Non-visual semantics may contribute accessibility nodes without generating boxes.

## 4. Formatting contexts and layout — A2–A6

### A2: div defaults
`<div>` is a generic block container with initial `display: block`. Its width/height are auto by default, and its children participate in normal flow. It has no intrinsic padding, border or margin unless user-agent/default style rules say otherwise. It is not an alias for old `Flex`.

### A3: display modes
The target display set is `block`, `inline`, `inline-block`, `flex`, `grid`, and `none`. Each mode requires a documented formatting context and cross-backend tests before it can be marked supported. CSS display combinations outside the approved subset MUST raise actionable diagnostics, not silently map to a different mode.

### A4: intrinsic measurement
Cinnamon owns sizing decisions; adapters may return content measurements and baselines under explicit constraints. Define min-content/max-content contributions, preferred intrinsic dimensions, aspect ratio, replaced-element sizing, fonts, line height, text wrapping, device pixel ratio, and stable rounding. Measurement caches MUST invalidate when fonts, text, content, DPI or style constraints change. Native toolkit preferred sizes are measurement inputs, never final layout authority.

### A5: flow and positioning
Implement block/inline normal flow and line boxes first; then relative and absolute positioning as independently gated capabilities. Specify containing blocks, static position, offsets, stacking contexts and painting order before release. Margin collapsing must match the declared browser-reference subset, including edge cases; do not approximate it silently. `position: fixed` and `sticky` are deferred until viewport/scroll semantics are approved.

### A6: overflow
Target `visible`, `hidden`, `auto`, `scroll`, including clipping, scroll containers, scroll offsets, hit testing, scrollbar sizing and scroll lifecycle. Horizontal/vertical overflow rules and native backend differences require explicit tests. Unsupported values or combinations MUST be diagnosed.

## 5. Dual-level public component model — B1/B2

Velto SHALL expose **two complementary public families**, not competing UI engines:

### 5.1 Web-like Primitives (recommended for new application markup)

Lowercase tags form the low-level, web-inspired vocabulary. They implement their own semantic contracts, defaults and input behavior; they are **not aliases** for similarly named PascalCase components.

**Foundation (P0):** `div`, `p`, `h1`–`h6`, `button`, `input` (initially text), `img`.

**Next wave (P1):** `span`, `strong`, `em`, `small`, `code`, `br`, `hr`, `label`, `a`, `ul`, `ol`, `li`, `textarea`, `select`, `option`, `progress`, semantic structural tags (`main`, `header`, `footer`, `section`, `article`, `nav`, `aside`), and approved input types (`checkbox`, `radio`, `number`).

**Advanced (P2):** `form`, `meter`, `dialog`, `details`, `summary`, and `table` family if a table formatting algorithm is explicitly designed.

**Not generic HTML primitives:** `html`, `head`, `body`, `script`, `iframe`, `meta`, and asset `link`/`style` tags. `canvas`, `video` and `audio` require separate native contracts, not presumed browser equivalence.

Tag defaults (display, font, margins, control behavior) MUST be published in a versioned Velto default stylesheet. Semantics and accessibility MUST not be inferred from visual style alone. `input` types have explicit capability gates.

### 5.2 Velto Components (retained higher-level API)

Existing public components, including `Button`, `Text`, `Flex`, `Grid`, `GridItem`, `Input`, `Checkbox`, `Radio`, `Switch`, `Slider`, `Select` and others, SHALL retain their public names, supported props, callback signatures, and documented behavior during internal modernization. The exact inventory and contracts MUST be taken from the target `develop` source and its tests; this list is illustrative, not an exhaustive inventory or a claim that all listed features have identical implementations.

Components MAY offer composite structure, a built-in label, layout specialization, standardized visual variants, richer interaction, or a convenient API. **Do not invent properties:** for example, the inspected `develop` `Checkbox` contract currently exposes `checked`, `enabled`, and `on_change` but not `label`; `Switch` and `Radio` expose `label`. A future `Checkbox.label` feature is an optional additive contract proposal, not a verified current capability.

### 5.3 Normative relationship

- Primitive contracts SHALL NOT depend on higher-level Velto Components.
- Higher-level components SHOULD compose primitives when this preserves their established behavior and native parity; direct native adapters are permitted when justified by capability, accessibility, performance, or compatibility.
- Both families MUST share style resolution, Cinnamon box geometry, event normalization, reconciliation, accessibility infrastructure and renderer capability reporting. No second layout/style engine is permitted.
- Similar names do not imply identical behavior: `div` defaults to block; `Flex` preserves its documented flex semantics. Lowercase `button` and `Button` may have different property models and defaults.
- Equivalent rendered behavior is a **testable conditional goal** when computed styles, state, constraints, content and semantics match, not an unconditional promise that all pairs render identically.
- A higher-level component's public props MUST have defined precedence relative to CSS declarations, default styles, inherited styles and internal part styles. This precedence is a dedicated design gate; never silently override consumer CSS or legacy props.
- Styling composite internals (parts/slots or scoped selectors), focus ownership, label association and accessibility aggregation require explicit contracts before public exposure.

### 5.4 Illustrative composition (target API; not proof of implementation)

Web-like composition:

```jsx
<div>
    <input id="notifications" type="checkbox" checked={enabled} on_change={set_enabled} />
    <label for="notifications">Enable notifications</label>
</div>
```

Higher-level component with an **already documented** `label` prop:

```jsx
<Switch label="Enable notifications" checked={enabled} on_change={set_enabled} />
```

The examples express abstraction levels, **not identical control types**: `Switch` is a toggle switch, while `input type="checkbox"` is a checkbox. A labeled `Checkbox` is a possible future additive feature, not part of the inspected current `develop` contract.

## 6. Inline text — B3

Inline tags (`span`, `strong`, `em`, `small`, `code`) form styled runs and line boxes; they are not necessarily separate widgets. Specify whitespace collapsing, `white-space`, wrapping, explicit breaks, bidi direction, font fallback, glyph shaping, text selection, baseline alignment and intrinsic measurement. `<br />` inserts a line break within the inline formatting context. `<p>` is a block with a defined default stylesheet. Headings expose semantic levels independently of their computed font styles.

## 7. Semantics and accessibility — B4

Define accessible role/name/description, heading level, label-to-control association, focus order, keyboard activation, disabled/read-only behavior, error announcements and screen-reader exposure. A semantic element can exist in the accessibility tree without having its own native widget. Backend adapters MUST report capability gaps; accessibility behavior cannot be certified by geometry tests alone.

## 8. Custom and native components — B5

Both retained Velto Components and new custom Python components and native-widget adapters MUST participate in the same box, sizing, style and lifecycle contracts as built-ins. A custom component can expand into children; a leaf native control is treated as a replaced/measurable element with explicit intrinsic dimensions and baseline. Backend-specific integrations (e.g. Qt widgets) are allowed but must declare supported backends and cannot override Cinnamon layout. No mandatory `<Window>` tag is introduced; top-level window creation remains an application/runtime concern.

## 9. CSS source and cascade — C1/C2

CSS-like styles may be loaded from external `.css` files and assigned via `class`, `id`, and `style` to web-like primitives and, under a defined public styling contract, higher-level Velto Components. The public API for registering style files is a separate design gate; no unimplemented import/loading syntax is normative yet.

Phase 1 selectors: type, `.class`, `#id`, multiple classes, selector lists, and documented specificity. Establish a deterministic precedence model: default stylesheet < application stylesheets < inline declarations, with source order resolving equal-specificity ties. Define how `!important` is handled before claiming CSS cascade compatibility; until approved, diagnose unsupported usage. Attribute and combinator selectors are later gates.

Styles are resolved per VNode/element, including state changes. `class` is a selector attribute, not a Python class. `id` uniqueness is checked within the chosen application/root scope and violations produce diagnostics.

## 10. Property rollout — C3

**CSS Core:** parser, declarations, class/id/type selectors, specificity, computed-style inspection.

**CSS Layout:** `display`, `box-sizing`, `width`, `height`, `min-width`, `min-height`, `max-width`, `max-height`, `margin*`, `padding*`, `border-width*`, `gap`, `flex-direction`, `flex-wrap`, `justify-content`, `align-items`, `align-self`, grid tracks/placement, and later `position`/offsets and overflow. Values include supported px, percentages, `auto`, and explicitly certified relative units.

**CSS Visual:** `color`, `background-color`, border styles/colors/radius, `font-family`, `font-size`, `font-weight`, `line-height`, text alignment, `opacity`; later backgrounds/shadows and advanced paint.

**CSS States:** `:hover`, `:focus`, `:active`, `:disabled` and state-triggered recalculation.

**CSS Advanced:** custom properties, `var()`, inheritance, compound selectors, themes, responsive mechanisms and extended units, each behind separate approval and tests.

Properties not supported MUST generate an actionable diagnostic in strict mode. Support tables MUST distinguish parsing, computed-style support, layout, painting and per-backend behavior.

## 11. Inheritance and defaults — C4

Publish a versioned default style sheet for web-like tags and explicit, separately documented component defaults for retained Velto Components. Specify inheritable properties explicitly (e.g. color and font properties) and non-inheritable box properties. Support `inherit`, `initial`, `unset` only once their semantics are tested. Defaults MUST be independent of platform-specific toolkit stylesheet defaults to the extent required by the declared compatibility profile.

## 12. State selectors — C5

PSX normalizes hover, focus, active and disabled states from native backend events. Style invalidation recomputes affected declarations, layout and paint only when necessary. State changes MUST not remount keyed components. Keyboard and pointer semantics are specified independently of toolkit-specific event objects.

## 13. Variables and themes — C6

CSS custom properties (`--token`) and `var()` are an advanced phase. Define lexical inheritance, fallback, cycle handling, computed-value resolution, theme scoping and update invalidation. Theme switching must preserve component identity and avoid unnecessary remounts. Theme APIs and stylesheet-loading APIs require their own public contracts.

## 14. Events — D1

Canonical event names are Pythonic snake_case: `on_click`, `on_change`, `on_input`, `on_focus`, `on_blur`, `on_key_down`, etc. Standardize event payloads independently of Qt/Tk/Kivy; define propagation/cancellation only if supported and tested. No automatic JSX camelCase alias requirement. Existing markup expression and callback support must be checked against the current compiler before documenting runnable examples.

## 15. Forms and controlled inputs — D2

State lives in hooks or application state. Inputs expose controlled `value` or `checked`, and explicit callbacks; they MUST not silently mutate Python state. Define caret/selection preservation, IME composition, numeric validation, focus and disabled/read-only contracts. `<label>` associates accessible names with controls. `<form>` is a later optional coordinator for Enter/submit, validation, duplicate submission prevention and focus-on-error, never a second state store.

## 16. Native capability gaps — D3

Each feature has a capability matrix per Qt binding, Tkinter and Kivy. Unsupported functionality MUST be reported with tag/property/backend/context and a suggested supported alternative. Diagnostics should happen at compile time when statically knowable, otherwise at style resolution/mount/runtime. Silent fallback is forbidden where it changes promised geometry, semantics or interaction. A strict compatibility profile may reject unsupported capabilities; any permissive profile must be explicit and documented.

## 17. Parity and acceptance — D4

Use browser-reference fixtures (e.g. Chromium) to compare computed box rectangles, content/padding/border/margin edges, baselines, line wrapping, flex/grid placement, clipping and paint snapshots. Fixtures MUST specify browser version, viewport, DPI, fonts, OS, CSS, content and expected outputs. Define tolerances separately for geometry, text shaping and raster differences before certification. Require functional backend tests for creation, measurement, updates, focus, readback, teardown and accessibility. Register impacted tests in `scripts/ci/impact.py` and maintain public-behavior census evidence. Certify immutable source SHAs, not documentation-only claims.

## 18. Compatibility and modernization — D5 (revised)

This is an **additive public API evolution with internal refactoring**, not a planned removal of existing built-in components. Retain the existing PascalCase names, props, supported callback payloads, default behaviors and public import paths as verified from the target source. New lowercase web-like tags are recommended for new applications; old components remain first-class and are **not deprecated solely because web-like primitives exist**.

A compatibility inventory SHALL record each existing component's public contract, backend-specific behavior, intrinsic measurement, layout, styling and accessibility before refactoring. For each component, create baseline regression fixtures and verify compatibility after integration with the universal box model and CSS-like resolver. Any unavoidable behavior difference requires explicit approval and release documentation, not an implicit breaking change.

Migration documentation SHALL explain **optional** adoption of web-like primitives and interoperability between the two levels. No forced rewrite is required. Component-specific improvements (for example adding an optional label where absent) are separately reviewed additive features; do not misrepresent them as already implemented. Maintain non-UI application/runtime compatibility as independently certified.


## 19. Recommended implementation phases

| Phase | Scope | Acceptance gate |
|---|---|---|
| F0 | Freeze dual-level contracts, inventory all existing component APIs and approve test fixtures | Primitive contracts plus legacy component regression baseline |
| F1 | Universal box model, foundational primitives, and adapter seams for retained components | Differential box/flow tests plus unchanged legacy public contracts |
| F2 | CSS parser, selectors, cascade and defaults | Computed-style fixtures and diagnostics |
| F3 | Flex, Grid, intrinsic sizing, percentages, positioning and overflow | Cinnamon browser-parity fixtures across backends |
| F4 | Visual CSS and rich text | Text and paint comparisons |
| F5 | States, inputs, keyboard and accessibility | Interactive parity and screen-reader checks |
| F6 | Extended semantic tags, forms, composite-component styling and native extension API | Backend capability matrix, component composition and lifecycle |
| F7 | Variables, themes and advanced selectors | Dynamic style invalidation tests |
| F8 | Release readiness, dual-API docs and cross-platform regression | Immutable SHA certification, backward-compatibility evidence and optional adoption guide |

Each phase MUST include testing and backend certification for its own scope; F8 is a release gate, not the first testing phase. Sequence may change when dependencies are discovered in source inspection.

## 20. Open technical gates (not approvals to invent behavior)

1. Precise CSS reference version and compatibility subset (including margin collapsing, display semantics and replaced-element algorithms).
2. Source syntax and lifecycle for registering `.css` files, inline style object/string, and style scoping.
3. `!important`, origins/layers, pseudo-elements, and whether `:root` exists without a browser document.
4. Exact intrinsic measurement contract, native text shaping strategy, scrollbar geometry and DPI rounding.
5. Hit testing, event bubbling, default actions, and keyboard focus navigation.
6. `display: contents`, `visibility`, `position: sticky/fixed`, stacking contexts and paint order.
7. Release versioning, backward-compatibility criteria, and optional web-like adoption documentation.
8. Explicit native extension protocol and per-backend fallbacks.
9. CSS-vs-component-prop precedence, internal part/slot styling, accessibility aggregation, and composition vs direct native adapter criteria.

None of these may be silently treated as implemented or approved merely because the architectural direction is approved.

## 21. Source and decision trace

Based on the user-provided **Velto — Web-like Components Specification v0.1** (2026-10-14), the approved A1–D5 decision matrix (2026-10-17), and the latest explicit override retaining all existing Velto Components as a higher-level API while adding web-like primitives as the recommended lower-level markup. The earlier removal/from-scratch replacement decision is superseded. Inspected `develop` source establishes that `Checkbox` currently has no portable `label` prop, while `Switch` and `Radio` do. This document specifies target behavior; it does not assert current code support or verified browser parity.