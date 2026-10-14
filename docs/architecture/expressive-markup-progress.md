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
| Scope safety | Authored static M4B templates only | PSX Runtime external/dynamic input remains restricted |
| Phase exclusion | M8 postponed to F6 | No Qyro CLI/Engine changes in F5 |

## Baseline architecture (to preserve)

- `psx/markup/lexer.py`, `parser.py` and `ast.py`: existing PSX Runtime restricted reference grammar. Explicit-scope templates must not gain arbitrary Python execution.
- `psx/markup/transform.py`: M4B static lexical transform; generated Python AST captures caller lexical bindings, retains source mapping, and keeps authored code intact.
- `psx/markup/compile.py`: templates resolve registered constructors, produce existing VNodes/Fragments and keep safe PSX Runtime compilation separate from statically authored expressions.
- `psx/core/reconcile.py`: keyed identity, component hook ordering, native ownership and renderer scheduling remain authoritative. No new layout engine or widget lifecycle rules.

## G1 acceptance matrix (all initially pending)

| Case | Required observation | Evidence |
| --- | --- | --- |
| Lexical precedence | `==`/`!=`, grouping, `&&`, ternary, arrow and `.map` parse deterministically | Pending test |
| Conditional nodes | Truthy/falsy and zero semantics defined separately from text interpolation | Pending test |
| Ternaries | Right-associativity, nested markup branches, no eager execution | Pending test |
| Declarative mapping | Compiler-only `.map`, finite iterable and stable key requirements | Pending test |
| Arrow closure | Zero/one argument; syntax errors and lexical capture preserved | Pending test |
| PSX Runtime isolation | Dynamic untrusted strings cannot invoke new expression paths | Pending test |
| Source mapping | Diagnostics point to original markup span and filename | Pending test |
| Unknown syntax | `===`, `!==`, `{#if}`, JS block/async arrows rejected clearly | Pending test |
| Existing compatibility | Current `psx()` PSX Runtime and M4B fixtures stay green | Pending test |
| CI routing | Compiler/parser/tests select affected core, Headless and any native consumers through `scripts/ci/impact.py` | Pending test |
| Public census | New public interactions have reviewed executed receipts or documented nonapplicability | Pending review |
| Immutable CI | Selected jobs succeed on the exact code SHA of the new grammar implementation | Pending run |

## Technical decisions to finalize during G1

1. **Grammar containment:** expressive syntax is accepted only by the M4B static lexical compiler, never implicitly by `compile_template` on runtime/untrusted PSX Runtime strings.
2. **Parser precedence:** parenthesized expressions are explicit; `&&` binds more tightly than `? :`; ternaries nest right-to-left. Python `==`/`!=` are comparisons, not strict JavaScript equality.
3. **Result normalization:** conditional absent output contributes zero children, while normal literal text interpolation keeps its historical behavior. Mapping output requires stable keys. Clearly diagnose invalid result categories; never silently coerce nested structures into text.
4. **No hooks inside conditional expression bodies:** state hooks remain in mounted components and keep their unconditional invocation contract.
5. **Static compilation only:** generated callable and iteration logic derives from validated syntax into ordinary Python AST, not `eval`, arbitrary exec or frame capture.
6. **No removed builders:** example syntax must use current registered Velto components. Legacy `Row`/`Column` are not public after F3.

## Next engineering increments

A. Extend the grammar AST model and lexer/parser specification with parser fixtures plus failure spans (syntax only).  
B. Add source-transform fixtures demonstrating correct binding names and safe Python AST generation, with PSX Runtime isolation.  
C. Verify change-router selection and public-census applicability; execute relevant CI and record an immutable code SHA.

**State:** specification groundwork recorded; no new parser behavior is claimed as shipped or certified.

## Literal-versus-reference grammar clarification (2026-10-14)

