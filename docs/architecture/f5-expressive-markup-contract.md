# F5 — Expressive PSX Markup (Velto)

**Status:** DESIGN APPROVED / IMPLEMENTATION NOT STARTED.  
**Owner decisions:** 2026-10-14.  
**Authority:** This specification supersedes the earlier exploratory "Pending — expressive PSX markup" section of `docs/roadmap.md`. Scope is exclusively expressive markup. **M8 Intelligent Hot Reloading is explicitly excluded from F5 and assigned to deferred F6.**

## 1. Objective and invariants

Enable React-like declarative syntax inside Python-authored PSX markup without embedding a JavaScript runtime or browser. The static lexical transformer (M4B) is the primary authority for new expressions; Python remains the runtime. The explicit-scope M4A parser/compiler must remain safe and backward compatible, without executing expressions received from strings or using `eval`/`exec`. F5 must not change Cinnamon geometry or backend-owned widget layout.

Preserve existing host/component registries, VNode construction, renderer identities, reconciliation keys, lifecycle, scheduler, hook order, closure semantics, source maps and exception reporting. M4B transforms authored source before Python execution; the developer does not pass a manually assembled `scope` to `psx()`.

## Literal attributes and expression braces — owner clarification (2026-10-14)

**Binding grammar rule:** Curly braces in PSX Markup are reserved for variable references, mappings/list transforms, conditional expressions and arrow callbacks. **Static values are quoted, including numbers.** `<Flex gap="12" padding="50" />` is valid; `<Flex gap={12} />` is invalid and must produce a source-spanned `MarkupSyntaxError`, not silently accept a numeric constant. `<Flex gap={spacing} />` is valid only if `spacing` resolves in the authored lexical scope (M4B) or explicitly provided trusted mapping (M4A); an undefined identifier raises a diagnostic. No `eval`, `exec` or Python frame inspection may be used for lookup.

Quoted numeric attributes pass through the existing registry-backed coercion/validation: known integer-valued props are converted as appropriate, while string/text props remain strings. This preserves markup schema authority rather than guessing types from braces. Boolean presence syntax and established string props are unchanged.

For expressive F5 conditional, map and arrow constructs, braces delimit *validated compiled expressions* rather than an arbitrary Python evaluator. This is the **only extension** to simple references; bare literal expressions `{12}` in attributes remain invalid. A referenced variable can have any schema-valid value, including zero.

## 2. Owner-approved syntax

| Capability | Approved syntax | Interpretation |
| --- | --- | --- |
| Conditional AND | `{condition && <Element />}` | JSX-like short circuit, transformed to Python AST |
| Conditional branches | `{condition ? <A /> : <B />}` | JSX-like ternary, including nested ternaries |
| Lists | `{items.map((item) => <Text key={item.id}>{item.label}</Text>)}` | `.map()` is compiler syntax, **not** an assumed Python `list.map` method |
| Inline callbacks | `on_click={() => increment()}` or `on_click={(value) => set_value(value)}` | Arrow functions are statically transformed into Python closures |
| Equality | `==`, `!=` | Python equality semantics; `===` and `!==` are **not supported** |
| Conditional falsy | `False`, `None`, `0`, `""` and other falsy values | **No VNode** in conditional position; no React-style visible zero |

No `{#if}`, `{:else}`, `{#each}`, or other template control directives. No JavaScript `this`, `undefined`, `new`, object destructuring, `async` arrow functions, general JavaScript evaluation, or unconstrained `.map()` calls are authorized.

### 2.1 Conditional semantics

- Conditions evaluate exactly once and obey ordinary Python truth-testing rules (including `__bool__`/`__len__`) after static compilation.
- `&&` is a **conditional-node operator** in approved M4B markup expressions: falsy left operand produces no children; truthy left operand evaluates and returns the right-hand VNode, fragment, or approved sequence. Do not implement generic JavaScript value semantics for `&&` outside these positions.
- `? :` selects exactly one branch; inactive branches are not evaluated. Nested ternaries must have defined right-associative parsing and preserve their source spans.
- A falsy expression used as conditional output results in **zero child nodes**, including `0`. This is separate from ordinary unconditional text interpolation: `<Text>{0}</Text>` remains text `0` to preserve compatibility. A branch explicitly rendering `<Text>0</Text>` also renders text.
- Preserve order of surrounding siblings, key identity and native widget ownership when branches toggle. Define and test valid results (VNode, fragment, flat iterable of VNodes, null/falsy) and deterministic rejection of unsupported scalar or nested result forms without silently stringifying.
- Python comparisons use `==` and `!=`; reject `===` and `!==` with a source-position diagnostic.

### 2.2 Declarative map semantics

- A narrow M4B transform recognizes an approved `iterable.map((item) => <Element />)` expression and produces Python iteration, ordered VNode children, and lexical lambda bindings. Optional indexed callback `(item, index) => ...` may be supported only after explicit specification and tests in G1; it must not be inferred from a generic Python list method.
- `map` iterates a finite iterable in source order once per render. It is not a global monkey-patch of Python lists, and `map()` in unrelated Python code is not rewritten.
- Require an explicit stable `key` for dynamic sibling lists; catch missing and duplicate keys, illegal key types, reordering, insertion, deletion, and nested lists deterministically. Do not use list index as identity for reordered stateful items.
- No accidental eager invocation of event handlers during rendering. Arrow closures created in a map capture their individual item/lexical bindings, not the final loop value.
- Nested maps, conditional list items, empty sequences and fragments must be handled in a formally bounded normalization policy before G2/G3 acceptance. No implicit reparenting or remount when keys remain stable.

