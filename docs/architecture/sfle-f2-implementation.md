# SFLE F2 — Implementation plan and progress

> **Status:** F2 authorized on 2026-10-10. F2.0 blueprint and F2.1 typed
> contracts, strict tree validation, diagnostics, capability manifests and
> JSON-safe versioned exchange are committed on the feature branch.
> **F2.2 has started:** a CSS §9.7 single-line, resolved-size flex distribution
> kernel and a resolved-line formation/placement kernel now exist in both
> Python and Rust source form. A restricted integrated resolved-size pipeline
> now connects those kernels and a separate used-box geometry helper exists.
> These paths are **not yet wired** to the engine protocol. No full Flexbox implementation, compiled Rust/PyO3
> extension, public Flex component, renderer migration or Chromium conformance
> claim exists yet.
>
> Binding architecture: [F1 final architecture](sfle-f1-final-architecture.md),
> [F1 component contracts](sfle-f1-contracts.md),
> [CSS box model and percentage rules](sfle-f1-box-model.md).

## F2.2 progress — numbered implementation subblocks

This is the tracked internal subdivision of **F2.2**, not a replacement for
the official F2.0–F2.4 phase structure. Status is updated after each delivery.

| Subblock | Deliverable | Progress |
| --- | --- | --- |
| F2.2.0 | Resolved flex math, line formation, LTR/RTL, fixed-edge CSS boxes | Implemented; focused CI passed |
| **F2.2.1** | **Intrinsic sizing and automatic main-axis minimums** | **Implemented; SFLE Rust + Python 3.10–3.13 CI passed (restricted scope)** |
| **F2.2.2** | **Percentage cycles, box sizing and sizing-edge contracts** | **Scoped resolved-input implementation complete; context-dependent cases explicitly deferred to F2.2.4** |
| **F2.2.3** | **Main/cross alignment, baseline, stretch and multi-line distribution** | **Scoped resolved-input acceptance: implemented in Python/Rust; first six Chromium border-box fixtures passed; native/orthogonal baseline constraints deferred to F2.2.4** |
| **F2.2.4** | **Recursive layout and constrained native measurement protocol** | **In progress: 5/8 internal subblocks scoped-accepted; F2.2.4.5 dependency/remeasurement protocol closed; geometry/native adapters/integration pending** |
| F2.2.5 | PyO3/maturin Rust-primary engine and Python fallback integration | Pending |
| F2.2.6 | Rust/Python parity corpus and core stabilization | Pending |

**Remaining subblocks:** three (F2.2.4–F2.2.6). Scoped F2.2.2/F2.2.3 acceptance does not imply full CSS conformance. Other pending stages:
F2.3 Chromium conformance and F2.4 migration planning.

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
| F2.2 | CSS Flexbox computation: Rust primary + parity-matched Python fallback | **In progress:** integrated restricted line/size/placement kernels in Python/Rust plus resolved box geometry in Python; parity and browser conformance unverified |
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
    line_layout.py  Order-aware line breaking and physical LTR/RTL placement
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

## 9. F2.2 — Resolved line formation and LTR/RTL placement

A second isolated pure-math slice has been added without claiming full
Flexbox support:

~~~text
psx/sfle/line_layout.py           Python resolved item / line placement
rust/sfle-core/src/line_layout.rs Rust equivalent data and algorithms
tests/sfle/test_line_layout.py    Declarative Python behavioral examples
~~~

Both kernels accept already-resolved, nonnegative *outer* item main/cross
sizes, a definite container size, numeric main/cross gaps, source order,
CSS `order`, and explicit horizontal writing direction (`ltr` or `rtl`).
They form flex lines by the order-modified sequence **before** shrink
distribution, and then translate main/cross directions into physical x/y.

~~~mermaid
flowchart TD
    A["Resolved hypothetical outer item sizes"] --> B["Stable order-modified item sequence"]
    B --> C["Greedy flex-line formation"]
    C --> D["Main sizes after flex distribution (separate kernel)"]
    D --> E["Physical coordinate mapping"]
    E --> F["LTR / RTL; row / column; reverse; wrap-reverse"]
    F --> G["Resolved outer rectangles + line IDs"]
~~~

**Important isolation:** The current API invokes placement directly on
resolved items; integration with the §9.7 length-resolution kernel is
**not implemented**. Existing fixture examples use already-resolved used
sizes. `nowrap` cannot accept multiple manually passed lines; an item
larger than its container may overflow without being silently resized.

**Covered contracts in source:** row, row-reverse, column, column-reverse;
LTR/RTL axis origins; `wrap` and `wrap-reverse` cross stacking; stable
`order` ties; gap between line items and between lines; deterministic
node IDs; invalid input rejection.

**Not yet supported:** aligning or stretching items, `align_content`,
auto margins, negative margins, padding/border/content-box conversion,
intrinsic/percentage sizes, min/max when forming lines, flex-line packing
after resolution, baseline metrics, nested layout traversal and scroll
content constraints. The line cross size is currently the maximum of
already-resolved item cross sizes; this is a narrow input contract, **not**
a substitute for the complete CSS multi-line cross-size algorithm.

### Verification status

Python tests and Rust unit tests were committed for axis direction and
line membership, but **neither suite has been executed against the GitHub
branch in this task**. Numeric parity versus Chromium is pending; the
0.01 logical-px acceptance threshold has **not** been certified.
There is no native PyO3 binding or wheel and `LayoutEngine.compute()`
continues to fail explicitly. The capability manifest must remain empty.

Next: execute both language test suites in CI, correct any discovered
cross-language divergence, connect sized lines to positioned boxes with
CSS box-model contributions, then expand the feature-gated semantic set.

## 10. F2.2 — Integrated resolved geometry and CSS used boxes

The earlier math kernels were independent. The following first integration
now connects them under **strict resolved-input preconditions**:

~~~text
psx/sfle/resolved_pipeline.py      Python integrated line/size/placement
rust/sfle-core/src/resolved_pipeline.rs
                                   Rust counterpart for the same restricted path
psx/sfle/box_geometry.py           Pure CSS used-box rect conversion
tests/sfle/test_resolved_pipeline.py
tests/sfle/test_box_geometry.py    Focused behavioral tests
~~~

The pipeline forms lines with the **hypothetical outer main sizes** in
stable CSS `order`, resolves each line's flexible main sizes through the
§9.7 kernel, then places resolved items in their LTR/RTL and reverse-axis
coordinates. The pipeline deliberately requires **zero padding, border
and margin** on its input items, so the mathematical flex base and used
outer main size are interchangeable for this limited slice.

The separate box geometry helper converts already-resolved, positioned
physical margin rectangles into margin/border/padding/content rectangles,
handling signed margins only when the resulting rectangles remain
representable. This helper does **not** yet feed measurements/edges back into
flex line fitting or minimum-size calculations. Conflating that conversion
with full CSS box-sizing would be incorrect.

~~~mermaid
flowchart TD
    A["Pre-normalized items: zero-edge boxes"] --> B["Order-aware hypothetical line formation"]
    B --> C["Per-line CSS §9.7 grow/shrink + clamps"]
    C --> D["LTR/RTL physical placement"]
    D --> E["Resolved intermediate rectangles"]
    F["Separate resolved margin/border/padding values"] --> G["Used-box geometry converter"]
    E -. "future integration with edge-aware flex algorithm" .-> G
    G --> H["Content / padding / border / margin rectangles"]
~~~

**Feature gate remains closed.** Until native/batched Rust binding,
edge-aware sizing, intrinsic and percentage resolution, alignment,
container cross-size distribution and browser-reference fixtures are
implemented, `LayoutEngine.compute()` must still reject requests. The
Python/Rust integrated kernels are internal and cannot be used to claim a
conformant full Flexbox engine.

### Validation follow-up

