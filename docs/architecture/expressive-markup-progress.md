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

## Literal-versus-reference grammar clarification (2026-10-14)

The owner clarified that `<Flex gap="12" />` is the approved literal syntax; numeric `gap={12}` must fail because braces are reserved for named references/expressions. The parser's old numeric-brace exception has been removed. Quoted integers use the existing component property coercion, preserving previously supported VNode values; unknown `{name}` continues to fail through M4A explicit-scope lookup or M4B lexical lookup with source coordinates. This is a behavior-changing parser correction with accompanying tests and CI regression verification. No dynamic `eval` or frame lookup is added. **G1 remains IN PROGRESS until the full expressive AST is implemented.**

## First executable grammar increment — CERTIFIED, G1 STILL OPEN (2026-10-14)

**Immutable implementation SHA:** `949d45d0d252dec4fcc108c6644322352380eff3`. **Required native selective CI:** https://github.com/Neuri-AI/PSX/actions/runs/38606480969 — SUCCESS (14/14 executed jobs, including final mandatory conclusion); four unrelated Rust/Chromium/SFLE/wheel jobs impact-skipped and are **not** represented as executed. PR: https://github.com/Neuri-AI/PSX/pull/25 (draft, targeting `develop`). CI core job reports **558 passed** plus 5 passed subtests including new grammar fixtures; public core suite **757 passed**. Legacy scoped public census Grid/GridItem **62/62** and native Grid/GridItem **150/150** executed unchanged; these **are not receipts for unshipped F5 interactions**.

**Implemented:** `psx/markup/expressive_syntax.py` provides non-executing, source-spanned operator preflight for `&&`, `? :`, `=>`, `.map(`, `==`, `!=`. It tracks quote escapes and matching expression delimiters; rejects strict JS comparisons, unsupported template control directives, async arrows and unclosed quoted/delimiter inputs with `MarkupSyntaxError` filename/line/column. It intentionally neither parses nested JSX completely nor emits VNodes or Python AST. `tests/test_expressive_markup_syntax.py` exercises 12 grammar/isolation cases; existing M4A explicit-scope and current M4B lexical transformation remain unchanged. Source and test routes are connected to `scripts/ci/impact.py` with an exact router test and executable core workflow command.

**Remaining before G1 CLOSE:** define and implement a full expression AST/grammar with nested JSX structural parsing, operator precedence and right-associative ternaries; validate narrow `.map` callback parameter grammar, legal arrow parameter/body shape and lexical name resolution boundaries; complete accurate markup-to-Python source spans and unsupported diagnostics for malformed nested branches; test attribute-expression containment and additional M4A negative cases. The current lexical token preflight is an initial contract foundation **not a completed grammar compiler**. No new F5 public runtime operations exist yet, so public census new-operation receipts are not applicable for this increment; revisit at G2–G4 when interactions ship.

**Gate F5-G1: IN PROGRESS.** No work on M8/F6, Qyro CLI, or Qyro Engine.


## Quoted-literal attribute grammar — CERTIFIED (2026-10-14)

**Owner decision:** Literal values in PSX Markup must be quoted (`<Flex gap="12" />`); braces are reserved for lexical references or F5 compiler-recognized expressive syntax. Numeric-braced static attributes (`gap={12}`, `padding={50}`) now deterministically fail with source-spanned `MarkupSyntaxError`. `gap={spacing}` still resolves only a supplied M4A mapping name or an existing M4B Python lexical binding; missing names fail rather than dynamically evaluating expressions.

**Implementation:** `psx/markup/parser.py` rejects numeric-braced literals. `psx/markup/compile.py` converts quoted, unitless numeric strings *only for known numeric/length-related props*, before all child/content policy paths; unit-bearing CSS-like values remain strings and text props stay strings. Numeric GridItem `span` and `offset`, Flex metadata, and native widget child metadata retain their typed numerical contract. This is deliberately not an `eval()`/`exec()` feature or frame introspection.

**Test migration:** existing positive fixtures for Flex, Grid, GridItem, CSS metadata and live Qt/Tk/Kivy markup were migrated from `{number}` to `"number"`, without changing geometry expectations or weakening negative tests. `tests/test_expressive_markup_syntax.py` additionally rejects braced numeric forms, confirms quoted numeric typing and explicit-scope missing-name failure, and characterizes static M4B source transformation.

