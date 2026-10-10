# SFLE F1.6 / F1.7 — Contextual layout metadata and typed CSS-like lengths

> **Status:** historical F1.6/F1.7 design exploration. Decisions now ratified.
> **Canonical frozen architectural contracts:** [F1.6/F1.7 box model and percentages](sfle-f1-box-model.md).
> This document retains earlier alternatives for traceability; where it differs,
> the ratified contract takes precedence.
> **D-F1.10 supersession:** Row and Column are removed from the target public
> API entirely, without aliases or compatibility. Any legacy Row/Column
> suggestions below are historical only and must not be implemented. See
> [final F1 architecture](sfle-f1-final-architecture.md).
> **No runtime implementation or public API change in this document.**
>
> Parent design record: [SFLE F1 contracts](sfle-f1-contracts.md).
> Architecture: [SFLE](sfle.md).

## 1. D-F1.6 — Shared metadata without opening component validators

**Accepted direction:** Flex item properties are portable layout metadata
recognized on existing components; only an effective direct Flex formatting
context interprets them. The native widget contracts remain closed.

### 1.1 A three-way property partition

Do not simply add `flex_grow` to `TEXT_PROPS`, `BUTTON_PROPS`, etc.
Define a centralized, immutable, closed `FLEX_ITEM_PROP_NAMES` set.
A `LayoutPropsResolver` partitions the original PSX props into:

1. **Component props:** passed to the existing component-specific
   `ComponentContract.validate_builder` / `validate` unchanged.
2. **Layout metadata:** passed to a shared `FlexItemStyleValidator`,
   normalized into immutable `FlexItemStyle`.
3. **Unknown props:** rejected. No permissive `**props` fallback.

`key` remains VNode identity and `ref` remains component/native-ref metadata
under the established PSX contracts; neither is a CSS layout property.

~~~mermaid
flowchart TD
    A["VNode supplied props"] --> B["LayoutPropsResolver"]
    B --> C["Closed component props"]
    B --> D["Closed Flex item metadata"]
    B --> E["Unknown / ambiguous props"]
    C --> F["Existing ComponentContract validators"]
    D --> G["Shared FlexItemStyleValidator"]
    E --> X["Deterministic diagnostic/error"]
    F --> H["Native component adapter"]
    G --> I["Frozen FlexItemStyle"]
    I --> J{"Effective direct Flex item?"}
    J -- "Yes" --> K["SFLE layout input"]
    J -- "No" --> L["Inert; preserved with VNode"]
~~~

**Builder and renderer invariant:** both validation paths should delegate to
the same partitioner but preserve their existing error categories/messages
for native component props where backward compatibility requires them.
A second validation pass may use the normalized data rather than reparsing
public strings. Native factories must never receive flex-only metadata.

**Important design correction:** a component may already own a `width`,
`height`, `align`, `padding`, or `spacing` prop with different semantics.
These names **cannot be blindly subtracted** from component props or silently
reinterpreted as layout metadata. Canonical flex-only names remain
`flex_grow`, `flex_shrink`, `flex_basis`, `align_self`, and `order`.
Shared sizing properties should be introduced via a dedicated sizing
normalization layer and a documented migration plan, possibly using
`layout_width`/`layout_height` in the first release to avoid clashes.
Do not claim `width="50%"` works on `Image` or `Scroll` until their existing
validators and renderer semantics are explicitly migrated.

### 1.2 Proposed logical contracts

~~~python
@dataclass(frozen=True, slots=True)
class ResolvedProps:
    component_props: Mapping[str, object]
    item_style: "FlexItemStyle"  # immutable, validated


class LayoutPropsResolver(Protocol):
    def resolve(self, node_type: object,
                props: Mapping[str, object]) -> ResolvedProps: ...
~~~

The actual implementation must not create persistent duplicate mutable
property stores. Use immutable normalized snapshots and cache against
node/style revisions. Preserve the original VNode's public props for rerenders,
diffing and developer tooling.

### 1.3 Parent context and component boundaries

- Metadata may be supplied on an item regardless of current parent. Only
  direct children of a `Flex` formatting context become active flex items.
- A child of `Column` or `Row` keeps its existing behavior. A nested Flex
  establishes a *new* formatting context for its own direct children.
- A function component boundary is **not** a native widget. Metadata attached
  at that boundary must be retained as an explicit logical layout participant
  without copying the props to the first rendered child.
- A function component with a single root can map measurements to that root;
  a fragment/multiple-root result requires a specified, deterministic
  anonymous layout-box policy. **This remains an F1.6 subdecision**:
  defer multi-root boundary flex sizing with a capability error, or
  implement a faithful anonymous box mechanism.
- `order` affects computed visual position, not reconciliation order,
  hooks, keys, refs, focus order, or semantics. Keyboard/accessibility order
  cannot be silently reordered.
- Changed layout metadata invalidates layout calculations but should not
  recreate or update a native widget solely because `flex_grow` changed.
