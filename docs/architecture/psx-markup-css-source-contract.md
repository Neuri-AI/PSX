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
decrypted bytes without writing the plaintext to disk. The Qyro `release` runtime already implements authenticated protected resource bundle
loading: `.velto/resources.pak` is decrypted by `ProtectedResourceBundle`,
ordinary resource files are extracted to a temporary directory, and
`FileSystemResourceAdapter` exposes them through the existing `get_resource()`
filesystem-path API. The CSS reader can read those returned paths normally:
no extra `.pak` decryption API is required for the shipped protected-resource
workflow. This does **not** claim per-file in-memory CSS decryption or that
protected ordinary CSS never touches disk. The source-integration changes to
Qyro `VeltoContext` target its `release` branch, not the stale `main` facade.

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


## Global CSS across PSX native components (P1.4.6)

The CSS source is resolved once for the PSX tree, before backend dispatch.
Builtin PascalCase components (`Text`, `Button`, `Input`, `TextArea`,
`Checkbox`, `Radio`, `Select`, `Link`, `Badge`, `SpinBox`,
`Flex`, `Grid`, `GridItem`, `Box`, `Scroll`, `Slider`,
`Spacer`, `Divider`, `Image`, `ProgressBar`, `RadioGroup`,
`Switch`) can carry CSS `class`/`class_name`, `id`, and `style`
attributes in markup without leaking those keys into native props.

Builtin PascalCase controls and their HTML-like aliases share lowercase type
selectors, e.g. `button` matches both `<Button>` and `<button>`.
The `*` selector now matches across builtin and semantic element targets,
with CSS specificity `(0, 0, 0)`; normal type, class, ID, and inline
precedence remain unchanged. Inheritable properties flow from the parent
through the same computed style tree. Implicit text content is *not* a CSS
element: it inherits its parent's typography and does not re-match `*`.

Builtin VNodes constructed in Python, without markup CSS metadata, also
participate in type/universal matching under their lowercase builtin tag.
Custom lexical components are not automatically treated as a same-named
builtin. CSS computation is backend-independent; supported paint/geometry
properties must still be projected by the corresponding Qt, Tkinter or Kivy
adapter. The existence of a computed CSS property never guarantees that
an arbitrary native widget can render it.
