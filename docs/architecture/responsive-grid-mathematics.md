# Responsive Grid mathematical solver — row membership contract

**Implementation status:** first G2 increment in review; tests and CI must pass before closure. The previously certified G1 metadata/fail-closed implementation is the baseline. This is an internal solver specification, not public Grid mount support.

## Pure input and fixture format

`tests/fixtures/grid_row_packing.json` defines schema version `1`, a `cases` array, and each case's descriptive `name`, `items` and either `rows` or `error: "invalid"`. Each item has a stable nonempty `id`, `span` (1–12 or `"auto"`), optional `offset` (0–11), and optional signed integer `order`. Expected rows are arrays of `{id, start, span}` records in **logical twelve-column units**; these are *not* pixel rectangles. Both implementations consume this exact fixture without backend-specific reinterpretation.

Locations:
- Python reference/fallback: `psx/sfle/grid_math.py`, `pack_grid_rows`.
- Rust primary: `rust/sfle-core/src/grid_math.rs`, `pack_grid_rows`.
- Executable fixture assertions: `tests/sfle/test_grid_math.py` and the Rust kernel's unit tests. The Rust suite also invokes Python fixtures to prevent false single-language GREEN.
- CI: `scripts/ci/impact.py` routes these production paths, tests and fixtures to `sfle` + `rust`; pure docs-only changes select no product suites. `tests/test_ci_impact.py` proves these routes.

## Deterministic line membership / mixed auto and explicit items

1. Validate all item inputs and globally unique IDs before calculating anything. Never silently clamp or coerce a boolean into an integer. An explicit `span + offset > 12` fails.
2. Stable-sort items by `order`, retaining declaration order for equal values. This only affects visual placement, not identity.
3. Process items left to right without backtracking into an earlier finalized row. Reserve all explicit spans plus *logical offsets*, irrespective of whether the item has an auto span.
4. Each row's auto items are guaranteed **strictly positive** logical space. If adding an explicit item would consume the final available units reserved for preceding autos, finalize the existing row first, even if the explicit item could otherwise fit the row exactly.
5. An auto item after an exact twelve-column reservation likewise starts a fresh row. Conversely, auto items may share spare capacity on a partly explicit row. Pending autos are not treated as zero during greedy admission.
6. On row finalization, calculate `auto_share = (12 - sum(explicit spans + offsets)) / number_of_autos`. In appearance order, advance the logical cursor by an item's offset, record its `start`, then advance by the explicit span or `auto_share`.
7. The first row is not emitted when there are no items. A partial row has no artificial trailing stretch if it contains no autos.
8. Any invalid input aborts with a non-successful return: `GridPackingError` in Python or `GridPackingError::InvalidInput` in Rust.

**Frozen ambiguous example:** `[auto, 8, auto, 6]` becomes **row 1 `[auto(2), 8, auto(2)]`**, then **row 2 `[6]`**. The later explicit 6 cannot fit once 8 has been reserved, and must not retroactively move either earlier auto item.

Other canonical cases:
- `[12, auto, auto]` → `[[12], [auto(6), auto(6)]]`
- `[auto, 12]` → `[[auto(12)], [12]]`
- `[8, auto, auto]` → `[[8, auto(2), auto(2)]]`
- `[(4, offset 2), (6, offset 0)]` → `[[start 2/span 4, start 6/span 6]]`
- `[auto offset 1, auto offset 2]` → `[[start 1/span 4.5, start 7.5/span 4.5]]`

## Next math increments — do not confuse with this one

- **Pixel projection and gutters:** given a definite Grid content-box width, reduce usable physical pixel width by actual between-item column gaps; never count a logical offset as a rendered widget/gap. Use the existing signed saturating 1/64px SFLE `LayoutUnit` for deterministic projected edges. Preserve float ratios until the agreed edge-projection boundary; test non-divisible widths.
- **RTL and cross axis:** apply logical-to-physical x reversal, row heights, row gaps, min/max constraints and explicit overflow reporting, with the Rust kernel authoritative and Python numerically equivalent.
- **Runtime hookup:** G2 eventually supplies math to the renderer-neutral layout engine, but native widget geometry and mount lifecycle are G3, with responsive reflow and nesting under G4.
- **Error/precision review:** document saturation and overflow/readback contract, cyclic widths, deterministic fixture stress and Rust–Python true runtime differential. Shared fixture agreement alone is not a full native differential certification.

**Census applicability:** This increment adds no public props, user events, methods or interactions. The G1 Grid/GridItem public census still applies unchanged; no fictitious native Grid receipt may be issued before G3. Add new cases and executed receipts whenever later increments change an observable public contract.