### 2.3 Arrow callbacks

- Statically parse arrow arguments and expression body into an ordinary Python callable, preserving lexical captures of locals, `self`, state setters and loop-item bindings.
- Support initially zero or one positional argument; further parameter forms and block bodies require a separate approved contract. The right-hand side is an expression, not an arbitrary JS statement block.
- Evaluate the callback body **only when the event invokes the function**. It must not run while creating markup.
- Preserve event binding, rebinding, native disabled behavior, teardown, hook compatibility and per-item closure identity. Diagnostics must reference the original authored source.

## 3. Compiler and runtime architecture

**M4B source → expressive grammar/AST → validated Python AST → existing VNode factories/reconciler → native backends.** Keep existing M4B transform before execution, static template caching keyed to grammar/compiler version, source maps for every transformed expression, and registry-defined component validation. Do not use dynamic frame inspection.

M4A explicit scope remains restricted and unchanged; markup from untrusted or dynamic strings must not gain expression-evaluation privileges. Generated ordinary Python callbacks may execute author-written application functions, but compiler-produced expression parsing is scoped to explicitly accepted constructs. Maintain the current component boundary and `use_state` calling-order invariants: hooks inside dynamic list callbacks or conditionally invoked component bodies must obey reconciler rules; component-owned hooks remain inside mounted child components.

New parser nodes and syntax must have unambiguous precedence for `&&`, `? :`, arrows, `.map()`, equality, grouping and nesting. Reject ambiguity instead of attempting JavaScript coercion. Explicit security tests must cover inaccessible attributes, template injection, invalid callback syntax and attempted escapes from the expression subset.

## 4. Official F5 implementation gates (G1–G6)

Every gate starts **NOT STARTED**, and may be CLOSED only with implemented functional behavior, appropriate backend test execution and immutable SHA evidence. An approved architecture is not implemented code.

| Gate | Delivery | Acceptance / mandatory evidence | Depends |
| --- | --- | --- | --- |
| **G1 — Expressive grammar and compiler contract** | Normative syntax, AST, precedence, source mapping, falsy and error taxonomy | Approved examples, positive/negative grammar fixtures, M4A/M4B isolation tests and explicit unsupported diagnostics; no claims of native rendering | F4 closure |
| **G2 — Conditional expressions** | `&&`, `? :` and nested branches in M4B | Each branch evaluated only when active, falsy produces no node, comparisons `==`/`!=`, stable VNodes and exact source diagnostics; compiler/Headless tests and routing | G1 |
| **G3 — Declarative `.map()` lists** | Compiler transform to Python iteration, keyed child production and nested forms | Empty/insert/remove/reorder/duplicate-key, nested map, index/closure behavior and identity retained under reconciliation; explicit negative cases | G2 |
| **G4 — Arrow functions** | Lexically captured callbacks in markup/event attributes and list items | Zero/one argument, capture/rebinding, deferred invocation, lifecycle/disabled/teardown, invalid-arrow diagnostics and cross-platform event evidence | G3 |
| **G5 — Composition, lifecycle and security** | Cross-feature combinations with reconciliation/hook invariants and safe M4A boundary | Adversarial nested ternary + maps + arrows, mixed native tree, state and key preservation, malformed/untrusted expressions, rollback, source-map integrity and F1–F4 regressions | G4 |
| **G6 — Integral F5 certification** | Complete executable acceptance matrix | All applicable Qt bindings/Tkinter/Kivy/Headless functional suites, compiler and safety tests, intelligent CI coverage, executed public census receipts, exact immutable SHA, unsupported-cell dispositions and explicit owner signoff | G1–G5 |

## 5. Three mandatory artifacts with every change

1. **Functional tests** for each new behavior, boundaries, errors, state updates, events, identity and teardown, plus native UI tests where applicable.
2. **Intelligent CI routing** in `scripts/ci/impact.py` and selector regressions in `tests/test_ci_impact.py`; actual GitHub Actions jobs must execute the affected suites.
3. **Executed public behavior receipts** in the source-derived certification census when new props, interactions, events or methods become public. No fabricated `PASS`, silent skip, or acceptance on a different code SHA.

Descriptive source/test filenames, not opaque `f5-g2` naming; phase identifiers belong in planning documentation. Documentation-only updates must not run product tests. Do not delete or weaken existing F1–F4 tests.

## 6. M8/F6 boundary (binding scheduling decision)

**F5 must not implement or modify Qyro CLI, Qyro Engine, or the postponed intelligent hot-reload workstream.** M8 is now scheduled under **F6 — Intelligent Hot Reloading**, with implementation deferred until the owner revises CLI and Engine. F6 will assess the existing watcher/supervisor/compatible refresh vertical slice, reconcile `PROCESS_RESTART` with safe component updates, and separately specify snapshot restoration, dependency graph, diagnostics and CLI integration. F6 gates and acceptance criteria require their own future approval; no inferred delivery date. F5 completion does not depend on F6.
