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

## First executable grammar increment — CERTIFIED, G1 STILL OPEN (2026-10-14)

**Immutable implementation SHA:** `949d45d0d252dec4fcc108c6644322352380eff3`. **Required native selective CI:** https://github.com/Neuri-AI/PSX/actions/runs/38606480969 — SUCCESS (14/14 executed jobs, including final mandatory conclusion); four unrelated Rust/Chromium/SFLE/wheel jobs impact-skipped and are **not** represented as executed. PR: https://github.com/Neuri-AI/PSX/pull/25 (draft, targeting `develop`). CI core job reports **558 passed** plus 5 passed subtests including new grammar fixtures; public core suite **757 passed**. Legacy scoped public census Grid/GridItem **62/62** and native Grid/GridItem **150/150** executed unchanged; these **are not receipts for unshipped F5 interactions**.

**Implemented:** `psx/markup/expressive_syntax.py` provides non-executing, source-spanned operator preflight for `&&`, `? :`, `=>`, `.map(`, `==`, `!=`. It tracks quote escapes and matching expression delimiters; rejects strict JS comparisons, unsupported template control directives, async arrows and unclosed quoted/delimiter inputs with `MarkupSyntaxError` filename/line/column. It intentionally neither parses nested JSX completely nor emits VNodes or Python AST. `tests/test_expressive_markup_syntax.py` exercises 12 grammar/isolation cases; existing M4A explicit-scope and current M4B lexical transformation remain unchanged. Source and test routes are connected to `scripts/ci/impact.py` with an exact router test and executable core workflow command.

**Remaining before G1 CLOSE:** define and implement a full expression AST/grammar with nested JSX structural parsing, operator precedence and right-associative ternaries; validate narrow `.map` callback parameter grammar, legal arrow parameter/body shape and lexical name resolution boundaries; complete accurate markup-to-Python source spans and unsupported diagnostics for malformed nested branches; test attribute-expression containment and additional M4A negative cases. The current lexical token preflight is an initial contract foundation **not a completed grammar compiler**. No new F5 public runtime operations exist yet, so public census new-operation receipts are not applicable for this increment; revisit at G2–G4 when interactions ship.

**Gate F5-G1: IN PROGRESS.** No work on M8/F6, Qyro CLI, or Qyro Engine.