Python tests and Rust unit tests cover the restricted integrated
math, RTL, line wrapping, numeric flex allocation and used-box rectangle
conversions. The GitHub Actions run for commit
`090b2829ef096d08c987baaece95957c1f8d0a7c` **completed successfully**:
Rust core checks and Python 3.10, 3.11, 3.12, 3.13 all passed. The general
PSX alpha validation workflow on that commit also passed.

**What CI does not prove:** Rust/Python fixture-by-fixture numeric parity,
browser conformance within 0.01 logical CSS px, PyO3 packaging, or a complete
CSS box-model-aware algorithm. Those remain separate acceptance gates.

The next useful block should prioritize evaluating the CI outcomes and
then expanding edge-aware line fitting (including padding, border and
signed margins) without violating CSS auto-minimum and box-sizing rules.

## CI optimization: documentation-only changes

GitHub Actions now distinguishes **the latest PR synchronization delta**
from the full historical PR diff. This is important because a code-bearing
PR remains code-bearing in GitHub's ordinary `paths` filters even if the
latest commit only changes `docs/`.

- `.github/workflows/ci.yml`: push events ignore `docs/**`. On PR
  synchronization, a lightweight file-change job inspects the `before`/
  `after` commit range and skips the Python matrix, Qt offscreen suite
  and distribution build if only `docs/` changed.
- `.github/workflows/sfle-core.yml`: push triggers include SFLE Python,
  Rust, tests, its workflow and `pyproject.toml`. The lightweight PR
  change detector skips the Python/Rust suite when the latest synchronized
  changes do not affect these paths.
- A documentation-only PR update may still create a **small detector job**:
  GitHub's PR path filter examines the aggregate PR diff, not just the
  most recent commit. The expensive test jobs are skipped.
- PR opening or reopening still checks the overall diff; mixed code/docs
  updates always run relevant checks. Renamed files consider both previous
  and current paths. Large or unclassifiable diffs run checks rather than
  accidentally skipping them.

Workflow behavior is separate from SFLE layout conformance certification.

## 11. F2.2 — Resolved fixed edges in line sizing

The next restricted, renderer-neutral slice includes resolved physical
`margin`, `border` and `padding` in Flexbox line fitting and used-box
geometry, with matching Python/Rust implementations:

~~~text
psx/sfle/edge_pipeline.py          Edge-aware content-size resolution
rust/sfle-core/src/edge_pipeline.rs Rust counterpart, pure crate
tests/sfle/test_edge_pipeline.py   Python fixtures: growth, wrapping, RTL
~~~

**Normative preconditions** for this interim slice: `FlexBasis` values
represent pre-resolved *content-box* base/hypothetical/min/max lengths.
All four physical edge contributions are numeric and **nonnegative**;
auto/percentage values are **not** silently reduced to zero. The known
automatic minimum-size condition must already be expressed as a numeric
`min_size`. Intrinsic sizing and the generic `LayoutEngine.compute` remain
unsupported and are explicitly gated.

~~~mermaid
flowchart TD
    A["Resolved content sizes + fixed edges"] --> B["Hypothetical outer sizes"]
    B --> C["Order-aware flex line formation"]
    C --> D["Reserve fixed edges for each line"]
    D --> E["CSS §9.7 content grow/shrink"]
    E --> F["Recombine used outer item sizes"]
    F --> G["Physical LTR/RTL rectangle placement"]
    G --> H["Margin / border / padding / content boxes"]
~~~

For each line, usable content main space equals
`max(0, container_main_size - sum(fixed_outer_edges))`, and the existing
flex solver subsequently accounts for main-axis gaps. This lets fixed edges
consume real space rather than being ignored as in the initial zero-edge
pipeline. Overflow is preserved as a geometry result; it is not clipped
or presented as compliant in unsupported conditions.

**Deferred CSS semantics:** negative/automatic margins, CSS percentage
reference bases, automatic min-content sizing, native intrinsic measurement,
baseline and stretch alignment, multi-line cross-axis distribution, and
layout-tree recursion. In particular, the current signed-margin converter
is **not** an authorization to use negative margins in line fitting.

The pure Rust and Python edge-aware source was added along with Python and
Rust fixtures; numeric parity and Chromium conformity must still be
separately verified. Do not enable engine capability claims prematurely.

## 12. F2.2 — Property-aware CSS sizing (definiteness first)

The current slice adds a *property-aware* length resolver in both languages:

~~~text
psx/sfle/sizing.py              Python sizing properties and used/unresolved tags
rust/sfle-core/src/sizing.rs     Rust counterpart and tests
tests/sfle/test_sizing.py       Python percentage/definiteness/keyword tests
~~~

The resolver preserves `AUTO`, intrinsic keywords, `NONE`, and indefinite
percentages as distinct tagged results. It produces a numeric used size only
when the reference dimension is **definite**, including definite zero.
The three reference dimensions are provided explicitly, never inferred
from an untyped parent numeric width.

| Property group | Percent reference | Status |
| --- | --- | --- |
| Physical margin/padding (all four sides) | Containing block inline size | Definite references supported |
| `flex_basis` | Definite flex container main size | Definite references supported |
| Width/height and min/max | Corresponding containing block axis | Definite references supported |
| `gap` percentages | Depends on cyclic/intrinsic layout stage | Rejected explicitly |
| Border percentages | Not a supported CSS border-width value | Rejected explicitly |

A negative margin percentage is preserved as a signed used value;
negative padding, gap and sizing values are rejected. **This is a
resolution contract, not a complete flex item sizing algorithm.**
`min-content`, `max-content`, `fit-content` and `auto` stay unresolved:
the next computation layer must consult native intrinsic measurements,
CSS auto min-size and the specific property's formatting context instead
of fabricating numeric values. Indefinite percent `flex_basis` similarly
remains deferred; the complete Flexbox algorithm must apply the appropriate
content-based fallback in its correct sizing phase.

~~~mermaid
flowchart TD
    A["Tagged Length + property"] --> B["Select CSS reference axis"]
    B --> C{"Reference definite?"}
    C -->|Yes| D["Finite used logical px"]
    C -->|No| E["Tagged unresolved percent"]
    A --> F["AUTO / intrinsic / NONE"]
    F --> G["Deferred to measurement or sizing stage"]
    A --> H["Unsupported cyclic gap / invalid property value"]
    H --> I["Explicit diagnostic"]
~~~

Both Rust and Python expose this resolver as a **pure intermediate
operation**, not a complete `LayoutEngine`; the engine capability manifest
remains empty until its full supported path is conformant and verified.
The solver is **not yet connected** to edge-aware line sizing or native
measurement, and no runtime/native adapter/public component is modified.

### Validation gate

The initial CI execution caught a pytest collection issue because `request`
is reserved as a fixture name. The fixture was renamed and the subsequent
SFLE Actions run **38059494023** for commit `398bd59` passed all five
computational jobs: Rust core and Python 3.10, 3.11, 3.12 and 3.13.
Full browser geometry, replaced-element/aspect-ratio behavior, text
remeasurement and cross-language numerical fixture parity remain **pending**.

## 13. F2.2.1 — Intrinsic sizing and automatic minimums

First pure immutable sizing slice:

~~~text
psx/sfle/intrinsic.py             Python intrinsic flex basis and main min
rust/sfle-core/src/intrinsic.rs   Equivalent Rust calculation contracts
tests/sfle/test_intrinsic.py      Keyword, caps and scroll-aware tests
~~~

Given native-measured `IntrinsicSizes`, the code resolves the supported
`min-content`, `max-content` and `content` flex-basis keywords.
`flex-basis:auto` uses an explicit definite preferred main-size suggestion
when supplied, or falls back to a measured content-based max-content size.
The non-scroll-container automatic main minimum uses the min-content
suggestion limited by a definite specified size and maximum constraint.
An actual scroll container instead has an automatic minimum of zero.
Explicit min-size overrides the automatic rule.

