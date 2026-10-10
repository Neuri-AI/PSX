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
