"""Real native toolkit event loops in separate process generations.

Executed as a subprocess by test_native_event_loop_process.py. Each invocation
mounts a new native PSX application, enters its actual event loop and exits
through the toolkit's own scheduled stop callback.
"""
import os
from pathlib import Path
import sys

from psx import App, Flex, Text

backend = sys.argv[1]
marker = Path(sys.argv[2])
if backend == "qt":
    from psx.renderers.qt.pyside import PySide6Renderer
    from PySide6.QtCore import QTimer
    renderer = PySide6Renderer(argv=["native-restart-child"])
    def stop():
        renderer.application.quit()
    def schedule():
        QTimer.singleShot(250, stop)
elif backend == "tk":
    from psx.renderers.tkinter import TkinterRenderer
    renderer = TkinterRenderer()
    def schedule():
        renderer.root.after(250, renderer.root.quit)
elif backend == "kivy":
    from psx.renderers.kivy import KivyRenderer
    from kivy.clock import Clock
    from kivy.base import stopTouchApp
    renderer = KivyRenderer()
    def schedule():
        Clock.schedule_once(lambda dt: stopTouchApp(), .25)
else:
    raise RuntimeError("Unsupported native backend")

app = App(Flex(Text("Actual event loop")), renderer=renderer)
try:
    handle = app.mount()
    assert handle.widget is not None
    if backend == "qt":
        handle.widget.show()
    if backend == "tk":
        renderer.root.deiconify()
    schedule()
    marker.write_text("mounted", encoding="utf-8")
    assert renderer.run() == 0
    marker.write_text("event_loop_exited", encoding="utf-8")
finally:
    app.unmount()
    if backend == "tk":
        renderer.close()
    marker.with_suffix(".clean").write_text("unmounted", encoding="utf-8")