~~~mermaid
flowchart TD
    A["UI-thread intrinsic snapshot (external)"] --> B["Pure typed intrinsic inputs"]
    B --> C["Resolve basis: auto/content/min/max-content"]
    B --> D["Resolve automatic main minimum"]
    D --> E{"Actual scroll container?"}
    E -->|"Yes"| F["Auto min = 0"]
    E -->|"No"| G["Min-content, capped by specified/max"]
    C --> H["Validated FlexBasis for §9.7"]
    F --> H
    G --> H
~~~

The `scroll_container` flag is an **explicit classification provided by
the future overflow/measurement stage**. `overflow:auto` alone does
not imply that a scroll container is present. No native viewports, events,
Scroll component behavior or rendering adapters are modified.

**Feature gates:** replaced elements, transferred aspect ratio, indefinite
percentage basis resolution, fit-content, text-height remeasurement when
width changes, cycles and cross-axis intrinsic measurement are **not
claimed as supported**; they require follow-on contract work. This module
never measures a GUI widget, accesses fonts or silently invents sizes.

**Acceptance:** commit implementations and focused Python/Rust tests;
inspect GitHub Actions for Python 3.10–3.13 and Rust. Browser conformance
and parity fixture comparisons remain pending until F2.2.6/F2.3.

## 14. F2.2.2 — Cyclic percentage gap and definite box sizing

This is an incremental delivery of F2.2.2, **not completion of all CSS
percentage-cycle and box-sizing semantics**.

~~~text
psx/sfle/percentage_box_sizing.py         Python pure sizing boundaries
rust/sfle-core/src/percentage_box_sizing.rs
                                         Rust counterpart
tests/sfle/test_percentage_box_sizing.py  CSS-definiteness boundary fixtures
~~~

A percentage gap is resolved against the definite corresponding container
axis when available. When the reference is indefinite, CSS cyclic gap
contributes zero to **intrinsic size calculations only**. Its final
used-layout value remains unresolved: the engine raises an explicit
capability error until a suitable used size exists. No indefinite hint
is treated as a definite reference.

For a definite specified dimension with already-resolved padding/border:

- `content-box`: content = specified; border-box = specified + edges.
- `border-box`: content = max(0, specified - edges); border-box =
  content + edges. The fixed edges set the border-box floor.

Both languages reject invalid negative values and preserve definite zero.

**CI verification:** commit `6c7f5ea0a1e53996d23dd033c7878b7258f0e15c`
passed Rust and Python SFLE 3.10–3.13, along with general PSX validation,
PySide6 offscreen and the distribution build. The later docs-only update
correctly skipped expensive test matrices.

~~~mermaid
flowchart TD
    A["Tagged percentage gap"] --> B{"Axis definite?"}
    B -->|Yes| C["Used numeric gap"]
    B -->|No| D{"Intrinsic contribution phase?"}
    D -->|Yes| E["Zero intrinsic contribution only"]
    D -->|No| F["Explicit unsupported until used-size resolution"]
    G["Definite width/height + resolved padding/border"] --> H["CSS box-sizing"]
    H --> I["Content-box / border-box used sizes"]
~~~

**Still required before marking F2.2.2 complete:** integrate resolved sizing
with flex items and main/cross dimensions, add CSS min/max box-sizing
adjustments, cover dependent percent cycles beyond gap, and implement
negative/automatic flex margins without conflating them with layout
auto-minimum sizing. Browser-backed reference cases remain a separate
acceptance gate.

### Chromium headless CI checkpoint (agreed)

A **small, opt-in Playwright/Chromium fixture suite should be introduced
after F2.2.3**, rather than deferring all browser comparisons to F2.3.
It should run on supported GitHub Actions Linux runners, compare shared
input structures with Python/Rust and Chromium's element rectangles, and
produce useful diffs. It must not run for docs-only changes and must not
silently assume subpixel browser rounding equals SFLE's double-precision
coordinates.

The larger conformance suite and 0.01 logical-px numerical acceptance
threshold remain owned by F2.3. This checkpoint is a plan, **not an
implemented workflow yet**.

## 15. F2.2.2 — Signed and automatic main-axis margins

A separate pure **post-flex** margin distribution kernel now exists:

~~~text
psx/sfle/main_margins.py             Python signed/auto main margins
rust/sfle-core/src/main_margins.rs   Rust counterpart
tests/sfle/test_main_margins.py      LTR/RTL, reverse and overflow fixtures
~~~

This kernel receives previously-resolved **border-box** main sizes and
logical main-start/main-end margin values. Explicit margins may be signed;
an `auto` margin is represented by a distinct `None`, never by numeric
zero. After flex sizing, any **positive** remaining main-axis space is
distributed equally to all auto main margins. Under negative free space,
auto main margins resolve to zero. Logical axes map to physical positions
for LTR/RTL row and row-reverse, and column/column-reverse.

The result positions border boxes directly, avoiding the incorrect
assumption that a signed-margin box must always be representable as a
nonnegative-width `Rect`.

~~~mermaid
flowchart TD
    A["Flex-sized border boxes + signed / AUTO logical margins"] --> B["Remaining main free space"]
    B --> C{"Positive and AUTO margins?"}
    C -->|"Yes"| D["Share equally across auto edges"]
    C -->|"No"| E["Auto edges resolve to zero"]
    D --> F["Physical border positions with LTR/RTL/reverse"]
    E --> F
~~~

**Important scope boundary:** This is a standalone pure post-sizing kernel
and is **not yet connected** to `edge_pipeline.py`. That pipeline still
rejects negative margins. Before this subblock is complete, its line
formation must also use signed fixed margins and zero auto margins,
flex sizing must incorporate the resulting outer contributions, and
cross-axis auto margins need their own CSS semantics. Other outstanding
requirements include min/max box-sizing constraints and percentage cycles.
No complete CSS Flexbox feature is advertised by the engine.

**CI checkpoint:** GitHub Actions SFLE run `38060561716` passed Python
3.10–3.13 and Rust on the margin-kernel change set. This confirms the
committed unit tests, not browser geometric conformity or the missing
integration with line breaking.

The agreed optional Chromium/Playwright fixture CI checkpoint remains
scheduled after F2.2.3; it will not require a local browser.

## 16. F2.2.2 — Integrated line fitting with signed/auto main margins

This increment closes the disconnect between the standalone main-margin
solver and the *resolved* Flex pipeline, without enabling a full CSS engine.

~~~text
psx/sfle/margin_flex_pipeline.py        Integrated Python restricted pipeline
rust/sfle-core/src/margin_flex_pipeline.rs
                                      Integrated Rust restricted pipeline
tests/sfle/test_margin_flex_pipeline.py
                                      Focused integration tests
~~~

The restricted pipeline orders items, forms lines from hypothetical
**outer** main sizes (including signed fixed margins, with auto margins
counted as zero), resolves flexible content sizes **per line**, then
distributes positive remaining main-axis space among auto margin edges.
Used border, padding and content rectangles are returned in physical
LTR/RTL row/column coordinates. Its dedicated output explicitly records
used main-start/end margins and *does not fabricate a positive-width
margin rectangle*: a CSS margin box can have a negative mathematical
extent when margins are signed.

~~~mermaid
flowchart TD
    A["Content flex bases + padding/border + signed/AUTO main margins"] --> B["Order-modified outer hypothetical line fitting"]
    B --> C["Per-line CSS flex size resolution"]
    C --> D["Post-flex AUTO main margin distribution"]
    D --> E["Border / padding / content geometry in LTR/RTL"]
~~~