The owner clarified that `<Flex gap="12" />` is the approved literal syntax; numeric `gap={12}` must fail because braces are reserved for named references/expressions. The parser's old numeric-brace exception has been removed. Quoted integers use the existing component property coercion, preserving previously supported VNode values; unknown `{name}` continues to fail through PSX Runtime explicit-scope lookup or M4B lexical lookup with source coordinates. This is a behavior-changing parser correction with accompanying tests and CI regression verification. No dynamic `eval` or frame lookup is added. **G1 remains IN PROGRESS until the full expressive AST is implemented.**

## First executable grammar increment — CERTIFIED, G1 STILL OPEN (2026-10-14)

**Immutable implementation SHA:** `949d45d0d252dec4fcc108c6644322352380eff3`. **Required native selective CI:** https://github.com/Neuri-AI/PSX/actions/runs/38606480969 — SUCCESS (14/14 executed jobs, including final mandatory conclusion); four unrelated Rust/Chromium/SFLE/wheel jobs impact-skipped and are **not** represented as executed. PR: https://github.com/Neuri-AI/PSX/pull/25 (draft, targeting `develop`). CI core job reports **558 passed** plus 5 passed subtests including new grammar fixtures; public core suite **757 passed**. Legacy scoped public census Grid/GridItem **62/62** and native Grid/GridItem **150/150** executed unchanged; these **are not receipts for unshipped F5 interactions**.

**Implemented:** `psx/markup/expressive_syntax.py` provides non-executing, source-spanned operator preflight for `&&`, `? :`, `=>`, `.map(`, `==`, `!=`. It tracks quote escapes and matching expression delimiters; rejects strict JS comparisons, unsupported template control directives, async arrows and unclosed quoted/delimiter inputs with `MarkupSyntaxError` filename/line/column. It intentionally neither parses nested JSX completely nor emits VNodes or Python AST. `tests/test_expressive_markup_syntax.py` exercises 12 grammar/isolation cases; existing PSX Runtime explicit-scope and current M4B lexical transformation remain unchanged. Source and test routes are connected to `scripts/ci/impact.py` with an exact router test and executable core workflow command.

**Remaining before G1 CLOSE:** define and implement a full expression AST/grammar with nested JSX structural parsing, operator precedence and right-associative ternaries; validate narrow `.map` callback parameter grammar, legal arrow parameter/body shape and lexical name resolution boundaries; complete accurate markup-to-Python source spans and unsupported diagnostics for malformed nested branches; test attribute-expression containment and additional PSX Runtime negative cases. The current lexical token preflight is an initial contract foundation **not a completed grammar compiler**. No new F5 public runtime operations exist yet, so public census new-operation receipts are not applicable for this increment; revisit at G2–G4 when interactions ship.

**Gate F5-G1: IN PROGRESS.** No work on M8/F6, Qyro CLI, or Qyro Engine.


## Quoted-literal attribute grammar — CERTIFIED (2026-10-14)

**Owner decision:** Literal values in PSX Markup must be quoted (`<Flex gap="12" />`); braces are reserved for lexical references or F5 compiler-recognized expressive syntax. Numeric-braced static attributes (`gap={12}`, `padding={50}`) now deterministically fail with source-spanned `MarkupSyntaxError`. `gap={spacing}` still resolves only a supplied PSX Runtime mapping name or an existing M4B Python lexical binding; missing names fail rather than dynamically evaluating expressions.

**Implementation:** `psx/markup/parser.py` rejects numeric-braced literals. `psx/markup/compile.py` converts quoted, unitless numeric strings *only for known numeric/length-related props*, before all child/content policy paths; unit-bearing CSS-like values remain strings and text props stay strings. Numeric GridItem `span` and `offset`, Flex metadata, and native widget child metadata retain their typed numerical contract. This is deliberately not an `eval()`/`exec()` feature or frame introspection.

**Test migration:** existing positive fixtures for Flex, Grid, GridItem, CSS metadata and live Qt/Tk/Kivy markup were migrated from `{number}` to `"number"`, without changing geometry expectations or weakening negative tests. `tests/test_expressive_markup_syntax.py` additionally rejects braced numeric forms, confirms quoted numeric typing and explicit-scope missing-name failure, and characterizes static M4B source transformation.

