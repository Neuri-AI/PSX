# SFLE F2 — Implementation plan and progress

> **Status:** F2 authorized on 2026-10-10. F2.0 blueprint and F2.1 typed
> contracts, strict tree validation, diagnostics, capability manifests and
> JSON-safe versioned exchange are committed on the feature branch.
> **F2.2 has started:** a CSS §9.7 single-line, resolved-size flex distribution
> kernel now exists in both Python and Rust source form. It is **not** wired
> to the engine protocol. No full Flexbox implementation, compiled Rust/PyO3
> extension, public Flex component, renderer migration or Chromium conformance
> claim exists yet.
>
> Binding architecture: [F1 final architecture](sfle-f1-final-architecture.md),
> [F1 component contracts](sfle-f1-contracts.md),
> [CSS box model and percentage rules](sfle-f1-box-model.md).

## 1. F2.0 — Technical card

| Field | Decision |
| --- | --- |
| Responsibility | Backend-neutral SFLE computation contract and incremental CSS Flexbox algorithm |
| Public component | Target: `Flex` only; existing `Row`/`Column` retired during authorized migration, without aliases |
| Child policy | `Flex` supports multiple direct VNodes; function component Flex items require one effective rendered root |
| Events | No new layout events |
| Portable props | Container props + `flex_*`, `align_self`, `order`, `layout_*` child metadata |
| Native integration | UI-thread measurement, immutable snapshots, native geometry adapters; detailed integration follows in F3 |
| Calculation | Pure, GUI-agnostic logic with one normalized input schema |
| Engine priority | Rust primary (PyO3 / maturin); equivalent Python fallback |
| Direction | Horizontal writing mode, both `ltr` and `rtl` |
| Validation | Closed props, typed lengths, feature-gated explicit errors |
| Lifecycle | Scheduler-coalesced dirty roots; apply only current-generation geometry |
| Layout owner | SFLE, not toolkit-specific Row/Column distribution |
| Scroll | Independent viewport, clipping, scrolling, events and offsets; explicit content layout boundary |
| No aliases | Row and Column remain in the repository until migration code is implemented and validated; no future public compatibility API |

### Backend mechanisms

| Backend | Measure intrinsic dimensions | Apply geometry | Native lifecycle |
| --- | --- | --- | --- |
| Qt (PySide/PyQt) | Qt size hints, text/font metrics, size policies on UI thread | Explicit native geometry | Existing PSX adapter |
| Kivy | Widget content metrics under constraints on UI thread | Convert SFLE top-left origin to Kivy coordinates | Existing PSX adapter |
| Tkinter | Requested widget/content sizes on Tk thread | Native placement from SFLE rectangles | Existing PSX adapter |
| Headless | Supplied deterministic intrinsic measurement snapshots | Serializable logical rectangles | No native widget |

Registration strategy: eventually declare the `Flex` primitive through
the canonical component registry/contract mechanism. Specialized renderer
adapters will handle native creation/measurement/commit while SFLE alone
performs distribution. Do **not** register `Row` or `Column` aliases after
migration. No registration is changed in this initial F2.1 skeleton.

## 2. Implementation stages and stop conditions

| Stage | Content | Completion condition |
| --- | --- | --- |
| F2.0 | Architecture blueprint, module boundaries and delivery order | Explicit engine/core/native ownership and supported target surface |
| F2.1 | Immutable lengths, strict ancestry, measurement/output models, stable diagnostics, capability manifest, v1 JSON-safe wire schema | Implemented in feature branch; execution/CI validation not yet performed |
| F2.2 | CSS Flexbox computation: Rust primary + parity-matched Python fallback | **In progress:** Python + Rust single-line resolved-size flexible-length math; engine integration and parity verification pending |
| F2.3 | Browser reference geometry + LTR/RTL conformance | Same line structure; geometry within 0.01 logical px pure with equivalent measurements |
| F2.4 | Inventory/plan migration of Row/Column/Scroll boundaries | No planned aliases; Scroll independent, native adapters retained |

**F2.1 contract decisions now encoded:** JSON-safe wire version 1,
typed PX/PERCENT/keyword lengths, pre-order tree with one root, strict parent
references and unique identities, typed input and output, immutable tuples,
stable error codes and a closed versioned feature manifest. Every current
engine feature is deliberately **disabled**, and the Python computation
placeholder throws an explicit unsupported-feature error.

