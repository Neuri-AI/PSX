# M9 — Kivy & Qt Variants

**Status:** implemented for the validated initial subset. PyQt6 and PyQt5 implement the same initial
`Row`/`Column`/`Text`/`Button` renderer contract as PySide6, including queued
UI scheduling, stable event slots and keyed widget reconciliation. They are
validated in separate subprocesses because Qt bindings must never share one
process. Select them with `App(..., renderer="pyqt6")` or `"pyqt5"`.

Kivy 2.3.1 is installed in the `osx310` environment. `KivyRenderer` maps
`Column`/`Row` to `BoxLayout`, `Text` to `Label`, and `Button` to Kivy Button;
it uses `Clock.schedule_once` for UI scheduling and preserves child order despite
Kivy's reverse `children` storage. Select it with `App(..., renderer="kivy")`.
The automated native smoke test is skipped only when the macOS host has no SDL
or Cocoa display provider; it must be completed in a logged-in GUI session.
The validated subset excludes Kivy styling, inputs, mobile packaging and native
widget interoperability. M9 does not widen M8 reload safety.
