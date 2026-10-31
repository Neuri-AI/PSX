
# Portable Image

`Image` displays a bitmap image loaded from a local file with the same public
contract in every renderer. It mounts a `QLabel` with a scaled `QPixmap`, a
`ttk.Label` with a `PhotoImage`, or a Kivy `Image` widget, and preserves that
widget during compatible updates. It has no events of its own.

| Property | Type | Default |
| --- | --- | --- |
| `source` | Non-empty `str` (local file path) | Required; first positional argument |
| `fit` | `"contain"`, `"cover"`, `"fill"`, or `"none"` | `"contain"` |
| `width` | Positive `int` or `None` | `None` (natural width of `source`) |
| `height` | Positive `int` or `None` | `None` (natural height of `source`) |
| `alt` | `str` | `""` |
| `enabled` | `bool` | `True` |
| `key` | `str`, `int`, or `None` | `None` |
| `ref` | PSX ref or `None` | `None` |

`source` is a local filesystem path. The idiomatic call site resolves it
through the applications resource helper so the same code works in
development and in a packaged build:

```python
from qyro import get_resource

logo = get_resource("images/logo.png")
```

When neither `width` nor `height` is provided, the widget takes the images
natural size. When only one axis is provided, the other is computed to
preserve the sources aspect ratio. When both are provided, the widget is
fixed to exactly that size and `fit` decides how the image is drawn inside
it.

`fit` controls the mapping between the sources aspect ratio and the
widgets rectangle:

| Value | Behaviour |
| --- | --- |
| `"contain"` | Scale the image to fit entirely inside the widget, preserving aspect ratio. Empty space is distributed evenly on both sides (letterbox/pillarbox). |
| `"cover"` | Scale the image to cover the whole widget, preserving aspect ratio. Overflow is clipped symmetrically. |
| `"fill"` | Stretch the image to the widgets rectangle without preserving aspect ratio. |
| `"none"` | Draw the image at its natural size, centered in the widget. No scaling is applied. |

`fit` only matters when both axes are fixed by `width` and `height`, or when
the widgets target rectangle differs from the sources natural aspect ratio.
If the widget size matches the sources aspect ratio, all four values produce
the same visual result.

`alt` is a best-effort description of the image. Qt maps it to the widgets
accessible name; Tkinter does not have a native equivalent and the value is
currently ignored; Kivy does not have a native equivalent either. It is
documented so callers can provide accessibility metadata without it being
silently dropped in the future. When the image fails to load, the renderer
may fall back to displaying `alt` as plain text.

`enabled=False` disables the widget at the native level. Since `Image` has no
interactive behaviour, the visible effect depends on the theme.

The renderer caches the loaded image by `source`. Changing only `fit`,
`width`, `height`, `alt`, or `enabled` re-uses the cached bitmap and only
recomputes the target rectangle. Changing `source` reloads the file.

```python
from psx import Column, Image, Text
from qyro import get_resource

logo = get_resource("images", "logo.png")

Column(
    Text("Logo (contain)", font_size=18),
    Image(logo, width=200, height=80, fit="contain"),
    Text("Logo (cover)", font_size=18),
    Image(logo, width=200, height=80, fit="cover"),
    Text("Logo (fill)", font_size=18),
    Image(logo, width=200, height=80, fit="fill"),
    Text("Logo (natural)", font_size=18),
    Image(logo),
    spacing=12,
    padding=20,
)
```

```python
psx("""
    <Column spacing={12} padding={20}>
      <Text font_size={18}>Logo (contain)</Text>
      <Image source={logo} width={200} height={80} fit="contain" />
      <Text font_size={18}>Logo (cover)</Text>
      <Image source={logo} width={200} height={80} fit="cover" />
      <Text font_size={18}>Logo (fill)</Text>
      <Image source={logo} width={200} height={80} fit="fill" />
      <Text font_size={18}>Logo (natural)</Text>
      <Image source={logo} />
    </Column>""",
)
```

## HTML-style `<img>` in PSX Markup

The lowercase `img` alias follows HTML naming and uses **`src`**, not the
internal `Image.source` attribute. Use either a literal resource path or
a normal PSX lexical expression:

```python
from velto import VeltoContext
from velto.ui import psx
from velto.runtime import get_resource

class App(VeltoContext):
    def render(self):
        logo = get_resource("images/logo.svg")
        return psx("""
            <div>
                <img src="images/logo.svg" width="200"/>
                <img src={logo} width="25vw" height="50%"/>
            </div>
        """)
```

Both forms lower to the existing native `Image` VNode. Literal relative
`src` paths are resolved through Qyro's `get_resource` when that resource
exists, including resources extracted from frozen packages. A pre-resolved
absolute path (such as `src={get_resource(...)}`) is preserved as-is.
Standalone PSX retains ordinary relative filesystem paths.