**Scope:** main-axis margins only. All cross-axis margins are rejected;
alignment, nested flex/recursive sizing, unresolved percentages and native
measurement remain outside the supported path. This implementation is
additive alongside `edge_pipeline`; no public renderer or engine
capability is enabled. This avoids changing the pre-existing zero/signed
edge-geometry contract while tests and browser conformance are pending.

**Remaining F2.2.2 work:** CSS min/max constraints with box-sizing,
cross-axis margin semantics, percentage-dependent layout sizing, and
geometry parity with browser reference snapshots. **Verified CI:** run `38061081019` passed Python SFLE 3.10–3.13 and
Rust; run `38061081024` passed general PSX Python, PySide6 offscreen
and distribution build for code commit `de512501`.

Early headless Chromium
fixtures remain scheduled just after F2.2.3, using GitHub Actions
rather than requiring a developer's local machine.

## 17. F2.2.2 — Definite CSS min/max with box-sizing

The pure Python and Rust normalization now accepts already-definite CSS
`flex-basis`, `min-width`/`min-height` and
`max-width`/`max-height`, along with an already-resolved sum of
padding and border widths on the main axis:

~~~text
psx/sfle/percentage_box_sizing.py          normalize_flex_box_basis(...)
rust/sfle-core/src/percentage_box_sizing.rs normalize_flex_box_basis(...)
tests/sfle/test_percentage_box_sizing.py   normalized bounds and integration
~~~

All sizes are converted into the **content-box units** expected by the
existing `FlexBasis` math kernel. For `border-box`, fixed padding and
border contribute a floor, so computed content sizes never become negative.
CSS minimum constraints win if a specified definite maximum is smaller.
For `content-box`, the numeric basis and constraints are retained.

The resulting `FlexBasis` is accepted directly by the already-implemented
signed/auto-margin Flex pipeline, tested with a nonzero padding/border
contribution. The same operation and edge cases are implemented in Rust.

~~~mermaid
flowchart TD
    A["Definite flex basis and min/max + padding/border"] --> B{"box-sizing"}
    B -->|"content-box"| C["Keep content sizes"]
    B -->|"border-box"| D["Subtract fixed edges, floor at zero"]
    C --> E["CSS minimum wins conflicting maximum"]
    D --> E
    E --> F["Validated content-box FlexBasis"]
    F --> G["Existing resolved Flex and main-margin pipeline"]
~~~

**Scope gates remain:** percentage-dependent or intrinsic min/max bounds,
automatic min-content detection, cross-axis automatic margins and
constraint resolution that depends on available content width still
require their respective sizing/measurement stages. This is a definite
numeric sub-slice, not full CSS box sizing conformance.

**Verified CI:** on code commit `d3d1773c`, SFLE run `38061313934`
passed Rust plus Python 3.10–3.13. PSX run `38061313909` passed
Python 3.10–3.13, PySide6 offscreen, and distribution build. The
subsequent documentation-only commit correctly skipped expensive CI.

## 18. F2.2.2 — Resolved cross-axis signed and AUTO margins

A matching pure Python/Rust cross-axis margin positioning kernel was added:

~~~text
psx/sfle/cross_margins.py          position_cross_margins(...)
rust/sfle-core/src/cross_margins.rs
tests/sfle/test_cross_margins.py   Positive space, overflow, signed, reverse
~~~

Both kernels operate on **previously resolved border-box cross size** and a
**previously established flex-line cross size**. Positive free space is
shared between the present AUTO margins (one or both). For nonpositive
space, the cross-start AUTO margin becomes zero; an opposite AUTO margin
may absorb the remaining negative space. Fixed signed margins are
preserved. The returned position is physical relative to its flex line;
reverse cross-axis positioning uses the opposite physical edge.

~~~mermaid
flowchart TD
    A["Known flex line cross size + border-box cross size"] --> B["Fixed signed / AUTO cross margins"]
    B --> C{"Free cross space positive?"}
    C -->|Yes| D["Distribute to AUTO cross margins"]
    C -->|No| E["Cross-start AUTO = 0; end AUTO absorbs remainder"]
    D --> F["Physical border position on cross axis"]
    E --> F
~~~

**Important:** this is a standalone kernel and not yet connected to
`margin_flex_pipeline`. It does not determine line cross sizes, perform
stretch/baseline alignment, implement `align-content`, or handle native
measurements. Those integration points remain for F2.2.3 and F2.2.4.
The optional early Playwright/Chromium headless GitHub Actions checkpoint
remains scheduled after F2.2.3.

**CI:** for code commit `416a769c`, SFLE workflow `38062168357`
passed Rust and Python 3.10–3.13. The general PSX workflow
`38062168348` is tracked separately.

## 19. F2.2.2 — Cross margins integrated into resolved Flex layout

Both the Python and Rust `margin_flex_pipeline` now accept separate,
explicit `cross_start` and `cross_end` margin values. The existing
`main_start`/`main_end` contract is preserved. All four margin values
are typed and signed, with `None` denoting AUTO.

The line-cross calculation uses the definite inner container cross size
for a single `nowrap` line. Wrapped lines take the largest nonnegative
outer cross contribution of their line items, counting AUTO margins as
zero and retaining fixed signed margins. The existing cross-line
placement supplies line origins; the shared cross-margin kernel places
each border rectangle *within* its line. Outputs now record both used
main and used cross margin values. Matching implementations exist in
Python and Rust with focused tests for nowrap centering, overflow,
signed wrapped-line margins, wrap-reverse and column RTL.

~~~mermaid
flowchart TD
    A["Ordered flex lines + resolved item cross sizes"] --> B{"nowrap?"}
    B -->|Yes| C["Line cross size = definite container cross size"]
    B -->|No| D["Line cross size = max fixed outer contribution"]
    C --> E["Resolve AUTO and signed cross margins"]
    D --> E
    E --> F["Combine physical line origin with cross border offset"]
    F --> G["Border / padding / content rectangles"]
~~~

**Outstanding:** CSS align-items/align-self/align-content, stretch,
baseline, size remeasurement under width constraints, and general
cyclic/intrinsic percentage support. This restricted resolved-layout
pipeline does **not** enable engine capabilities. The early Chromium
Playwright fixture CI checkpoint remains planned immediately after F2.2.3,
without requiring a local browser.


### F2.2.2 integrated cross-margin CI checkpoint

The first Python SFLE matrix found an output-contract bug: the correct
cross-axis border positions were calculated but `MarginFlexBox` silently
used its default zeros for the *recorded* used cross margins. The immutable
output constructor now explicitly preserves `used_cross_start_margin` and
`used_cross_end_margin`. Subsequent SFLE run `38062858653` on code
commit `3029f250` passed Rust and Python 3.10–3.13. General PSX alpha
validation run `38062858640` is checked separately.

## 20. F2.2.2 — Percentage flex-basis fallback based on definiteness

This incremental slice distinguishes a **definite flex container main
size** from an indefinite size carrying only an available-space hint.
With a definite main size, a percentage flex-basis resolves to the
specified fraction of that main size; **definite 0% remains zero**.
When the main size is indefinite, the CSS used flex-basis becomes
content-based: the new helper delegates to the already-implemented
`flex-basis: content` path using premeasured `IntrinsicSizes`.

~~~text
psx/sfle/percentage_flex_basis.py
rust/sfle-core/src/percentage_flex_basis.rs
tests/sfle/test_percentage_flex_basis.py
~~~

~~~mermaid
flowchart TD
    A["Typed percentage flex-basis + AvailableSize"] --> B{"Container main size definite?"}
    B -->|"Yes"| C["Fraction × definite main size"]
    B -->|"No"| D["Premeasured content-based flex basis"]
    D --> E{"Unsupported intrinsic case?"}
    E -->|"Yes"| F["Explicit capability error"]
    E -->|"No"| G["Measured content size"]
~~~

