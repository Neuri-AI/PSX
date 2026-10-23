"""Native child whose real event loop initiates coordinated process replacement."""
import json
import os
from pathlib import Path
import socket
import sys
from psx import App, Flex, Text
from psx.sfle.model import AvailableSize, LayoutConstraints

backend, location = sys.argv[1:]
trace = Path(location)
generation = len(trace.read_text().splitlines()) if trace.exists() else 0
with trace.open("a", encoding="utf-8") as output:
    output.write(str(generation) + "\n")
viewport = LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True))

if backend == "qt":
    from PySide6.QtCore import QTimer
    from psx.renderers.qt.pyside import PySide6Renderer
    renderer = PySide6Renderer(argv=["supervised-native-child"], sfle_constraints=viewport)
    schedule = lambda callback: QTimer.singleShot(350, callback)
    stop = renderer.application.quit
elif backend == "tk":
    from psx.renderers.tkinter import TkinterRenderer
    renderer = TkinterRenderer(sfle_constraints=viewport)
    schedule = lambda callback: renderer.root.after(350, callback)
    stop = renderer.root.quit
elif backend == "kivy":
    from kivy.clock import Clock
    from kivy.base import stopTouchApp
    from psx.renderers.kivy import KivyRenderer
    renderer = KivyRenderer(sfle_constraints=viewport)
    schedule = lambda callback: Clock.schedule_once(lambda _dt: callback(), .35)
    stop = stopTouchApp
else:
    raise ValueError(backend)

host, port = os.environ["VELTO_RELOAD_ENDPOINT"].split(":")
with socket.create_connection((host, int(port)), timeout=5) as connection:
    connection.sendall((os.environ["VELTO_RELOAD_TOKEN"] + "\n").encode())
    application = App(Flex(Text("Supervised native app")), renderer=renderer)
    try:
        handle = application.mount()
        if backend == "qt":
            handle.widget.show()
        if backend == "tk":
            renderer.root.deiconify()
        if generation < 2:
            def restart():
                payload = {"version": 1, "kind": "restart_request",
                           "reason": "runtime_bootstrap_changed"}
                connection.sendall((json.dumps(payload) + "\n").encode())
            schedule(restart)
        else:
            schedule(stop)
        result = renderer.run()
        if generation >= 2:
            trace.with_suffix(".clean").write_text("event_loop_exited")
        raise SystemExit(result)
    finally:
        application.unmount()
        if backend == "tk":
            renderer.close()
