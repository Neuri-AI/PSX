# SFLE F2 — Implementation plan and progress

> **Status:** F2 authorized on 2026-10-10. F2.0 implementation blueprint and an
> initial F2.1 data-contract skeleton have been added to the feature branch.
> **No CSS Flexbox calculation, public Flex component, Rust extension, renderer
> migration, or browser conformance claim is made yet.**
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
| F2.1 | Immutable lengths, constraints, layout tree, measurement and result contracts | Validated imports and versioned pure input/output schema; no GUI imports |
| F2.2 | CSS Flexbox computation: Rust primary + parity-matched Python fallback | Matching output on supported flex fixtures; explicit feature gating |
| F2.3 | Browser reference geometry + LTR/RTL conformance | Same line structure; geometry within 0.01 logical px pure with equivalent measurements |
| F2.4 | Inventory/plan migration of Row/Column/Scroll boundaries | No planned aliases; Scroll independent, native adapters retained |

**Not yet complete:** F2.1 should still settle stable serialized wire
representation (Rust enum/tag mappings, node ordering, capability schema,
error types), measure constraints and layout-tree ancestry checks before the
computation core relies on them. F2.2 must not begin under assumptions that
these unresolved contract details are already implemented.

## 3. Current added modules (F2.1 initial skeleton)

~~~text
psx/sfle/
    __init__.py     Internal contract re-exports (not PSX public Flex API)
    lengths.py      Immutable tagged CSS-like lengths and strict parsing
    model.py        AvailableSize, constraints, boxes, measured nodes,
                    layout tree snapshot, output model
    engine.py       LayoutEngine Protocol and explicit unimplemented fallback
~~~

`PythonLayoutEngine.compute()` intentionally raises
`UnsupportedLayoutFeature` today. This preserves D-F1.9 (no silent
non-CSS geometry), and **does not count as a Python fallback
implementation**. The Rust primary extension is not yet present.

~~~mermaid
flowchart TD
    V["PSX VDOM (unchanged)"] --> C["Future SFLE coordinator"]
    C --> M["Future UI-thread intrinsic measurement"]
    M --> I["Immutable LayoutInput v1 (F2.1 skeleton)"]
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