- Unknown names (`flex_gorw`) fail with a precise unsupported-prop error.
- Invalid numeric values (boolean, NaN, infinity, negative grow/shrink)
  fail before layout computation.
- A recognized but unsupported CSS feature must emit a capability diagnostic
  or error, **never** silently fall back to different geometry.

### 1.4 Full lifecycle

~~~mermaid
sequenceDiagram
    participant M as PSX Markup/Builder
    participant P as LayoutPropsResolver
    participant C as ComponentContract
    participant R as Reconciler
    participant L as SFLE coordinator
    participant N as Native adapter
    M->>P: VNode props
    P->>C: Component-only props
    C-->>P: Existing component validation
    P-->>R: VNode + normalized layout metadata
    R->>L: Mounted identity and effective Flex parent
    L->>L: Activate direct-child FlexItemStyle only
    R->>N: Native component props only
    L->>N: Computed geometry when changed
~~~

## 2. D-F1.7 — Typed length/value grammar

### 2.1 Separate *specified* from *computed* values

**Never** encode all special sizes as arbitrary strings or use `None` for
both `auto` and indefinite. Distinguish:

- **Specified value:** what the user declares (e.g. `"50%"`, `"auto"`, 24).
- **Normalized length expression:** immutable tagged value after validation.
- **Resolved numeric value:** produced only when CSS constraints permit it.
- **Definiteness:** independent semantic flag for available containing size.

Recommended canonical tag family:

| Kind | Example | Representation |
| --- | --- | --- |
| `PX` | `24`, `"24px"` | finite f64 logical CSS-like px |
| `PERCENT` | `"50%"` | finite fraction = 0.5; **unresolved** until eligible reference size |
| `AUTO` | `"auto"` | tag without numeric payload |
| `MIN_CONTENT` | `"min-content"` | intrinsic keyword tag |
| `MAX_CONTENT` | `"max-content"` | intrinsic keyword tag |
| `FIT_CONTENT` | `"fit-content"` | intrinsic sizing mode; exact CSS rules must be specified |
| `NONE` | `"none"` | valid for selected max constraints only |
| `NORMAL` | `"normal"` | property-specific keyword, e.g. gap; do not conflate with zero |
| `CALC` (deferred) | `"calc(100% - 16px)"` | typed expression AST; **not supported** by first release |

The tag is **property-dependent**: `none` must not be accepted as a
`flex_basis` value; `auto` is not a valid negative gap. Do not accept all
tags uniformly on all length-bearing properties.

### 2.2 Proposed immutable model

~~~python
class LengthKind(Enum):
    PX = "px"
    PERCENT = "percent"
    AUTO = "auto"
    MIN_CONTENT = "min-content"
    MAX_CONTENT = "max-content"
    FIT_CONTENT = "fit-content"
    NONE = "none"
    NORMAL = "normal"


@dataclass(frozen=True, slots=True)
class Length:
    kind: LengthKind
    value: float | None = None  # PX value or PERCENT fraction only


@dataclass(frozen=True, slots=True)
class AvailableSize:
    value: float | None
    definite: bool


@dataclass(frozen=True, slots=True)
class ResolvedSize:
    value: float | None
    definite: bool
    reason: str | None = None
~~~

These classes are **illustrative, not final Python code**. A production type
should be a discriminated union or enforce invariants in its constructors so
an `AUTO` length cannot carry a random numeric payload.
`AvailableSize(None, definite=True)` must be invalid. Even when an available
size is *numerically* zero, it may be definite; it must not be treated as absent.

If Rust is selected, the same schema maps to a tagged enum and compact f64
payload. Avoid passing Python objects or GUI handles into the native
computation loop.

### 2.3 Validation by property

| Property | Accepted initial kinds | Constraints |
| --- | --- | --- |
| `width`, `height` | PX, PERCENT, AUTO, intrinsic keywords as implemented | nonnegative definite dimensions |
| `min_width`, `min_height` | PX, PERCENT, AUTO, supported intrinsic | CSS automatic minimum behavior retained |
| `max_width`, `max_height` | PX, PERCENT, NONE, supported intrinsic | no negative length |
| `flex_basis` | PX, PERCENT, AUTO, supported intrinsic | zero distinct from auto |
| `gap`, `row_gap`, `column_gap` | PX, PERCENT when supported | nonnegative; percentages may be cyclic |
| `padding` | PX, PERCENT when supported | nonnegative; CSS percent reference dimension rules |
| `margin` | PX, PERCENT, AUTO when supported | negative fixed/percent margins permitted by CSS |

**Do not globally reject all negative length values:** CSS margins may be
negative, whereas width/gap/padding cannot. Validate per property.

Preserve differentiation between CSS `box-sizing: content-box` and
`border-box`, padding/border boxes and scrollable overflow. `margin` is
outside the border box. Adopt explicit CSS resolution rules for percentage
padding/margins and cyclic percentage gaps rather than naive axis-based
division.

