# PSX CSS Sources and Resource Integration

**Branch:** `feature/universal-box-model-and-styling`. This document describes
the CSS source-binding layer, not native CSS painting or Cinnamon geometry.

## Public source declarations

Stylesheet source text is **not** a public `psx(stylesheet=...)` argument.

Markup declarations use a resource-only tag:

```python
from psx import psx

root = psx("""
    <link rel="stylesheet" href="styles/main.css" />
    <div class="container" style={{"color": "#fff"}}>
        <h1>Hello Velto!</h1>
    </div>
""")
```

The `link` tag is not a native widget and has no children. It requires the
exact local CSS source attributes `rel="stylesheet"` and `href="*.css"`.
Unsupported attributes and remote URLs fail closed.

App-level sources may be declared as `stylesheets = ["styles/reset.css"]`
on `VeltoContext` (Qyro's `ApplicationContext` facade), or in Qyro project
settings under `css.stylesheets`. Qyro wraps the authored `render()` method
without requiring a custom constructor, binds an application-scoped context,
and reads resources through its documented `get_resource()` path API.
Explicit class resources follow configured global resources and precede
in-markup links. Each app render has an isolated source context.

For users without Qyro, PSX reads relative CSS paths from the project working
directory; advanced embedders can inject a resource reader using
`psx.css.context.scoped_css_resources(..., resolver=...)`. The parser is
independent of Qyro. Resolver results may be UTF-8 text or bytes, allowing
protected resources to be integrated by a resource provider capable of reading
decrypted bytes without writing the plaintext to disk. The currently verified
Qyro `get_resource()` entrypoint returns a filesystem path; support for
Qyro protected `.pak` content requires its separate read API and is **not
claimed to be implemented** by the filesystem adapter.

## CSS imports

A CSS file can include leading `@import "./buttons.css";`. Imports are
resolved relative to the importing file; the loader enforces root confinement,
detects circular references and rejects malformed or late imports. Imported
rules enter the cascade before rules in the importer, and global source
declarations enter before markup-local link sources.

CSS `style={{...}}` and literal declaration text remain inline properties.
Type, class and ID selectors, supported property grammar, specificity, source
order and inheritance use the existing CSS Core resolver.

## Runtime boundaries

These source declarations produce immutable computed-style metadata on PSX
VNodes, separate from native widget props. This increment does **not** imply
that CSS widths change Cinnamon geometry or CSS colors/fonts are painted by
Qt/Tkinter/Kivy; those are subsequent work. No CSS Grid, remote URLs,
transitions, animation or browser stylesheet APIs are promised.

Hot-reload dependency tracking and invalidation are later work. Source manager
should retain ordering and source-relative references so a watcher can reload
changed documents without resetting component state.

## Verification

Relevant suites: `tests/css/test_sources.py`,
`tests/css/test_context.py`, `tests/test_markup_css_binding.py`,
`tests/test_css_markup_census.py`, and Qyro's
`tests/test_css_stylesheet_scope.py`. Public behavior census receipts must
reflect actual executed GitHub Actions jobs at the exact source commit;
absence of native paint/geometry certification is intentional.
