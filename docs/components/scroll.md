# Scroll

Portable multi-child viewport with native scrolling in Qt, Kivy and Tkinter.

## Contract

- **Name:** `Scroll`; `child_policy="multiple"`
- **Children:** zero or more PSX VNodes; nested `Scroll` is supported
- **Content container:** renderer-owned; not a public VNode
- **Events:** none in v1
- **State:** native scroll offsets are preserved across compatible reconciliations
- **Viewport:** constrained by its parent or optional finite positive `width` and `height`
- **Cross-framework goal:** overlay scrollbars must not reserve layout space

| Property | Type | Default | Valid values |
| --- | --- | --- | --- |
| `direction` | `str` | `"vertical"` | `vertical`, `horizontal`, `both` |
| `content_direction` | `str` | `"vertical"` | `vertical`, `horizontal` |
| `scrollbar` | `str` | `"auto"` | `auto`, `always`, `hidden` |
| `width` | `int \| float \| None` | `None` | Positive finite number or `None` |
| `height` | `int \| float \| None` | `None` | Positive finite number or `None` |
| `spacing` | `int` | `0` | Nonnegative integer |
| `padding` | `int \| tuple` | `0` | Nonnegative integer, pair or four-tuple |
| `enabled` | `bool` | `True` | Boolean |
| `key`, `ref` | runtime metadata | `None` | PSX-managed |

`direction` determines allowed scroll axes; `content_direction` is the
layout direction of *direct children*. For complex structures, put a
`Column`, `Row` or another container inside Scroll.

### Python builder

```python
from psx import Scroll, Text

view = Scroll(
    Text("Introduction"),
    Text("More content"),
    direction="vertical",
    height=320,
    spacing=12,
    padding=(12, 16),
)
```

### Markup

```python
from psx import psx

def render():
    return psx("""
        <Scroll direction="horizontal"
                content_direction="horizontal"
                height={180}
                scrollbar="auto"
                spacing={12} padding={8}>
            <Image source="one.png" width={200} />
            <Image source="two.png" width={200} />
            <Image source="three.png" width={200} />
        </Scroll>
    """)
```

### Nested scrolling

```python
from psx import psx

def render():
    return psx("""
        <Scroll direction="vertical" height={500}>
            <Column spacing={16}>
                <Text>Overview</Text>
                <Scroll direction="horizontal"
                        content_direction="horizontal"
                        height={160} spacing={8}>
                    <Image source="one.png" width={200} />
                    <Image source="two.png" width={200} />
                </Scroll>
                <Text>Details</Text>
            </Column>
        </Scroll>
    """)
```

The intended input policy is **inner first**: the nearest viewport consumes
scrolling until it reaches a boundary; remaining input may scroll its parent.
Toolkit event dispatch differs. Verify nested wheel/trackpad behavior for each
native backend during manual DX rather than assuming exact equivalence.

## Lifecycle and backend mechanisms

- **Core:** `SCROLL_PROPS`, `SCROLL_DEFAULTS`, `SCROLL_CONTRACT`,
  `validate_scroll_props`, `Scroll(...)` and markup registration.
- **Shared:** `psx/renderers/components/scroll.py` normalizes props,
  allowed axes, padding and bounded delta consumption.
- **Qt:** `QScrollArea` containing a renderer-owned QWidget and box layout.
  Native scrollbars are hidden from layout; superimposed indicator
  QScrollBars track native positions. Wheel events are ignored at boundaries
  so enclosing views may handle them. Reorientation updates box layout in
  place without replacing child widgets.
- **Kivy:** `ScrollView` containing a managed `BoxLayout`; minimum content
  dimensions follow children and viewport. Wheel and trackpad input are
  handled by Kivy's own ScrollView to avoid competing scroll offset updates;
  the previous macOS-specific direction inversion and manual fallback were
  removed after reports of rebound/flicker. The adapter also avoids
  overriding `on_scroll_start`: Kivy's wheel-event direction and `scroll_y`
  boundary convention must be handled by its native `ScrollView`. A prior
  custom boundary check blocked two-finger scrolling unless the user dragged
  with the trackpad pressed. Native indicators are drawn
  over the viewport. Cross-axis hints and parent stretch constraints can
  affect sizing, so validate on all relevant layout configurations.
- **Tkinter:** `Canvas` plus frame in `create_window`; PSX creates children
  with that inner frame as their real Tk master, passing a typed TkHandle
  wrapper into renderer creation (never a proxy namespace). Visual thumb indicators are
  drawn inside Canvas. Aqua/macOS wheel and trackpad deltas are normalized
  separately from Windows-style 120-unit wheel notches, with pixel movement
  and remainder-aware nested handoff. The adapter only reapplies scrollregion
  when the measured content/viewport extent changes. Per-widget wheel callbacks inspect enclosing Scroll
  frames without `bind_all` or global bindings.
- **Headless:** contract validation, child ordering and lifecycle records.

`scrollbar="hidden"` suppresses indicators but does not disable content
scrolling. `enabled=False` prevents interactive input.

## Manual developer-experience acceptance checklist

No automated tests are added or run for this component phase.

- [ ] Render empty Scroll, a single child, and multiple direct children
- [ ] Exercise `vertical`, `horizontal` and `both` with real overflow
- [ ] Test `content_direction` independently from allowed scroll axes
- [ ] Verify auto/always/hidden indicators overlay instead of resizing content
- [ ] Check explicit width/height and parent-constrained viewports
- [ ] Check nested Scroll wheel/trackpad input and limit handoff
- [ ] On macOS, verify two-finger trackpad scrolling **without clicking or
  holding down the trackpad**, separately from a
  physical mouse wheel, including natural scrolling enabled/disabled;
  backend/SDL2 versions may expose different events
- [ ] Verify Tkinter creates normal Text/Column children within Scroll without
  foreign-handle TypeError
- [ ] On macOS Tkinter, compare two-finger scroll travel to native applications;
  confirm no near-zero delta slowdown or scroll position jump at boundaries
- [ ] Check Windows physical wheel sensitivity and nested overflow handoff
- [ ] Confirm content and widget identity survive keyed add/remove/reorder
- [ ] Confirm offsets survive normal rerenders and clamp on content shrink
- [ ] Change direction, padding, spacing, dimensions and enabled state live
- [ ] Check wheel handling over buttons, inputs, labels and nested containers
- [ ] Verify native teardown does not retain timers, widgets or event handlers
- [ ] Compare Qt bindings, Kivy and Tkinter on desktop with mouse and trackpad
- [ ] Verify text, images and nested Column/Row do not become unexpectedly stretched

## Known manual-DX review points

Exact overlay styling, drag-to-scroll thumbs, precise partial-delta chaining
and toolkit-specific sizing for unbounded parent constraints require hands-on
validation and may need follow-up refinement. These are not claimed verified
by code publication alone.
