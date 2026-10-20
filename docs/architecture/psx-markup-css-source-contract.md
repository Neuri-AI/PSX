# Scoped CSS sources for PSX Markup

**Implementation branch:** `feature/universal-box-model-and-styling` (PR #48).  
**Scope:** stylesheet-to-VNode association and immutable computed style metadata, not native CSS painting or Cinnamon geometry.  
**Compatibility:** legacy PascalCase widget properties and native renderer contract remain unchanged.

## Public syntax for the initial, bounded CSS binding

The author of a PSX template may attach one stylesheet source to a render:

```python
from psx import psx

root = psx(
    '<div class="panel"><span style="color: #fff">Hello</span></div>',
    stylesheet=".panel {width: 50%; background-color: #123}",
)
```

Only the explicitly registered lowercase HTML-like aliases accept `class`,
`class_name`, `id`, and `style` metadata. The preferred spelling is
`class`; `class_name` is an equivalent alternative. Supplying both is an error.
`class` is a whitespace-separated token list, `id` a single CSS identifier,
and `style` either validated declaration text or a mapping of property names to
typed values (in the supported PSX expression syntax).

These fields are **never sent to native widget constructors**, never assigned to
legacy `props`, and never reinterpret existing `width`, `font_size`,
`layout_width` or other widget-owned parameters. Existing PascalCase tags
retain their established public contracts. Source markup can supply a stable
`key` without alteration.

The compiled M4A and M4B template paths both carry stylesheet arguments;
expression-compiled templates preserve source metadata through the expressive
element constructor. The style resolver produces immutable `css_computed`
snapshots on VNodes, as well as detached snapshots for keyed diffing. There is
no global stylesheet registry or native handle retention.

## Precedence

For a supported property, the order is:

1. CSS initial value.
2. Inherited value if the property is inheritable.
3. Matching stylesheet declarations (specificity, source order).
4. Validated inline declaration.

Existing native component props are **not part of this CSS cascade**. Converting
a computed property into native behavior is reserved for separately certified
geometry and renderer capability ports.

## Explicit unsupported behavior

- CSS computed dimensions **do not yet change Cinnamon geometry**.
- CSS colors, backgrounds, font values and border values **do not yet paint native widgets**.
- The approved CSS parser currently supports simple type/class/ID compound
  selectors. Descendant selectors, pseudo-classes, `!important`, arbitrary
  CSS functions, `@media`, and browser-wide inheritance are not promised.
- The existing responsive `Grid` is not replaced by CSS Grid.
- Native/custom components do not acquire new style props by implication.
- Failed or unknown declarations produce an explicit exception rather than
  being silently accepted or interpreted as a zero length.

## Verification and acceptance

Behavior-specific coverage is provided by `tests/test_markup_css_binding.py`,
`tests/css/test_tree.py`, and the contract-source public census in
`tests/test_css_markup_census.py`. The public census uses assertion-bound
JUnit properties from `tests/certification/public_behavior_census.py`.
Each claim must be tied to executed tests and an exact successful GitHub Actions
SHA. Native readback is **not applicable** to the source-association stage:
no native styling, geometry, or new native event is advertised.

The CSS source stage must not be conflated with the subsequent Cinnamon geometry,
native paint, incremental performance, and release certification work.