**Still pending before declaring F2.1 production-verified:** execute import,
serialization round-trip and edge-case checks, agree Rust binding transport
details (JSON is the debug/reference interchange, not a performance ABI), and
review the intrinsic measurement protocol for text wrapping under changing
width constraints. This is not a completed CSS math engine.

## 3. Current added modules (F2.1 initial skeleton)

~~~text
psx/sfle/
    __init__.py     Internal contract re-exports (not PSX public Flex API)
    lengths.py      Immutable tagged CSS-like lengths and strict parsing
    model.py        AvailableSize, constraints, boxes, measured nodes,
                    layout tree snapshot, output model
    engine.py       LayoutEngine Protocol and explicit unimplemented fallback
    capabilities.py Closed feature manifest and wire schema version
    errors.py       Stable coded errors and unsupported capabilities
    wire.py         Strict, JSON-safe input/output schema conversion
    flex_math.py    CSS §9.7 single-line resolved-size sizing kernel (not an engine)
~~~

`PythonLayoutEngine.compute()` intentionally raises
`UnsupportedLayoutFeature` today. This preserves D-F1.9 (no silent
non-CSS geometry), and **does not count as a Python fallback
implementation**. The Rust primary extension is not yet present.

~~~mermaid
flowchart TD
    V["PSX VDOM (unchanged)"] --> C["Future SFLE coordinator"]
    C --> M["Future UI-thread intrinsic measurement"]
    M --> I["Validated LayoutInput v1 + typed wire schema"]
    I --> E["LayoutEngine protocol"]
    E --> R["Rust primary (planned F2.2)"]
    E --> P["Python fallback (planned F2.2)"]
    R --> O["LayoutResult v1"]
    P --> O
    O --> A["Future geometry adapters (F3)"]
~~~

## 4. F1 invariants to preserve

1. `Flex` will be the only public distribution component; do not ship
   `Row`/`Column` aliases or wrappers.
2. Preserve inert, validated flex metadata outside an effective Flex
   formatting context.
3. Preserve type distinctions between `auto`, `0`, percentages,
   `min-content`, `max-content`, `none` and indefinite constraints.
4. Percentage references depend on their CSS property and definite axis.
5. Native widget measurement and geometry commits must occur on UI thread;
   pure computation must never capture GUI handles or callbacks.
6. Keep horizontal LTR and RTL behavior in the first supported layout slice.
7. Keep Rust/Python capability and geometry parity and explicit unsupported
   feature failures; no best-effort approximation or silent backend switch
   on calculation failure.
8. `Scroll` remains separate and retains its viewport/interaction behavior.
9. Preserve keys, reconciliation identity, hooks, refs, event slots and focus
   where existing mounted-instance contracts permit.
10. Preserve approved numerical thresholds: <=0.01 logical px pure,
    <=1.0 logical px native, calibrable with a recorded fixture reference.

## 5. Risks and boundaries

- Releasing two separate mathematical algorithms without conformance fixtures
  could introduce Rust/Python drift. Treat the browser fixture corpus as
  shared and keep feature manifests synchronized.
- Typed `Length` is property-agnostic; a later shared style validator must
  reject property-invalid values (e.g. negative padding) *before* compute.
- `LayoutInput` is an internal Python snapshot prototype, not a finalized
  wire-ABI promise or zero-copy Rust representation.
- The current PSX package declares Python >=3.10,<3.14; the Rust wheel strategy
  must respect the **actual PSX support matrix** until separately updated.
- No native wheel dependency, import-time dependency, or new GUI toolkit
  requirement should be introduced before the fallback can truly execute.
- Current Row/Column source remains untouched at this stage; deleting it
  before Flex and adapters are usable would break the alpha runtime.

## 6. Developer-experience checkpoint

The planned developer-facing form is:

~~~xml
<Flex direction="row" gap={16} width="100%">
    <Text flex_grow={1}>Left</Text>
    <Flex direction="column" flex_grow={2} layout_min_width={0}>
        <Button>Continue</Button>
    </Flex>
</Flex>
~~~

This markup is **not runnable today**; it is shown only to maintain the
F1-approved target during F2 design and implementation. No PSX compiler or
component registration changes accompany this blueprint.

## 7. F2.1 — Contract refinement and serialization rules