For this restricted calculation the intrinsic snapshots must come from
an upstream measurement adapter and correspond to the appropriate main
axis. The fallback is *not* equivalent to `flex-basis: auto` with an
explicit preferred size. The helper rejects unsupported transferred
aspect ratios in indefinite fallback cases.

**Still pending for F2.2.2:** integrating tagged layout percentages
with item style normalization and recursive measurement, dependent
min/max percentage sizing with indefinite containing blocks, and
other cyclic percentage cases. No generic SFLE engine capability or
browser-level conformity claim is unlocked by this increment.


**CI for percentage flex-basis fallback:** code commit `5a960a9c`,
SFLE workflow `38063346629`: Rust and Python 3.10–3.13 passed;
PSX alpha validation workflow `38063346625`: Python 3.10–3.13,
PySide6 offscreen and distribution build passed. These results apply
to the restricted implementation, not CSS Chromium geometry conformance.

## 21. F2.2.2 — Typed property-aware percentage constraints bridge

This increment connects the existing CSS percentage resolver, content-based
fallback for indefinite `flex-basis` and definite `box-sizing` normalization:

~~~text
psx/sfle/percentage_constraints.py
rust/sfle-core/src/percentage_constraints.rs
tests/sfle/test_percentage_constraints.py
~~~

Inputs include separately typed references for the containing block inline
size, corresponding main-axis containing block size, and flex container
main size; no ambient parent width is inferred. Percent main-axis
min/max use their containing block axis while `flex-basis` uses the flex
container main axis. Definite zero is preserved. `max:none` yields an
unbounded constraint, and the pure bridge delivers a validated content-box
`FlexBasis` into the already implemented Flex math/geometry pipeline.

When `flex-basis` percent has an indefinite main-axis reference, it can
use an **explicit premeasured** intrinsic content snapshot rather than
incorrectly assuming zero or treating available-size hints as definite.
Indefinite percentage min/max bounds and an automatic minimum are
explicitly deferred; they must be resolved in the contextual CSS
sizing/measurement phase. No invented geometry is emitted.

~~~mermaid
flowchart TD
    A["Typed length + property reference dimensions"] --> B["Resolve min/max with containing-block main axis"]
    A --> C["Resolve flex-basis with container main axis"]
    C --> D{"Definite?"}
    D -->|"Yes"| E["Used numeric basis"]
    D -->|"No"| F["Explicit measured content fallback or error"]
    B --> G{"Both constraints resolved?"}
    G -->|"No"| H["Explicit pending measurement diagnostic"]
    G -->|"Yes"| I["Normalize content-box/border-box"]
    E --> I
    F --> I
    I --> J["Validated FlexBasis"]
~~~

This remains a **restricted internal operation**, not full CSS percentage
cycle conformance. In particular, percentage min/max fallbacks that depend
on a CSS formatting context, intrinsic contribution cycles, native text
remeasurement and replaced-element/aspect-ratio rules are still gated.
No new public `Flex` feature or engine capability is enabled. Chromium
headless fixtures remain scheduled after F2.2.3.


**Verified CI:** commit `94c5cc1`: SFLE run `38063729558` passed
Rust and Python 3.10–3.13; general PSX validation run `38063729542`
passed Python 3.10–3.13, PySide6 offscreen and distribution build. This
validates only the deliberately restricted resolved-input contract.

## F2.2.2 scoped closure and F2.2.3 start

F2.2.2 pure resolved-input sizing and signed/auto margin contracts are accepted as implemented, with passing prior Python/Rust CI. This does NOT include complete CSS layout. Percentage min/max with indefinite containing blocks, cyclic percentages, width-sensitive intrinsic remeasurement, replaced elements and aspect-ratio transfers require recursive measurement in F2.2.4. Full Chromium geometry conformance belongs to F2.3, and numerical backend parity to F2.2.6. Unsupported inputs must continue to fail explicitly. Engine capability manifest stays closed.

First F2.2.3 increment: `psx/sfle/main_alignment.py`, `rust/sfle-core/src/main_alignment.rs` and `tests/sfle/test_main_alignment.py` implement pure resolved `justify-content` leading and between spacing for flex-start, flex-end, center, space-between, space-around and space-evenly. Supports signed resolved outer contributions and overflow fallbacks. Integration with the line pipeline, alignment of cross axes, baseline, stretch, and align-content are still pending. Chromium Headless with Playwright in GitHub Actions remains planned immediately after F2.2.3.\n\nCI verification: SFLE core workflow `38064329341` passed Rust and Python 3.10–3.13; PSX alpha validation `38064329313` passed Python 3.10–3.13, PySide6 offscreen, and the distribution build. Neither run constitutes browser conformance.


## F2.2.3 — Justify-content integrated into real Flex placement

The pure spacing solver is now used by the main-axis margin placement kernel and the integrated resolved Flex layout pipeline, in both Python and Rust. The implementation handles `flex-start`, `flex-end`, `center`, `space-between`, `space-around` and `space-evenly` with the correct logical main direction for row/row-reverse/column/column-reverse and LTR/RTL. Fixed gaps and signed outer margin contributions remain explicit. Positive remaining free space is first assigned to main-axis AUTO margins, so `justify-content` does not redistribute it. Overflow alignments retain their specified fallbacks. Rust preserves the old `compute_margin_flex_layout` entry point as a flex-start wrapper and adds `compute_margin_flex_layout_justified`; Python accepts a backward-compatible optional `justify` keyword.

The new regression test suite is `tests/sfle/test_justify_pipeline.py`, with Rust integration cases in `margin_flex_pipeline.rs`. The next slice remains cross-axis alignment and stretch/baseline. The small Chromium/Playwright CI checkpoint stays after F2.2.3, before formal F2.3 conformance.


**Integrated justify-content CI:** code commit `02737d37`, SFLE run `38064998080`: Rust and Python 3.10–3.13 all passed. PSX alpha validation run `38064997890` passed Python 3.10–3.13, PySide6 offscreen, and distribution build. No Chromium geometry comparison or `align-content`/baseline/stretch support is implied.


## F2.2.3 — Cross-axis align-items and align-self, resolved-size slice

Both implementations now support typed `align-items` at the container boundary and `align-self` overrides at the item boundary, with `auto` meaning inherit the container's cross alignment for `align-self`. Supported used alignment modes are `flex-start`, `flex-end`, and `center`. The calculation operates on previously established line cross sizes and resolved border boxes, preserving fixed signed cross margins and RTL/column/wrap-reverse physical-axis mapping.

Cross-axis `auto` margins still take priority over both alignment properties, as required by Flexbox. The existing used-margin output remains unchanged. New kernels are `psx/sfle/cross_alignment.py` and `rust/sfle-core/src/cross_alignment.rs`; integration resides in the existing `margin_flex_pipeline` pair. Python regression cases are in `tests/sfle/test_cross_alignment.py` with matching Rust module and integrated geometry tests.

`stretch` and `baseline` deliberately fail with an explicit unsupported error when selected for fixed-margin alignment: stretch requires the cross-size auto-vs-definite/min-max sizing contract and potentially native measurement; baseline requires per-item baseline metrics and line baseline groups. `align-content` and general multi-line distribution remain pending. These are not silently mapped to `flex-start`. The initial Chromium/Playwright headless reference suite remains scheduled after F2.2.3.


**CI for this increment:** commit `b5495b49` passed SFLE run `38065836312` (Rust and Python 3.10–3.13). The first run detected an incorrect expected reverse-axis center coordinate (35 vs 45 pixels) in the test fixtures; both fixtures were corrected and the second SFLE matrix passed. General PSX alpha run `38065836183` also passed Python 3.10–3.13, PySide6 offscreen and distribution build.


## F2.2.3 — Align-content multi-line distribution