The HTML sizing attributes accept positive unitless numbers (CSS pixels),
`px`, `%`, `vw`, and `vh`. Percentages remain relative to the
containing layout, while viewport lengths are resolved against the
current Cinnamon viewport on resize:

| Attribute | Example | Meaning |
| --- | --- | --- |
| `width="200"` | 200 | 200 logical CSS pixels |
| `width="200px"` | 200px | 200 logical CSS pixels |
| `width="50%"` | 50% | Half of the containing block's available width |
| `width="25vw"` | 25vw | One quarter of the window viewport width |
| `height="30vh"` | 30vh | 30% of the window viewport height |

Viewport/percentage dimensions require a Cinnamon-managed layout; older
unmanaged native layouts do not resolve a percentage against their parent.
The uppercase `<Image source={...}/>` and Python `Image(source, ...)`
retain their existing native property contract. The `img` alias rejects
the legacy `source` attribute to avoid exposing two public spellings.

### CSS width and height are layout dimensions

HTML-style `<img>` also respects stylesheets, not just XML-style width and
height attributes. For example:

```css
img {
    width: 200px;
}
```

```jsx
<img src="images/logo.svg" />
```

When CSS specifies only `width`, Cinnamon resolves the other auto axis from
the image's **native decoded intrinsic aspect ratio**, including within flex
columns. This means the following heading starts after the *used image height*
rather than after the resource's original unscaled height. A CSS-only
`height` works symmetrically. Percentage and viewport widths are reevaluated
with the current containing block/viewport.

When CSS specifies both axes, they are honored independently and `fit`
determines drawing within that rectangle. No renderer may change the
declarative `Image.width` or `Image.height` props as a workaround.
The same immutable aspect hint is passed to Qt, Tkinter, Kivy and both
Python/Rust Cinnamon implementations. Undecodable resources without
intrinsic dimensions do not produce a guessed aspect ratio.

## Supported formats and dependencies

`source` accepts whatever the underlying toolkit can decode. Common cases:

- **Qt**: all formats Qt was built with (`PNG`, `JPEG`, `BMP`, `GIF`, `SVG`
  through `QtSvg`, `WEBP`, etc.). No extra dependency is required.
- **Kivy**: all formats Kivys image providers can load (`PNG`, `JPEG`,
  `GIF`, `BMP`, `SVG` when `svg` is installed). No extra dependency is
  required for the common formats.
- **Tkinter**: native `tk.PhotoImage` supports only `PNG`, `GIF`, `PPM`, and
  `PGM`, and cannot scale by arbitrary factors. For `JPEG`, arbitrary
  scaling, or `width`/`height` overrides, install `Pillow`. SVG decoding
  needs a separate SVG-capable provider; Pillow alone does not decode SVG. Without Pillow,
  the adapter falls back to displaying the image at its natural size and
  ignores `fit`, `width`, and `height`.

When a source format is not supported by the current renderer, the failure is
silent for the widget (empty label) but may emit a warning at the toolkit
level. Checking the source path resolves to an existing file before rendering
avoids the common mistake of a `get_resource` call that returned a path to a
missing asset.

## Sizing and layout interaction

`Image` is a leaf. It does not accept children. Its size inside a layout is
governed by `width` and `height`:

- Both `None`: the widget reports its natural size, and the parent layout
  gives it exactly that. `expand=True` on the parents per-child tuple can
  override this and stretch the widget.
- Only `width` set: the height is derived from the source aspect ratio.
- Only `height` set: the width is derived from the source aspect ratio.
- Both set: the widget is fixed at exactly that size.

When the widget is stretched by the parent to a size different from the
sources aspect ratio, `fit` decides how the image is placed inside the
larger rectangle. See the table above.

## Interaction with `get_resource`

`get_resource(*segments, required=True)` from `qyro` resolves a resource path
through the applications public resolver, including frozen-mode behaviour.
It returns a `str`. Pass that `str` directly to `Image(source=...)`.

Because `source` is a plain string, `Image` does not know how the path was
obtained and does not attempt to resolve it further. If the path is relative,
it is interpreted relative to the current working directory of the process,
not to the module that contains the `Image` call.

## Unknown properties

Unknown properties and invalid property values raise `RendererCapabilityError`.
Builders, markup, and native renderers enforce this same contract. Each
update applies the current portable properties directly; removing an optional
property returns it to the portable default above. No native defaults are
captured.

Use the separate `Native(...)` API for framework-specific image widgets,
remote URLs, bytes/base64 sources, or any feature not covered by this
contract. References and keys retain their existing PSX lifecycle behavior.
