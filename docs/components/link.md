# Link

A portable text link with two **mutually exclusive** activation modes:
external navigation via `href`, or a Python `on_click` callback for future
PSX Router integration. The component does not depend on a router or Qyro.

## Contract

- **Role:** interactive leaf with inline text
- **Child policy:** `text-only`, with `label` as the content property
- **Children:** only text and text interpolations, never VNode children
- **Activation:** one browser navigation or one `on_click()` callback per user action
- **Update:** keep the native widget and update its props without opening a browser or invoking callbacks
- **Unmount:** release event connections/bindings; do not navigate

| Prop | Type | Default |
| --- | --- | --- |
| `href` | `str \| None` | `None` |
| `label` | `str` | `""` |
| `on_click` | `Callable[[], None] \| None` | `None` |
| `color` | `#RRGGBB \| None` | `None` |
| `underline` | `bool` | `True` |
| `enabled` | `bool` | `True` |
| `key`, `ref` | Runtime-managed | `None` |

The default visible color is `#2563EB`. When `href` is provided, it must
be an absolute HTTP(S) URL (e.g., `https://example.com`). Relative paths
and router paths must use `on_click` for now. An active `href` and an active
`on_click` at the same time raise `RendererCapabilityError`, including on
updates. Neither is allowed to silently take precedence over the other.

## Markup and Python builder

```python
from psx import Link, psx

external = Link("PSX repository", href="https://github.com/Neuri-AI/PSX")

def render():
    def open_settings():
        router.navigate("/settings")  # Future router API, not implemented yet.

    return psx("""
        <Column spacing={12}>
            <Link href="https://github.com/Neuri-AI/PSX">
                View on GitHub
            </Link>
            <Link on_click={open_settings} color="#8B5CF6"
                  underline={False}>Settings</Link>
        </Column>
    """)
```

The `router` reference above is illustrative only; it must be provided by
the application once a routing system is implemented. `psx()` resolves local
callbacks automatically, without an explicit `scope`.

## Renderer mechanisms

| Backend | Mechanism | Technical rationale |
| --- | --- | --- |
| Qt | Custom leaf adapter around `QPushButton` | Native focus/keyboard support, hyperlink styling, external navigation dispatch vs EventSlot binding |
| Kivy | Custom leaf adapter around `Button` | Native touch events, text markup, dynamic text measurement, external navigation dispatch vs EventSlot binding |
| Tkinter | Custom leaf adapter around `tk.Label` | Mouse/keyboard `bind` events, cursor/focus and owned font |
| Headless | Generic adapter | No browser side effect; validated properties, stable event slot |

The standard library `webbrowser.open()` performs external navigation for
GUI adapters. Headless only records the component and event slots.

## Manual DX checklist

- Confirm both `<Link>Text</Link>` and `Link(label="Text")` forms.
- Verify external HTTP(S) navigation using `href` and no callbacks.
- Verify `on_click` fires once and never opens a browser.
- Verify the mutually-exclusive rule during construction and prop updates.
- Verify disabled links do not activate and updates never navigate.
- Verify color, underline, label updates and stable native widget identity.
- In Kivy, verify links align to the left within a default stretching `Column`, rather than centering in the window.
- Verify pointer and keyboard activation where supported.
- Verify replacing event callbacks and unmounting without stale handlers.

Automated tests are intentionally deferred to the end of the component phase.