**Certified immutable implementation SHA:** `c98af793417bfda905dbb170810ef76505a338f2`; [Native layout selective validation #38609247155](https://github.com/Neuri-AI/PSX/actions/runs/38609247155) **SUCCESS**, **14/14 executed jobs succeeded** including the mandatory conclusion. Rust differential, native-wheel, SFLE geometry and Chromium oracle jobs were impact-skipped and are not reported as executed. This is a scoped grammar/typing regression certificate, not G1 completion.

**Current gate:** F5-G1 **IN PROGRESS**; full grammar AST and expressive compilation remain future increments. No changes to M8/F6, Qyro CLI or Engine.


## Expressive syntax grammar and AST — G1 CLOSED (2026-10-14)

**Single immutable implementation SHA:** `842719ace30a9cf8acf9b900ef6b404a88532503`. **Selected CI:** [Native layout selective validation #38611373011](https://github.com/Neuri-AI/PSX/actions/runs/38611373011), **SUCCESS**: **14/14 jobs that executed succeeded**, including mandatory public evidence aggregation and required conclusion; Rust/Chromium/native-wheel/SFLE jobs excluded as impact-inapplicable, not asserted executed. Core tests: **575 passed plus 17 subtests passed**, public core certification **757 passed**. Qt (all four bindings), Kivy, Tkinter and Headless affected jobs succeeded. **Draft PR:** [#25](https://github.com/Neuri-AI/PSX/pull/25). No PR merge is implied.

**Implementation:** `psx/markup/expressive_ast.py` defines a non-executing, typed, location-bearing AST for literals, lexical names, member access, calls, comparisons, conditional AND, right-associative ternary, zero/one-argument arrow, statically recognized one-item `.map()`, JSX elements and fragments. Nested JSX tags, child interpolations, expression-valued attributes, nested conditional expressions and source coordinates are parsed without executing user code, using neither `eval`, `exec` nor `ast.literal_eval`. String escapes and scalar numbers are decoded by explicitly bounded grammar routines, not a dynamic interpreter.

**Normative operator precedence:** grouped `(...)` and member/call/`.map` postfix bind most tightly; `==`/`!=` bind more tightly than left-associative `&&`; conditional `? :` is weaker and right-associative; arrow callback parameters `()` or `(name)` bind to an expression body. JSX element parsing is recursive. The `.map` callback is exactly one parenthesized positional item parameter and expression body; mapped JSX root elements must carry a `key` attribute. Indexed `(item, index)`, destructuring, blocks and async arrows are not part of this G1 grammar. Quoted values are required for literal JSX props; `{12}` in an attribute is rejected.

**Safety/negative proof:** Unsupported `===`/`!==`, unmatched delimiters, malformed JSX closing tags, invalid `.map` signatures, missing map keys, braced attribute literals, async syntax and M4A attempts to execute expressive expressions fail closed with source-spanned errors. Existing M4A explicit-scope and M4B baseline regression tests remain GREEN. `tests/test_expressive_markup_syntax.py` tests the actual AST types and nested parse trees, rather than merely token presence. CI impact router selects core and Headless for new markup files; core workflow explicitly runs grammar tests.

**Public census applicability:** G1 exposes **no new public component, property, event or method**; it adds an internal syntax-only AST. Therefore no new code-derived public operation receipt is applicable yet. Earlier Grid/GridItem census receipts remain independent; F5 public runtime behavior must receive its own executed receipts in G2–G5.

**Final G1 decision: CLOSED** for grammar, source spans and M4A isolation. **This does NOT imply expressive conditional / `.map` / arrow rendering runs in `psx()` yet.** The new syntax parser intentionally does not lower AST to Python code or VNodes; **G2–G4 own static lowering and runtime behavior**, including exact conditional falsy normalization, arrow invocation and key-preserving reconciliation. M8 remains deferred to F6. G2 is the next stage; G1 source/workflow SHA above remains the technical certificate even after documentation-only commits.
