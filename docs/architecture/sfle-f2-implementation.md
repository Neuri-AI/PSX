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
| **F2.2.2** | **Percentage cycles, box-sizing and deferred sizing edge cases** | **In progress: cyclic percentage gaps, definite box sizing and standalone signed/auto main margins (Python + Rust); CI pending for margins** |
| F2.2.3 | Main/cross alignment, baseline, stretch and multi-line distribution | Pending |
| F2.2.4 | Recursive layout and constrained native measurement protocol | Pending |
| F2.2.5 | PyO3/maturin Rust-primary engine and Python fallback integration | Pending |
| F2.2.6 | Rust/Python parity corpus and core stabilization | Pending |

**Remaining subblocks:** five (F2.2.2–F2.2.6). Other pending stages:
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

The agreed optional Chromium/Playwright fixture CI checkpoint remains
scheduled after F2.2.3; it will not require a local browser.