Both resolved-input implementations now have a pure `align-content` line-distribution kernel in `psx/sfle/align_content.py` and `rust/sfle-core/src/align_content.rs`. The main Flex pipelines call it to determine each flex-line's physical cross-axis origin and used cross size, and pass that used size to the existing cross margin and item alignment logic. Modes: `flex-start`, `flex-end`, `center`, `space-between`, `space-around`, `space-evenly`, and line-level `stretch`. The `nowrap` cross-line allocation is always the definite container cross size regardless of `align-content`; distribution covers wrapped lines. Fixed `cross_gap` is retained; `wrap-reverse` and RTL columns map line cross-start to physical coordinates. Negative free space does not produce negative distributed extra gaps; explicit center/flex-end can overflow.

**Important:** line-level `align-content: stretch` grows the flex **line** cross size only, not the item border box. `align-items: stretch` and `align-self: stretch` still require separate CSS automatic cross-size/min-max constraints and remain capability gated, as does baseline measurement. Full browser conformance awaits the previously agreed post-F2.2.3 Playwright/Chromium headless CI checkpoint and later F2.3.

New Python tests: `tests/sfle/test_align_content.py`; Rust module and integrated layout unit tests are included. The F2.2.3 subblock remains open for item stretching and baseline.


**Align-content CI checkpoint:** initial code set failed Rust compilation because the new wrapper was inserted at the incorrect level of the retained API wrapper hierarchy. This was corrected in code commit `d7cef816`, preserving the old entry points. On that commit, SFLE run `38066310555` passed Rust plus Python 3.10–3.13, and PSX alpha run `38066310554` passed Python 3.10–3.13, PySide6 offscreen and the distribution build. This confirms the new scoped tests, not browser parity.


## F2.2.3 — Explicit auto cross-axis item stretch

The pure `psx/sfle/cross_stretch.py` and `rust/sfle-core/src/cross_stretch.rs` implementations now calculate used content and border cross sizes from an established line cross size, definite padding/border, signed fixed cross margins, and explicitly supplied definite min/max content bounds. A conflicting minimum overrides maximum; fixed border/padding cannot shrink to negative sizes. Both resolved Flex pipelines consume the helper, with per-item `cross_size_auto`, `min_cross_content_size`, and `max_cross_content_size` contracts. These preserve the old default semantics (`cross_size_auto=false`) for callers not yet passing size definiteness.

Stretch is selected only by inherited `align-items: stretch` or per-item `align-self: stretch` **and** an explicitly automatic cross size with both cross margins fixed. Auto cross margins suppress stretching and take their existing margin-positioning precedence. For definite item cross sizes, stretch behaves as start alignment without modifying content. The sizing result is reflected in border, padding and content rectangles, also for RTL column layout and lines expanded by `align-content: stretch`.

**Limitations:** the automatic cross-size flag and min/max values must already be correctly normalized from CSS; native measurement, aspect-ratio transfer, width-sensitive intrinsic remeasurement and baseline groups remain deferred. Passing the scoped tests does not imply Chromium conformance or public engine integration. No public Flex capability is unlocked.


**Stretch CI checkpoint:** code commit `dd2aabf5` passed SFLE workflow `38066884574` (Rust and Python 3.10–3.13). Initial tests expecting every `stretch` mode to fail were updated to the now-supported contract: definite item cross dimensions remain unchanged while explicitly automatic dimensions stretch within min/max and fixed-edge constraints. PSX alpha workflow `38066884571` passed Python 3.10–3.13, PySide6 offscreen and distribution build. Chromium and baseline conformance remain open.


## F2.2.3 — Measured first-baseline group contract

New `psx/sfle/baseline.py` and `rust/sfle-core/src/baseline.rs` implement *first-baseline* alignment from **explicitly supplied** baseline positions relative to an item's logical cross-start content edge. The resolved horizontal Flex pipelines aggregate each line's baseline group's maximal ascent and descent (including signed fixed margins), increase wrapped line cross size when required, and position baseline-aligned items so their measured baseline coordinates coincide. Existing `align-items: baseline` and per-item `align-self: baseline` select this path only when a valid premeasured offset is supplied. Missing/out-of-range metrics raise explicit errors. Cross-axis AUTO margins bypass baseline alignment and retain their established precedence.

The item contract adds `baseline_from_cross_start` (Python) / `baseline_from_cross_start: Option<f64>` (Rust). It must be a measured content-box offset from the logical cross start, not a computed font ascent guess. The pipeline adds padding and border start offsets before grouping. Measurement remains upstream and will be introduced with F2.2.4 renderer adapters.

**Known scope restrictions:** column/orthogonal baselines require a dedicated writing-mode and baseline measurement contract and fail explicitly. Baseline synthesis, font fallback, replaced-element baselines and multi-baseline alignment variants are not implemented. Do not treat this slice as complete CSS Flexbox baseline conformance. First baseline is handled only for resolved horizontal flow, fixed margins and provided metrics. CI must pass before claiming F2.2.3 acceptance; Chromium reference testing remains the next agreed checkpoint after F2.2.3.


**Measured baseline CI checkpoint:** code commit `34b57ae5` passed SFLE run `38067349752` on Rust and Python 3.10–3.13, and PSX alpha run `38067349761` on Python 3.10–3.13, PySide6 offscreen, and distribution build. This only verifies restricted horizontal measured-first-baseline grouping, not native font measurement or Chromium conformance.


## Initial headless Chromium geometry checkpoint (post-F2.2.3 scoped work)

The first real-browser comparison lives at `tests/browser/test_sfle_chromium.py` and is executed by `.github/workflows/sfle-chromium.yml`. GitHub Actions installs Playwright and the **headless Chromium binary in the CI runner**, not on the developer workstation. Fixtures compare four border-box fields (`x`, `y`, `width`, `height`) with 0.05 CSS-pixel tolerance, using root-relative rectangles and explicitly defined CSS sizes. The initial, deliberately narrow corpus covers centered rows, row RTL `space-between`, wrapped `align-content: space-between`, wrapped line stretch with centered children, auto cross-axis item stretch, and RTL column center.

The comparison suite is not added to `tests/sfle`: ordinary SFLE Python/Rust contract validation does not require Chromium or Playwright. The browser job can be dispatched manually and also runs on changes to the engine, fixture suite or its workflow. The fixtures test **border-box positioning only** for fully resolved pixel inputs; they deliberately exclude native text baseline acquisition, indefinite percentages, intricate CSS intrinsic sizing, replaced elements, and recursive layout. This is an early scoped browser parity gate, not a claim that F2.3 browser conformance is complete.


### F2.2.3 scoped acceptance decision (first Chromium evidence)