**Certified immutable implementation SHA:** `c98af793417bfda905dbb170810ef76505a338f2`; [Native layout selective validation #38609247155](https://github.com/Neuri-AI/PSX/actions/runs/38609247155) **SUCCESS**, **14/14 executed jobs succeeded** including the mandatory conclusion. Rust differential, native-wheel, SFLE geometry and Chromium oracle jobs were impact-skipped and are not reported as executed. This is a scoped grammar/typing regression certificate, not G1 completion.

**Current gate:** F5-G1 **IN PROGRESS**; full grammar AST and expressive compilation remain future increments. No changes to M8/F6, Qyro CLI or Engine.


## Expressive syntax grammar and AST — G1 CLOSED (2026-10-14)

**Single immutable implementation SHA:** `842719ace30a9cf8acf9b900ef6b404a88532503`. **Selected CI:** [Native layout selective validation #38611373011](https://github.com/Neuri-AI/PSX/actions/runs/38611373011), **SUCCESS**: **14/14 jobs that executed succeeded**, including mandatory public evidence aggregation and required conclusion; Rust/Chromium/native-wheel/SFLE jobs excluded as impact-inapplicable, not asserted executed. Core tests: **575 passed plus 17 subtests passed**, public core certification **757 passed**. Qt (all four bindings), Kivy, Tkinter and Headless affected jobs succeeded. **Draft PR:** [#25](https://github.com/Neuri-AI/PSX/pull/25). No PR merge is implied.

**Implementation:** `psx/markup/expressive_ast.py` defines a non-executing, typed, location-bearing AST for literals, lexical names, member access, calls, comparisons, conditional AND, right-associative ternary, zero/one-argument arrow, statically recognized one-item `.map()`, JSX elements and fragments. Nested JSX tags, child interpolations, expression-valued attributes, nested conditional expressions and source coordinates are parsed without executing user code, using neither `eval`, `exec` nor `ast.literal_eval`. String escapes and scalar numbers are decoded by explicitly bounded grammar routines, not a dynamic interpreter.

**Normative operator precedence:** grouped `(...)` and member/call/`.map` postfix bind most tightly; `==`/`!=` bind more tightly than left-associative `&&`; conditional `? :` is weaker and right-associative; arrow callback parameters `()` or `(name)` bind to an expression body. JSX element parsing is recursive. The `.map` callback is exactly one parenthesized positional item parameter and expression body; mapped JSX root elements must carry a `key` attribute. Indexed `(item, index)`, destructuring, blocks and async arrows are not part of this G1 grammar. Quoted values are required for literal JSX props; `{12}` in an attribute is rejected.

**Safety/negative proof:** Unsupported `===`/`!==`, unmatched delimiters, malformed JSX closing tags, invalid `.map` signatures, missing map keys, braced attribute literals, async syntax and PSX Runtime attempts to execute expressive expressions fail closed with source-spanned errors. Existing PSX Runtime explicit-scope and M4B baseline regression tests remain GREEN. `tests/test_expressive_markup_syntax.py` tests the actual AST types and nested parse trees, rather than merely token presence. CI impact router selects core and Headless for new markup files; core workflow explicitly runs grammar tests.

**Public census applicability:** G1 exposes **no new public component, property, event or method**; it adds an internal syntax-only AST. Therefore no new code-derived public operation receipt is applicable yet. Earlier Grid/GridItem census receipts remain independent; F5 public runtime behavior must receive its own executed receipts in G2–G5.

**Final G1 decision: CLOSED** for grammar, source spans and PSX Runtime isolation. **This does NOT imply expressive conditional / `.map` / arrow rendering runs in `psx()` yet.** The new syntax parser intentionally does not lower AST to Python code or VNodes; **G2–G4 own static lowering and runtime behavior**, including exact conditional falsy normalization, arrow invocation and key-preserving reconciliation. M8 remains deferred to F6. G2 is the next stage; G1 source/workflow SHA above remains the technical certificate even after documentation-only commits.


## F5-G2 — Conditional rendering and static lowering: CLOSED (2026-10-14)

**Technical code SHA:** `a8515b392267c812f013b3324c4a40e1b9f94865`. **Selected native CI:** [GitHub Actions #38614587872](https://github.com/Neuri-AI/PSX/actions/runs/38614587872) — SUCCESS: **14/14 executed jobs**, including core, Headless, Qt (four bindings), Kivy, Tkinter, mandatory census aggregator and required final conclusion. Impact-skipped Rust, Chromium, SFLE geometry and native-wheel jobs are not counted as executed. Core reported **589 passing tests + 19 passing subtests**; existing public core census **757 passing tests**. This gate's code SHA remains the certification reference regardless of later docs-only commits.

**Implementation:** `psx/markup/expressive_lower.py` lowers G1's source-spanned syntax AST to ordinary Python `ast.IfExp` and `ast.Compare` nodes and typed callable/element construction. `psx/markup/expressive_runtime.py` constructs VNodes via the registered portable component factories and existing prop coercion, normalizes conditional false/zero/empty results to zero children, enforces text-only/child policy, and turns missing lexical names into source-spanned `MarkupSyntaxError`. `psx/markup/transform.py` only activates G2 for conditional operators **within actual markup braces**, preserving static quoted/textual `?` or `&&`, pre-existing M4B source templates and PSX Runtime's restricted explicit-scope parser. No interpreter, JavaScript runtime, `eval`, `exec` or frame inspection has been introduced in production code.

**Executed acceptance:** `tests/test_expressive_conditional_rendering.py` includes truthy/falsy `&&` including zero, Python equality/inequality, nested right-associative ternary selection, inactive-branch nonexecution, missing lexical-name diagnostic, PSX Runtime rejection, safety of literal question/ampersand strings, numeric text interpolation, source-map reference coordinates, invalid content policy, fail-closed future `.map` and arrow grammar, and mounted SFLE Headless event-triggered toggling that preserves parent widget identity. Routing was added to `scripts/ci/impact.py`, `tests/test_ci_impact.py` and actual core/Headless workflow commands.

**Public census applicability review:** F5-G2 changes the authored M4B expression grammar and the VNode composition produced by existing component constructors. It does **not** register new props, events, methods, components or native widget interactions. The existing component-derived census remains required and passed without fabricated new native receipts; the new language behavior is directly verified by executable compiler/Headless tests in required jobs. F5-G3–G5 must separately assess any newly published component/method/interaction combinations and add the corresponding code-derived census cells/receipts when applicable. The event `Button.on_click` used for lifecycle verification is already part of the existing public census, not a newly declared event.

**Gate boundary:** `&&` and `? :` conditional markup are now executable with M4B's static source transform, but `.map()` lowering remains G3 and arrow function compilation remains G4. PSX Runtime strings cannot execute expressive expressions, nor are Qyro CLI, Engine or postponed F6/M8 in scope. **F5 progress: 2/6 gates CLOSED**. PR [#26](https://github.com/Neuri-AI/PSX/pull/26) remains unmerged and in draft review; technical gate closure does not imply PR merger, alpha publication or deploy.


## F5-G3 — Declarative list rendering (implementation in review)

**Development branch:** `feature/expressive-declarative-lists`. **PR:** [#27](https://github.com/Neuri-AI/PSX/pull/27) (draft, targeting develop). Base implementation incorporates G2 in-progress PR #26; neither PR is implied merged.

**Implemented in this increment:**
- M4B statically lowers `items.map((item) => <Text key={item.id} />)` into an ordinary Python lexical lambda plus an explicit runtime list-materialization function; the transformation does not invoke a Python `list.map` method, use `eval`, `exec` or frame inspection.
- Runtime materializes ordered VNodes, rejects noniterable sources, non-VNode items, missing/invalid keys and duplicate keys before attempting native mounting. Nested maps inherit independent Python lexical scopes.
- Existing reconciler remains responsible for keyed insert/delete/move and native identity; no alternative reconciliation engine is introduced.
- `tests/test_declarative_list_rendering.py` covers empty, ordering, insert, removal, nested lists, lexical captures, conditional maps, invalid keys and Headless keyed identity; `scripts/ci/impact.py`, routing regression and executable native-layout core/Headless jobs include the tests.

**Acceptance still required:** certifying required GitHub Actions jobs on an immutable **code SHA** and reviewing adversarial situations (conditional JSX branches returning keys, nested fragment keys, duplicate keys across separate maps, generator errors and rollback). G3's acceptance was subsequently evidenced by the immutable-SHA certification below; technical gate CLOSED.

**F5 gate count:** G1 and G2 CLOSED; G3-G6 remain (four gates including G3). M8/F6 not part of this work.

### G3 adversarial validation increment (2026-10-14)

**Code SHA:** `7628a4d2f0aac93ac3c4e38530da5ac7e3434882`. **CI run:** [Native layout selective validation #38618906346](https://github.com/Neuri-AI/PSX/actions/runs/38618906346). The new CI run must finish successfully on this exact code SHA before G3 can close.

The previously missing executable cases were added to `tests/test_declarative_list_rendering.py`: both keyed branches of mapped conditional JSX; failure of an unkeyed alternate branch; rejection of an unkeyed mapped fragment; generator exception after yielding an item without changing the previously mounted native tree; and duplicate-key failure after partial generator consumption without native commit. Existing sibling key collision and stable Headless reorder identity cases remain present.

**Normalization decision:** direct mapped items must produce keyed VNodes, or absent conditional nodes; an unkeyed fragment returned as the mapped root is rejected. Nested mapped trees can use keyed container elements whose children are independently validated. An exception raised while materializing the list propagates before `Reconciler.render` is called, preserving the prior mounted tree. These are G3 test obligations, not new public props/events/methods; source-derived public census remains unchanged. Broader reconciliation rollback for native failures belongs to G5.

**Status:** G3 IN PROGRESS while the new SHA's selected CI jobs run. G4 must not be marked started on the basis of the prior green SHA alone.

## F5-G3 — Technical gate CLOSED (2026-10-14)

**Immutable implementation SHA:** `7628a4d2f0aac93ac3c4e38530da5ac7e3434882`.
**Certification:** [Native layout selective validation #38618906346](https://github.com/Neuri-AI/PSX/actions/runs/38618906346), latest attempt (rerun failed/cancelled jobs) **SUCCESS**, including the mandatory final conclusion. The initial attempt was interrupted when a later documentation-only commit was pushed; its cancelled job is not counted as a pass. The subsequent documentation-only run #38618977192 was green but skipped product suites and **is not** the certification basis.

**Executed verification:** Core and registry **604 passed + 23 subtests passed**, public core census **757 passed**, Headless **113 passed, 8 skipped + 6 subtests passed**. Required final CI conclusion **SUCCESS**. New public event/prop/method operations: **none**; the existing source-derived core census ran and reported 1716 executed receipt passes and zero failures, while the separate selective public evidence aggregate job was impact-skipped, not misreported as executed. The Headless job also completed its existing public native receipt collection.

**Coverage:** ordered, empty, inserted, removed, reordered, nested and conditional mapped elements; lexical binding; generated iterable consumption; strict keys and duplicate rejection; sibling-map collisions at reconciliation; per-key native Headless handle identity; conditional keyed/unkeyed branches; unkeyed fragment rejection; generator exception and late duplicate failure without committing the proposed tree. G3 stays on the existing reconciler and static M4B compiler; no dynamic Python source evaluator or PSX Runtime escape is introduced.

**Disposition:** **F5-G3 CLOSED (technical gate)**. G1, G2, G3 CLOSED = **3/6**. G4 (arrow callbacks) next; G5, G6 pending. PR #27 remains in draft unless independently changed or merged. This is a scoped technical certificate, **not** the all-backend integral F5-G6 certificate or owner signoff.

## F5-G4 — Deferred lexical arrow callbacks (implementation in review, 2026-10-14)

**Branch:** `feature/expressive-arrow-callbacks`. **Draft PR:** [#28](https://github.com/Neuri-AI/PSX/pull/28), targeting `develop`, stacked on the still-unmerged G3 branch.

**Implemented:** `psx/markup/expressive_lower.py` lowers owner-approved zero/one-positional-parameter `Arrow` expression AST to a native Python `ast.Lambda`; the body remains deferred and resolves lexical names when invoked. `psx/markup/transform.py` activates M4B static lowering for arrow tokens inside JSX expression braces. No production `eval`, `exec`, general JS interpreter, or frame inspection is introduced.

**Regression fixtures:** `tests/test_arrow_callback_rendering.py` covers no eager invocation, zero/one argument callbacks, item-specific closures inside keyed maps, native-like Headless event invocation and rebinding, unsupported two-parameter signatures and PSX Runtime explicit-scope isolation. An old G2 fixture that explicitly rejected all arrows now checks invalid two-parameter syntax rather than contradicting the approved G4 feature. `scripts/ci/impact.py`, `tests/test_ci_impact.py`, and executable core/Headless workflow commands include G4 fixtures.

**Acceptance still outstanding:** CI green on immutable code SHA, native Qt/Kivy/Tkinter event evidence, disabled/rebind/teardown tests and lifecycle adversarial cases. Review hook and source-map error boundaries; add executed public census cells only if public interactions actually expand. **G4 IN PROGRESS**, **NOT CLOSED**. No G5/G6 or deferred F6/M8 work is claimed.

## F5-G4 — Technical certification (2026-10-14)

**Code SHA:** `33ef70c7059aa7d4cf69c5b2cd1e8354b5338ea0`. **GitHub Actions:** [Native layout selective validation #38624475696](https://github.com/Neuri-AI/PSX/actions/runs/38624475696) — **SUCCESS**, including Core, deterministic Headless, Qt, Kivy, Tkinter, all four Qt parity bindings, change-router regression, executed public evidence aggregation, and mandatory final conclusion. Rust, Chromium, wheel and unrelated SFLE jobs were impact-skipped, not reported as executed.

**Corrections and contract boundaries:** A mounted arrow callback test uses the required native Cinnamon `Flex` root, retaining real Headless event slot rebinding checks. Added event slot teardown test verifies callbacks become inert upon unmount. An adversarial `disabled` attribute test documents the actual current public `Button` contract: `disabled` is rejected as an unsupported prop without invoking the arrow body; it is **not** claimed as an implemented feature. Any future public disabled behavior needs its own component specification, implementation and tests, independently of arrows.

**Disposition:** G4 arrow static lowering, deferred invocation, lexical capture, keyed-list closure isolation, rebinding and teardown **technically CLOSED** on the immutable code SHA. **G1-G4 = 4/6 CLOSED**; G5 cross-feature lifecycle/security and G6 final integral certificate remain. PR #28 is still a draft and no merge is implied. No F6/M8 work.

## F5-G5 — Composition/lifecycle/security technical acceptance (2026-10-14)

**Immutable code SHA:** `4f22e6208c61fb33e1b126e113256ca7b4f02562`. **Selected CI certificate:** [Native layout selective validation #38625213232](https://github.com/Neuri-AI/PSX/actions/runs/38625213232) — SUCCESS with Core, Headless, Qt, Kivy, Tkinter and all four Qt binding parity jobs, source-derived public behavior evidence aggregate and mandatory final conclusion. Relevant intelligent-router regression SUCCESS; unrelated Rust/Chromium/wheel/SFLE suites impact-skipped, not represented as executed.

**Functional additions:** `tests/test_expressive_composition_security.py` covers combined ternary + keyed map + deferred per-item arrow, stable native-like Headless identities after reordering, inactive branch non-evaluation, duplicate-key error before reconciliation mutation, PSX Runtime restricted-scope isolation, rejection of JavaScript strict equality, and source-spanned rejection of Python private/introspection member access. `psx/markup/expressive_runtime.py` now rejects attributes prefixed with underscore in compiled lexical member lookup, including mappings. G1–G4 executable tests remain selected by core/Headless. **Core: 619 passed + 23 subtests; core public census: 757 passed and 1716 executed receipt passes (0 failed). Headless: 128 passed, 8 skipped + 6 subtests; Headless public native receipt collection: 228 executed passes (0 failed).**

**Scope:** No new component/prop/event/method was registered. The newly recognized rejection of private lexical attributes is an authored M4B expression guard, not a native component surface or census cell. Public census was actually executed through the existing producers. No independent layout or reconciliation engine; PSX Runtime untrusted strings remain restricted. **F5-G5 technically CLOSED.**

## F5-G6 — Integral technical CI certificate / acceptance boundary (2026-10-14)

**Implementation SHA:** `4f22e6208c61fb33e1b126e113256ca7b4f02562`. **Required GitHub Actions:** [#38625213232](https://github.com/Neuri-AI/PSX/actions/runs/38625213232), **14/14 applicable jobs SUCCESS**, mandatory evidence aggregator and final conclusion SUCCESS. Four nonapplicable suites were skipped by impact classification. The run's checkout can use a PR merge-test SHA; the immutable implementation reference is the exact head SHA listed here.

**Verified:** grammar, static M4B lowering, lexical closure callbacks, keys, composition, Headless native-like lifecycle, PSX Runtime isolation, source diagnostics, registered component validation, cross-backend existing native regressions and source-derived public census. No M8/F6 feature has been implemented. **Technical CI acceptance PASS**.

**Remaining owner authorization:** The normative G6 contract separately requires **explicit owner signoff**. This ledger records technical evidence but **does not impersonate owner approval or claim PR merge**. Until that explicit approval, G6 is **TECHNICALLY CERTIFIED / AWAITING OWNER SIGNOFF**, not CLOSED under the contract.

## F5-G6 — Post-merge final review and owner-directed closure record (2026-10-14)

**Provenance:** PR [#29](https://github.com/Neuri-AI/PSX/pull/29) was merged into `develop` at merge SHA `7cea5e36f7949829711d194b158e5800046cc8c8`. Its source head `cf49b67b7201cb2e25bc0525cdeb1becebce23b3` contained only documentation changes after the certified implementation SHA `4f22e6208c61fb33e1b126e113256ca7b4f02562`. The branch was removed by the owner. The exact implementation's [selected CI run #38625213232](https://github.com/Neuri-AI/PSX/actions/runs/38625213232) completed SUCCESS including the required conclusion and executed public census aggregate; 14 applicable jobs succeeded, four unrelated suites were correctly impact-skipped. CI run references above are tied to the certified PR implementation, not asserted to be a fresh PR event on the post-merge SHA.

**Owner action:** The project owner reported merging PR #29 and explicitly instructed completion of G6. This is recorded as an owner-directed gate acceptance **conditional upon the documented G6 evidence**. No approval of unrelated features, public APIs, F6 or M8 is inferred.

**Final disposition:** The G6 acceptance checklist is met by the recorded immutable implementation SHA, cross-backend execution and receipt evidence plus the owner-directed closeout. **F5-G6 CLOSED; F5 G1–G6 CLOSED (6/6).** The closure is a technical/roadmap milestone, not a claim that every possible operating-system and Python-version combination was run in CI, or that a new version was published. The certified `disabled` rejection remains as documented. Further surface expansion is a separate approved workstream.
