# PSX implementation roadmap

Implementation status is evidence-based; milestone placement does not certify a
feature as complete.

| Milestone | Name | Status |
| --- | --- | --- |
| M0 | Research & Architecture | implemented baseline |
| M1 | Core & Headless Renderer | implemented baseline |
| M2 | PySide6 Renderer | implemented baseline |
| M3 | Reactivity & Hooks | implemented baseline |
| M4A | PSX Markup | implemented baseline |
| M4B | Static Lexical Transform | implemented baseline |
| M5 | Pydux Integration | implemented baseline |
| M6 | Qyro Integration | implemented baseline |
| M7 | Tkinter Renderer | implemented; native macOS smoke testing remains environment-dependent |
| M8 | Intelligent Hot Reloading | vertical slice implemented |
| M9 | Kivy & Qt Variants | implemented; native graphical smoke remains environment-dependent |
| M10 | Advanced UI & Native Interoperability | implemented; native adapter smoke is renderer-dependent |
| M11 | Alpha Release | alpha release candidate |
| M12 | PSX Playground & Visual Layout Inspector | implemented standalone React semantic development slice |
| M13 | PSX Visual UI Builder | planned |

## M8 — current scope

Dependencies: M3 scheduling/disposal, M4B source transforms, and renderer
ownership. The implemented dev-only baseline uses a dependency-free polling
watcher, debounce, project-path classifier and supervised child process. Python
source, manifests and native extension changes receive `PROCESS_RESTART`;
caches, virtual environments, build output and editor artifacts are ignored.
The supervisor prevents overlapping children and continues watching after a
restart. Frozen and non-development configurations disable watching.

Acceptance currently verified: rapid changes debounce; atomic replacement is
detected; child restart is clean; snapshots are JSON-only/versioned; production
configuration is disabled. Deferred acceptance: compatible in-process component
refresh, hook-state preservation across a code edit, safe module rebind,
automatic snapshot restoration and Qyro CLI `--hot-reload` integration.

## Dependencies, risks and testing

M9 depends on validated backend API/version matrices. M10 depends on D11 layout
semantics and capability-gated native ownership. M11 requires CI, packaging,
performance/leak validation and documentation. M12/M13 are post-alpha and must
reuse D11 semantics. The principal M8 risk is pretending arbitrary Python or
native dependencies are safe to reload; the supervisor is therefore the
documented fallback, not a failed hot-update implementation.

Every supported renderer retains its own native identity/event/cleanup tests.
M8 requires watcher debounce, atomic save, ignored paths, child lifecycle,
syntax-error recovery, frozen/production disable, snapshot validation and
diagnostics tests. Native GUI smoke tests complement, but do not replace,
deterministic headless tests.

## Pending — portable Flexbox/Grid layout system (proposal)

**Architecture document:** [SFLE — Shared Flex Layout Engine](architecture/sfle.md).
**F1 contracts:** [Approved decisions and open technical contracts](architecture/sfle-f1-contracts.md).
**Ratified F1.6/F1.7 contract:** [CSS box model and percentage resolution](architecture/sfle-f1-box-model.md).
Approved: closed shared metadata validation with single-root components,
metadata inert outside Flex, layout_width/layout_height namespace, and tagged
immutable lengths. The CSS box model and property-specific percentage rules
are specified, while D-F1.8–D-F1.12 and F1-RUST remain pending.

D-F1.1–D-F1.7 approved at architecture level: `Flex` with direct child layout props,
`snake_case`, progressive browser conformance, UI-thread native measurement,
and strict geometry comparison. D-F1.8–D-F1.12 and Rust policy remain open.

SFLE is the proposed backend-neutral CSS Flexbox geometry engine. The design
prioritizes browser-like visual layout results across Qt, Kivy, Tkinter, and
Headless, with renderer-specific intrinsic measurement and geometry application.
The specification covers the algorithm, Mermaid diagrams, lifecycle, adapters,
conformance strategy and outstanding decisions; SFLE remains unimplemented.

