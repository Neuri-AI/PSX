# WebView markup API

The built-in Qt WebView can be declared as `<WebView />` or `<Webview />`.
Use `src` for the document URL. The former `url` spelling remains accepted
for compatibility, but not alongside `src`. `html` is mutually exclusive
with `src`.

```jsx
<link rel="stylesheet" href="css/styles.css" />
<WebView class="browser" src="https://example.com" />
<Webview src="about:blank" width="400px" height="50vh" />
```

```css
.browser {
    width: 75vw;
    height: 60%;
}
```

PSX resolves CSS classes and inline styles into immutable computed styles.
Cinnamon, rather than Qt widget setters, owns geometry; dimensions accept
`px`, `%`, `vw`, and `vh` when supported by the layout context.
Percentage dimensions are relative to their containing block and require
a definite reference size. The programmatic `layout_width` and
`layout_height` properties remain supported for compatibility.

This native Qt WebView requires PySide6 QtWebView. Unsupported backends
must report a capability error rather than silently replacing the browser.
