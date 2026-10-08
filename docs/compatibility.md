# Compatibility matrix — alpha

| Runtime | Python | Status | Validation |
| --- | --- | --- | --- |
| Headless core | 3.10–3.12 | supported | deterministic test suite |
| PySide6 | 3.10–3.12 | supported | Linux offscreen CI and local native smoke |
| PyQt6 / PyQt5 | binding-supported Python versions | supported adapter | offscreen renderer tests |
| Tkinter | CPython system Tk | supported adapter | manual graphical smoke required on macOS |
| Kivy 2.3+ | 3.10–3.12 | supported adapter | local graphical smoke required |

Native controls are never portable by implication. A `pyside6` declaration
fails clearly under Tkinter or Kivy. The alpha does not support mobile,
browser, frozen-binary packaging, or cross-process restoration as stable API.

macOS users should manually verify Tkinter and Kivy examples in a logged-in
desktop session; CI cannot replace their native event-loop behavior.