### 2.4 Percentage resolution examples

~~~mermaid
flowchart TD
    A["Percent length: 50%"] --> B{"Property's reference size definite?"}
    B -- "Yes" --> C["Resolve against correct reference dimension"]
    B -- "No" --> D["Retain unresolved percent"]
    D --> E{"CSS property-specific fallback applies?"}
    E -- "Yes" --> F["Apply normative fallback"]
    E -- "No" --> G["Defer until constraints become definite"]
    C --> H["Numeric geometry input"]
    F --> H
    G --> I["Intrinsic measurement / second pass"]
~~~

For an item's `width="50%"` with a **definite** 400px containing width,
the percentage resolves to 200 logical px. The same percentage cannot
always be reduced to 200px if that reference size is indefinite.

A percentage `height="50%"` requires the appropriate definite containing
height according to CSS sizing rules. `flex_basis="50%"` uses the relevant
**main-axis** reference and may behave as content-based sizing when the
container main size is indefinite. The exact behavior of percentage
margins/padding/gaps is property-specific.

### 2.5 Markup and builder boundaries

- Python `24` and `24.5` normalize to `Length(PX, ...)`; reject bool
  despite bool being an int subtype.
- Python string `"50%"`, `"auto"`, `"min-content"` parse via the
  declarative value grammar. Invalid units such as `"12furlongs"` fail.
- Markup `width="50%"` is already a quoted string lexically, but the
  component/parent-aware validation rules must admit it.
- The current M4A parser accepts quoted strings and positive `{number}`
  literals. A negative literal or complex `{expression}` is **not**
  automatically supported; use quoted lengths or a future parser extension.
- No arbitrary `calc()` execution, `eval`, CSS cascade, or unbounded
  expression parsing in F1.
- Preserve raw specified style for documentation/inspector while passing a
  normalized immutable snapshot to the calculation engine.

## 3. Interoperation and conflicts that must be resolved

Current PSX component contracts include strict type requirements for certain
`width`/`height` props and dedicated layout-related props such as
`Column.align`, `Row.expand`, `Scroll.spacing`, and `Scroll.padding`.

**Historical design proposal (superseded by D-F1.10 for Row/Column):**

1. Keep existing component-owned props semantically unchanged outside SFLE.
2. Introduce shared `flex_*`, `align_self`, and `order` as metadata with
   no collisions.
3. Determine whether to introduce namespaced `layout_width` etc. **temporarily**
   or migrate existing `width`/`height` contracts deliberately while
   preserving old valid inputs. This is the central remaining F1.7 choice.
4. Use the parent's measured *outer box* for layout and the child's native
   preferred dimensions as its intrinsic content. Do not silently equate
   `Scroll.height` viewport semantics with arbitrary Flex item sizing.
5. **Superseded:** the earlier proposal to preserve Row/Column native
   placement is withdrawn. D-F1.10 requires eliminating these components
   from the public API and removing their redundant layout algorithms.

## 4. Rust and conformance implications

The typed length schema must be independent of Python-specific string
interpretation. Feed SFLE normalized tagged values, definite constraints,
immutable measured sizes and explicit node order in a **single batched layout
request** where practical.

Conformance fixtures must cover `auto` vs 0, 0% vs 0px, min-content,
max-content, indefinite percentage references, negative margins, nonnegative
gaps, min/max conflicts, wrapping, DPI rounding and nested constraints.
The pure math engine must never assume native widget sizes are exact browser
font metrics.

## 5. Decision history (ratified in canonical contract)

1. **D-F1.6.A — Component boundaries:** approve logical flex item boxes for
   single-root components; decide whether multiple-root components are
   rejected in v1 or modeled by an anonymous containing box.
2. **D-F1.6.B — Metadata outside Flex:** accept and validate but leave inert
   (recommended), rather than rejecting based on current parent.
3. **D-F1.6.C — Prop split:** centralized closed resolver plus existing
   component validators; never pass flex metadata into native factories.
4. **D-F1.7.A — Size prop collision:** staged migration of existing
   `width`/`height` or explicit `layout_width`/`layout_height`
   namespace for first delivery.
5. **D-F1.7.B — Length grammar:** tagged PX / PERCENT / AUTO / intrinsic
   keywords with property-specific allowed kinds; defer `calc()`.
6. **D-F1.7.C — Box model:** define margin/padding/border and
   `box_sizing` handling; CSS-compatible constraints by property.
7. **D-F1.7.D — Percentage and definiteness:** property-specific reference
   rules; retain unresolved values until CSS permits resolution.

These subdecisions are ratified in [the canonical contract](sfle-f1-box-model.md):
only single-root functional boundaries, validated/inert metadata outside Flex,
centralized prop splitting, namespaced layout dimensions, tagged lengths,
CSS box-model semantics and deferred property-specific percentage resolution.
This historical proposal is superseded where it conflicts with the ratified record.
No SFLE executable code or tests have been added.
