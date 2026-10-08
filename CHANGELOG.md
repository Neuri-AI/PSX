# Changelog

## 1.0.0a1 — Alpha release candidate

- Declarative VNode core, keyed reconciliation, hooks, effects, refs, and a
  deterministic headless renderer.
- PSX markup plus the M4B static lexical transform.
- Renderer adapters for PySide6, PyQt5/PyQt6, Tkinter, and Kivy.
- Pydux and Qyro integrations, optional development hot reload, and native
  widget interoperability through `Native(...)`.
- Alpha packaging metadata, documented compatibility boundaries, CI, and a
  dependency-free reconciliation benchmark.

Known limitations: final Tkinter and Kivy graphical smoke tests require a
logged-in desktop session; native widget controls intentionally remain
backend-specific; advanced specialized tags such as `Video` and `WebView` are
not portable primitives yet.