**Status:** F1 architecture partially approved; remaining public API details,
acceptance thresholds and implementation are not yet approved. Reference:
[Flexbox Grid](http://flexboxgrid.com/) (a responsive 12-column layout system
built on CSS Flexbox). PSX should reproduce the *layout semantics* in native
desktop renderers rather than embed CSS or assume a browser engine.

### Scope to design

- **Flex-style layout:** row/column flow, `gap`, `wrap`, `grow`, `shrink`,
  `basis`, `align_items`, `align_self`, `justify_content`, and ordering.
- **Responsive 12-column grid (Flexbox Grid-inspired):** spans, offsets,
  automatic/equal-width columns, nesting, distribution and alignment; column
  sizes may depend on breakpoint rules for the **container/window width**.
- **Optional CSS Grid-like track layouts:** consider a distinct `Grid` /
  `GridItem` contract with explicit rows/columns, track sizing and spans.
  Do not conflate Flexbox Grid's flex-based 12-column system with CSS Grid.
- **Portable measurement and layout:** intrinsic/min/max sizing, percentage or
  proportional widths, `gap`/gutters, padding, constraint propagation,
  overflow behavior, high-DPI scaling and deterministic recalculation on resize.
- **Responsive behavior:** define desktop-appropriate breakpoints, initial
  layout and resize transitions; avoid unnecessary widget recreation or loss
  of component state during reflow.
- **Renderer support:** Qt, Kivy, Tkinter and Headless should implement the
  same semantics through adapters or a shared backend-neutral layout model.
- **Architecture:** extend/reuse existing `Row`/`Column` and D11 layout
  contracts where compatible. Determine whether new `Flex`, `Grid` and
  `GridItem` components are warranted after an API design review. Reuse
  the same geometry rules in the PSX Playground Visual Layout Inspector and
  future Visual UI Builder.

### Aspirational markup (not currently supported)

```xml
<Flex direction="row" gap={12} wrap="wrap" justify_content="between">
    <Grid columns={12} gap={12}>
        <GridItem span={8}>
            <Sidebar />
        </GridItem>
        <GridItem span={4}>
            <Details />
        </GridItem>
    </Grid>
</Flex>
```

The snippet illustrates layout intent only; component names, accepted props,
nesting rules and responsive syntax are **not yet decided**. Future design
cards should settle those choices before any implementation. Do not add
automated tests as part of the current component DX-first rollout.

## Pending — expressive PSX markup (design not approved)

These are future compiler/runtime capabilities, **not supported today**.
Design and prioritize them separately from portable UI components such as Badge.

- **Conditional rendering — React/JSX-style syntax confirmed:** support
  `{condition && <Element />}` and `{condition ? <A /> : <B />}`,
  including nested ternaries and component expressions inside interpolation.
  Do **not** introduce `{#if}`/`{:else}` markup directives. A future compiler
  transformation should parse JSX-like syntax into safe Python-compatible
  expressions; this is not JavaScript runtime execution. Decide and document
  details of `===` comparisons, falsy scalar rendering (especially zero),
  short-circuit semantics, type constraints, precedence, and preservation of
  VDOM identity and hook ordering before implementation.
- **Inline lambda expressions:** explore supporting lambdas in attribute
  expressions and event handlers, subject to lexical scope resolution,
  callable safety and documented restrictions. Do not assume arbitrary
  Python execution is permitted by the current expression evaluator.
- **Declarative list rendering / JS-like `.map()`:** offer a natural syntax
  for mapping collections to repeated VNodes, potentially via Python
  comprehensions, `map(...)`, or a dedicated PSX directive. Python lists
  do not have JavaScript's `Array.map()`, so literal `items.map(...)`
  would require an explicit compiler transform or wrapper API.
- **Acceptance requirements:** correctly capture local variables, preserve
  stable `key` identity when reordering, reconcile add/remove/conditional
  branches, and preserve hook ordering rules and expression security.

All syntax, error handling, transform strategy and rollout order remain
pending a dedicated design decision.