GitHub Actions **SFLE Chromium geometry checkpoint** run [38067599261](https://github.com/Neuri-AI/PSX/actions/runs/38067599261) completed successfully on workflow commit `88d6f556`: **6/6 fixtures passed** under Playwright headless Chromium 153 (headless shell build 1243). The comparison tests assert `x`, `y`, `width`, and `height` of every item border-box within `0.05` CSS px of Chromium. General PSX alpha validation [38067599264](https://github.com/Neuri-AI/PSX/actions/runs/38067599264) passed Python 3.10–3.13, PySide6 offscreen and distribution build. Existing Rust and Python resolved-input tests remain passing from prior F2.2.3 commits. The six new browser fixtures directly exercise the **Python** solver; they do **not** independently exercise the Rust solver or its bindings.

F2.2.3 is **accepted only as a restricted resolved-input horizontal-writing alignment implementation**. The accepted scope covers justify-content; basic align-items/align-self; align-content for multi-line flex; explicit auto cross-size stretch; and first-baseline alignment only when upstream already supplies measured baseline offsets for horizontal Flex. Unresolved percentages and recursive sizing, native baseline acquisition, orthogonal/column baseline groups, synthesized/replaced-element baselines, and shared numerical Rust/Python browser parity are explicitly *not accepted* by this milestone; they belong to F2.2.4/F2.2.6 and broader browser conformance F2.3. The public capability manifest, native renderer migrations, and runtime backend selection remain closed.

**Next subblock: F2.2.4 — Recursive Layout & Measurement.** Before turning on any public Flex API, establish measured-size snapshots, constraint propagation, generation/invalidation rules, and native toolkit measurement boundaries; follow with Rust-primary/Python fallback integration F2.2.5 and expanded shared parity corpus F2.2.6.


## F2.2.4 — Recursive measurement planner: first accepted increment

The renderer-independent modules `psx/sfle/measurement_plan.py` and `rust/sfle-core/src/measurement_plan.rs` plan a deterministic child-before-parent measurement worklist from an explicitly constrained layout tree. Python uses the existing validated `LayoutInput`, `LayoutConstraints` and `MeasuredBox` contracts; Rust independently validates a preorder node snapshot and definite/indefinite axis constraints. Exact cached-measurement reuse requires identical node ID, constraints and revision **and no dirty descendant**. A missing, constraint-changed or revision-changed child invalidates its ancestors in the same bottom-up pass; generation-tagged measurement acceptance rejects stale results. Python regression cases in `tests/sfle/test_measurement_plan.py` cover traversal, reuse, cache invalidation, missing constraints and stale generations.

**Boundary:** This is dependency planning, **not** a complete recursive layout algorithm. It cannot guess a child's used width from the parent; child constraints must already be resolved by a future CSS sizing stage. UI-thread toolkit measurements, intrinsic width-dependent remeasurement, percentage cycle solving, ancestor size convergence and final nested geometry are not yet connected. The public Flex capability remains disabled.

Verified SFLE focused workflow `38068204776`: Rust and Python 3.10–3.13 passed. Headless Chromium checkpoint `38068204672` also passed the existing six geometry fixtures. General PSX validation is tracked separately. The next F2.2.4 increment must introduce explicit constraint propagation and safe remeasurement without inferring CSS values.


**Cache correctness follow-up:** the first planner revision could reuse a parent measurement while a descendant was scheduled for remeasurement. That was unsafe because a changed child's intrinsic size may invalidate every ancestor. The Python and Rust planners now propagate dirty status from descendants to parents during reverse-preorder traversal; focused regression tests explicitly prohibit stale ancestor reuse. This is conservative invalidation, pending finer dependency tracking in subsequent F2.2.4 increments. Follow-up code commit `ff25d4a0` passed SFLE run `38068376248` (Rust, Python 3.10–3.13), PSX alpha run `38068376245` (Python 3.10–3.13, PySide6 offscreen and build), and Chromium checkpoint `38068376249` (existing six fixtures).


## F2.2.4 — Explicit CSS child constraints for recursive measurement

The new `psx/sfle/constraint_propagation.py` and `rust/sfle-core/src/constraint_propagation.rs` provide a typed boundary from an **established parent content-box size** plus the child's explicitly specified `width` and `height` CSS Length values to the constraints used for child measurement. The width percent reference is the parent content-box inline width; height percent refers to the parent content-box block height (horizontal writing mode). Definite pixels and percentages become definite child axes; `auto`, intrinsic keywords and percentages with indefinite containing dimensions stay **indefinite**, with no fabricated used numeric value.

`plan_styled_measurements` connects these per-child derived constraints with the F2.2.4 descendant-first `plan_measurements` worklist, including existing revision and generation controls. Every non-root node needs an explicit style declaration and a separately established parent content-box constraint snapshot. This is deliberate: a parent's *available constraint* may differ from its used content box because of padding, borders, margins, intrinsic sizing or Flex algorithms; it is not a safe substitute. Tree branches missing established parent content boxes fail with an explicit unsupported-measurement diagnostic, rather than silently inheriting widths. Python `tests/sfle/test_constraint_propagation.py` and Rust module tests cover definite percentages, indefinite height, auto/intrinsic deferral, nested parent content references and missing-parent guards.

**Important boundary:** this increment resolves specified child width/height against known parent content boxes. It is **not** a general recursive Flex geometry solver; the parent's content box must currently be supplied by the upstream sizing pass, and automatic flex sizes, cyclic dependencies, native text measurement and iterative convergence remain pending. Until those contracts are implemented, do not enable the public Flex capability or claim that arbitrary CSS child constraints can be resolved. GitHub Actions Rust/Python/Chromium results are recorded on code commits after validation.


**Constraint propagation CI verification:** code commit `78071f81` passed focused SFLE workflow `38068993188` (Rust and Python 3.10–3.13). The initial commit failed Rust compilation because a borrowed map value was dereferenced twice; the map lookup was corrected to a single dereference and the complete SFLE matrix reran successfully. General PSX validation `38068993177` passed Python 3.10–3.13, PySide6 offscreen and build; Chromium checkpoint `38068993175` passed the existing six border-box reference fixtures.


## F2.2.4 — Used content-box to nested measurement bridge

An incremental typed adapter is now implemented in Python and Rust, without opening the public Flex capability:

- Python `plan_used_box_measurements(snapshot, used_boxes, child_sizing, revisions)` takes established `BoxRect` values and derives definite parent content dimensions from `box.content.width/height`. It then delegates to the existing `plan_styled_measurements` and descendant-first planner.
- Rust `plan_used_box_measurements` takes `UsedContentSize` snapshots (the content dimensions already extracted by the geometry owner), rejects nonfinite or negative inputs, and delegates to the equivalent existing planner.
- Matching Python/Rust regression cases check a three-level Flex/Flex/Text tree, explicit border-vs-content sizing, unknown/duplicate input, missing parent evidence, and nonfinite dimensions.

**Strict scope:** The input boxes must be from a valid, current-generation upstream geometry pass; this helper does not itself verify their generation or calculate Flex used sizes. Parent automatic sizing, intrinsic width-sensitive remeasurement, dependency-cycle resolution, geometry iteration, native UI-thread measurement, and final nested `LayoutResult` remain pending F2.2.4 work. Avoid describing this adapter as a complete recursive layout algorithm. Preserve the closed capability gate and draft PR until those requirements are met.

**Next milestone:** establish the per-node used-size computation/dependency state machine in the pure Python/Rust engine, with explicit handling of indefinite axes and remeasurement rather than assuming every parent used content box exists ahead of time.


## F2.2.4.5 — Dependency Resolution & Remeasurement (first restricted increment)

New pure, matching Python/Rust `remeasurement` modules compare validated previous/current used-size tree snapshots, preserving generation and identity checks. When a node's resolved content dimensions change, its dependent descendants and its ancestors are included in a deterministic reverse-preorder measurement worklist. The result also retains all partially indefinite nodes as a separate `deferred` collection; indefinite axes are **not** coerced to zero or treated as resolved geometry.

Files: `psx/sfle/remeasurement.py`, `rust/sfle-core/src/remeasurement.rs`, `tests/sfle/test_remeasurement.py`. These include changed-child, unchanged-tree, unresolved-axis, and invalid-generation/order regressions.

**Scope:** This is an invalidation *delta* between known snapshots; it does not execute measurements, compute ancestor automatic sizes, solve CSS percentage dependency cycles, inspect actual native widgets, or determine convergence. The F2.2.4.5 subblock remains **in development** until those follow-on behaviors are implemented and verified. Next: make a coordinator consume deltas and remeasure width-sensitive intrinsic nodes with stable generation guards, then handle cyclic layout dependencies according to explicitly supported CSS rules.

**Progress tracking:** F2.2.4 has eight internal subblocks. F2.2.4.1–F2.2.4.4 accepted in their restricted scope (4/8, 50% by count); F2.2.4.5 in progress; F2.2.4.6–F2.2.4.8 pending. Do not count F2.2.4.5 as complete from invalidation alone.


## F2.2.4.5 — Measurement round handshake (second restricted increment)

Python `psx/sfle/measurement_round.py` and Rust `rust/sfle-core/src/measurement_round.rs` now translate a previously computed `RemeasurementDelta` plus **explicit** per-node constraints and revisions into a leaf-first, generation-tagged round of measurement requests. Unaffected measurements may be retained only if both constraints and revisions match. The acceptance boundary checks that all and only requested results arrive, rejects stale generation and mismatched revisions, and verifies the entire set before exposing the result. Python regressions reside in `tests/sfle/test_measurement_round.py`, with mirrored Rust tests.

This is a **pure handshake protocol**. No toolkit callbacks, automatic loop, convergence detector, width-sensitive native text measurement, CSS cycle solver, or final Flex geometry are implemented here. F2.2.4.5 therefore **remains in progress**. Next increment must implement semantic dependency phases and a bounded layout/remeasurement coordinator, using explicitly supported CSS cycle rules and erroring on unsupported cycles. F2.2.4 progress stays **4 of 8 accepted**; F2.2.4.5 is not yet accepted.


## F2.2.4.5 — Bounded convergence guards (third restricted increment)

The pure `psx/sfle/convergence.py` and `rust/sfle-core/src/convergence.rs` state machines now record immutable used-content-size snapshots across rounds, enforcing generation and tree identity and a configurable positive maximum pass count. An unchanged snapshot is considered converged only if **both axes of every node are definite**. A repeated unresolved snapshot, oscillating pair of snapshots, stale generation, or exhausted iteration budget raises an explicit error instead of silently accepting arbitrary geometry. Regression tests cover those boundaries in both languages.

**Still not a CSS cycle solver:** no measurement callbacks are invoked, no automatic/intrinsic box sizes are derived, and CSS cyclic percentage semantics remain deferred. The state machine may be used only as a guard around a future standards-aware measurement/layout coordinator. F2.2.4.5 remains open, with 4/8 F2.2.4 subblocks accepted. Existing browser fixtures do not test the new guard.

## F2.2.4.6 — Restricted resolved nested Flex geometry

A pure recursive geometry slice now reuses the established resolved Flex line and size kernels for each nested container. The current `psx/sfle/resolved_tree.py` and `rust/sfle-core/src/resolved_tree.rs` implementations accept preorder nodes with definite zero-edge box extents, resolved child FlexBasis values, direction, wrapping, gaps, and order. They generate absolute positioned child boxes, including nested RTL and parent flex-grow changes. Python emits `LayoutResult` containing equivalent content/padding/border/margin rectangles only because this restricted subset has **zero edges**; Rust emits equivalent positioned rectangles. Tests are in `tests/sfle/test_resolved_tree.py` and Rust module tests.

Commit `3e9dfcab` passed SFLE Core, PSX Alpha Validation, and Chromium workflows for the PR (plus the two push workflows). The Chromium suite is still only the six **existing** reference fixtures, not new nested browser parity evidence.

**Not yet closure:** This is an already-resolved-input nested geometry kernel. It does not accept unresolved CSS lengths or native intrinsic measurements; nested percentages, auto cross sizes, stretch, full box edges, min/max, baseline and dependency cycles are not integrated. F2.2.4.5 remains open; F2.2.4.6 has a restricted initial implementation, not accepted complete. F2.2.4 currently remains 4/8 accepted (50%), with four subblocks including current pending. Do not begin F2.2.5 milestone prematurely.


## F2.2.4.7/8 — Native UI-thread boundary and first nested Chromium geometry reference

The native measurement boundary now exposes `NativeMeasurementPort` and `fulfill_native_round()` in `psx/sfle/native_measurement.py`. It requires an adapter-provided UI-thread assertion and a synchronous per-request measurement callback. Requests are generation-tagged; the port validates the completed batch through `accept_round` before exposing measurements. Tests in `tests/sfle/test_native_measurement.py` cover correct UI-thread access, no execution off the UI thread, stale generation, and revision mismatches. No Qt/Kivy/Tkinter implementation is connected yet, and the native port is not the full renderer adapter.

`tests/browser/test_sfle_chromium.py` now includes an additional nested, zero-edge Flex reference fixture that checks absolute positions and border-box dimensions for root, sibling, nested parent and leaf. It is the first Chromium nested-tree check but does not validate cyclic, auto or intrinsically sized Flex geometry.

**Closure remains blocked:** F2.2.4.5 must incorporate CSS-valid intrinsic/automatic size dependencies; F2.2.4.6 must support real edges, automatic and intrinsic sizing integrated with Flex distribution; F2.2.4.7 requires framework-specific UI-thread adapters and lifecycle integration; F2.2.4.8 requires broader Chromium regression and equivalent Python/Rust geometry evidence. Maintain F2.2.4 at **4/8 closed** until those acceptance gates are met.


## F2.2.4.5 — Scoped acceptance: dependency and remeasurement coordinator

**Status: ACCEPTED in the restricted alpha dependency-protocol scope (2026-10-10).**
This supersedes the *in-progress* entries above for F2.2.4.5, but does not
retroactively extend what earlier helpers support. The eight-way F2.2.4
tracker now records **5/8 accepted (62.5%)**, with F2.2.4.6–F2.2.4.8
remaining. F2.2 overall remains **4/7 accepted** until all of F2.2.4 closes.

### Acceptance evidence

- Deterministic descendant-first dependency invalidation and revision-aware
  reuse of immutable measurement snapshots: `remeasurement`,
  `measurement_plan`, `measurement_round` in Python and Rust.
- Bounded convergence, generation-safe atomic round acceptance, and
  rejection of repeated indefinite constraints, oscillation, and pass-limit
  exhaustion: `convergence`, `measurement_coordinator` in Python and Rust.
- **Actual multi-pass loop** in
  `psx/sfle/dependency_cycle.py` and `rust/sfle-core/src/dependency_cycle.rs`.
  Every round consumes accepted intrinsic measurements before asking a supplied
  pure CSS-sizing callback to recompute. The Python UI adapter callback must
  execute on the renderer UI thread; Rust core receives measured immutable
  snapshots via caller-provided callbacks.
- Regression tests cover a two-pass intrinsic dependency, a three-pass
  width-sensitive preferred-height remeasurement, invalid revisions and stale
  generations, zero-work reuse, and unsupported nonconvergence.
- **Intrinsic auto leaf-size suggestions** are collected with strict
  cache-constraint and revision matching (Python/Rust
  `intrinsic_dependencies`); they are *not* assigned as final CSS used sizes.
  CSS `flex-basis`, stretch, intrinsic min/max, parent auto sizes and flex
  distribution determine the final used geometry in the later layout phase.
- Last code commit `fd86afc680b53f957d0ed6403885090351d6bcc4`
  passed all five GitHub Actions runs for SFLE Core (Rust + Python 3.10–3.13),
  PSX Alpha Validation and Chromium checkpoint. Chromium is a regression gate
  here, **not** a browser comparison for all auto/dependency cases.

### Explicitly outside F2.2.4.5 closure

This acceptance closes the **dependency scheduling and remeasurement
protocol**, not the full CSS recursive layout engine. The pure CSS recompute
callback remains supplied by a caller, because automatic *Flex container*
size calculation, cyclic percentage semantics and final flex item sizes
require the still-pending F2.2.4.6 recursive sizing/geometry stage.
Unimplemented CSS input combinations raise explicit unsupported diagnostics;
they are not silently treated as resolved or made definite by intrinsic
preferred sizes. F2.2.4.7 must still integrate actual Qt/Kivy/Tkinter
UI-thread adapters; F2.2.4.8 must expand parity and integration coverage.
**Do not enable public Flex or begin F2.2.5 on this subblock's acceptance alone.**