~~~mermaid
flowchart TD
    A["VNode-facing style normalization (future)"] --> B["Typed Length + LayoutNode"]
    B --> C["LayoutInput validation: one root, parent-first, IDs unique"]
    C --> D["v1 wire encoding + schema/capability check"]
    D --> E["Pure LayoutEngine boundary"]
    E --> R["Rust implementation (next block)"]
    E --> P["Python fallback implementation (next block)"]
    R --> F["LayoutResult boxes + diagnostics"]
    P --> F
~~~

**Stable initial wire envelope:** `schema_version=1`,
`generation`, `writing_direction` (`ltr`|`rtl`),
`constraints`, `nodes`, and `measurements`. Styles are ordered pairs
of typed values; lengths serialize to `{"kind":"percent","value":0.5}` or
`{"kind":"auto","value":null}`. Percentages remain unresolved until layout.
Output includes matching schema/generation, ordered ID/box records and
diagnostic messages.

The wire decoder rejects unknown/missing fields, malformed numeric values,
non-finite values, duplicate JSON properties and structurally invalid
trees. It does not silently normalize unrecognized layout props or
unsupported CSS combinations; those belong to later shared style/capability
validation gates.

**Ancestry contract:** one effective root for non-empty snapshots,
parent-before-child node ordering, unique IDs and measurements referencing
existing nodes only. Ordered sibling identity is preserved in the input.

**Engine capability contract:** a versioned manifest declares the exact
CSS features available. Its initial contents are the empty feature set:
the current Python placeholder is not advertised as a functioning fallback,
and no Rust extension is loaded.

**Release note:** this block changes only internal `psx.sfle` modules.
`psx` public exports, native renderers, currently available Row/Column
and Scroll implementations remain untouched. No automated tests have been
added or run in this DX-first slice.

## 8. F2.2 — First pure computation slice: flexible main sizes

Two companion implementations have been added:

~~~text
psx/sfle/flex_math.py       Python CSS §9.7 resolved-size distribution
rust/sfle-core/Cargo.toml   Independent pure Rust crate declaration
rust/sfle-core/src/lib.rs   Rust CSS §9.7 counterpart (no PyO3 binding yet)
~~~

The algorithms accept an **already formed single flex line** with definite
container main size and already resolved content-box flex bases, hypothetical
main sizes, growth/shrink factors, numeric min/max constraints and numeric
inter-item gap. They implement the freezing loop, scaled shrink factors
(`flex_shrink * flex_basis`) and min/max violation handling. Their output
is a tuple/vector of resolved main content sizes, **not** a CSS box-layout
tree or native geometry.

~~~mermaid
flowchart TD
    A["CSS-normalized single line + definite main size"] --> B["Resolved bases / min-max / grow-shrink"]
    B --> P["Python flexible-length kernel"]
    B --> R["Rust flexible-length kernel"]
    P --> C["Content-box main-size vector"]
    R --> C
    C --> D["Next: line placement, box edges, cross-axis and LayoutResult"]
~~~

**Explicitly unsupported by this slice:** deriving intrinsic or percentage
flex basis, automatic minimum-size rules, padding/border/margin contribution,
auto margins, multiple lines, wrapping, alignment, box positioning,
replaced-element sizing and cyclic layout measurement. It must not be used
to claim CSS Flexbox layout support yet.

**Engine capability manifest remains empty** and
`PythonLayoutEngine.compute()` continues to reject every computation
request until all required features for an enabled path are conformant.
The native Rust crate currently has no PyO3/maturin entry point, binary
wheel or runtime loader. No automated tests were added or run and no
browser geometry comparison has been performed. Rust/Python numeric
parity remains a **required next verification**, not a completed fact.

### Immediate follow-on acceptance gates

1. Resolve and document how the main-size calculation receives the CSS
   content-box, border/padding, margins, automatic minimum and definite
   containing size from the normalized input.
2. Compare the Rust and Python numeric kernels using a shared set of
   hand-grounded CSS cases (including fractional factors and freeze cycles),
   then browser-reference fixtures before enabling any capability.
3. Extend line formation and physical box positioning with RTL and
   reverse-direction coordinate mapping; do not silently approximate
   unsupported cases.
4. Add a versioned Rust/PyO3 batch interface and deterministic load-time
   fallback only when the Python engine can compute the same advertised
   feature set.
