# Expressive Markup — Grammar and Compiler Acceptance Ledger

**F5-G1 status:** IN PROGRESS — kickoff 2026-10-14.  
**Branch:** `feature/expressive-markup-grammar`, created from `develop`.  
**Normative source:** [F5 expressive markup contract](f5-expressive-markup-contract.md).

This ledger tracks **implementation evidence**, not just architecture approval. G1 is not CLOSED until a parser/transform grammar, source-location-aware invalid diagnostics, negative isolation tests, CI impact coverage, and code-SHA-linked passing runs are demonstrated.

## Non-negotiable language choices

| Feature | Approved | Boundary |
| --- | --- | --- |
| Conditional nodes | `{ready && <Text />}` | Falsy result creates no VNode; no JavaScript runtime |
| Ternary nodes | `{ready ? <A /> : <B />}` | Nested ternaries, inactive branch not evaluated |
| Lists | `{items.map((item) => <Text key={item.id} />)}` | Static transform, not `list.map` |
| Arrows | `on_click={() => save()}`, `on_click={(item) => save(item)}` | Python lexical closures, call deferred |
| Equality | `==` and `!=` | `===`, `!==` not part of F5 |
| Falsy conditional output | No VNode even for `0` | Plain text interpolation still renders `0` |
| Scope safety | Authored static M4B templates only | M4A external/dynamic input remains restricted |
| Phase exclusion | M8 postponed to F6 | No Qyro CLI/Engine changes in F5 |

## Baseline architecture (to preserve)

- `psx/markup/lexer.py`, `parser.py` and `ast.py`: existing M4A restricted reference grammar. Explicit-scope templates must not gain arbitrary Python execution.
- `psx/markup/transform.py`: M4B static lexical transform; generated Python AST captures caller lexical bindings, retains source mapping, and keeps authored code intact.
- `psx/markup/compile.py`: templates resolve registered constructors, produce existing VNodes/Fragments and keep safe M4A compilation separate from statically authored expressions.
- `psx/core/reconcile.py`: keyed identity, component hook ordering, native ownership and renderer scheduling remain authoritative. No new layout engine or widget lifecycle rules.

## G1 acceptance matrix (all initially pending)

| Case | Required observation | Evidence |
| --- | --- | --- |
| Lexical precedence | `==`/`!=`, grouping, `&&`, ternary, arrow and `.map` parse deterministically | Pending test |
| Conditional nodes | Truthy/falsy and zero semantics defined separately from text interpolation | Pending test |
| Ternaries | Right-associativity, nested markup branches, no eager execution | Pending test |
| Declarative mapping | Compiler-only `.map`, finite iterable and stable key requirements | Pending test |
| Arrow closure | Zero/one argument; syntax errors and lexical capture preserved | Pending test |
| M4A isolation | Dynamic untrusted strings cannot invoke new expression paths | Pending test |
| Source mapping | Diagnostics point to original markup span and filename | Pending test |
| Unknown syntax | `===`, `!==`, `{#if}`, JS block/async arrows rejected clearly | Pending test |
| Existing compatibility | Current `psx()` M4A and M4B fixtures stay green | Pending test |
| CI routing | Compiler/parser/tests select affected core, Headless and any native consumers through `scripts/ci/impact.py` | Pending test |
| Public census | New public interactions have reviewed executed receipts or documented nonapplicability | Pending review |
| Immutable CI | Selected jobs succeed on the exact code SHA of the new grammar implementation | Pending run |

## Technical decisions to finalize during G1

1. **Grammar containment:** expressive syntax is accepted only by the M4B static lexical compiler, never implicitly by `compile_template` on runtime/untrusted M4A strings.
2. **Parser precedence:** parenthesized expressions are explicit; `&&` binds more tightly than `? :`; ternaries nest right-to-left. Python `==`/`!=` are comparisons, not strict JavaScript equality.
3. **Result normalization:** conditional absent output contributes zero children, while normal literal text interpolation keeps its historical behavior. Mapping output requires stable keys. Clearly diagnose invalid result categories; never silently coerce nested structures into text.
4. **No hooks inside conditional expression bodies:** state hooks remain in mounted components and keep their unconditional invocation contract.
5. **Static compilation only:** generated callable and iteration logic derives from validated syntax into ordinary Python AST, not `eval`, arbitrary exec or frame capture.
6. **No removed builders:** example syntax must use current registered Velto components. Legacy `Row`/`Column` are not public after F3.

## Next engineering increments

A. Extend the grammar AST model and lexer/parser specification with parser fixtures plus failure spans (syntax only).  
B. Add source-transform fixtures demonstrating correct binding names and safe Python AST generation, with M4A isolation.  
C. Verify change-router selection and public-census applicability; execute relevant CI and record an immutable code SHA.

**State:** specification groundwork recorded; no new parser behavior is claimed as shipped or certified.
