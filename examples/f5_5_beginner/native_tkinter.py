"""Minimal native Tkinter smoke app.

Run with python native_tkinter.py on a machine with tkinter and a display.
"""
import sys

from psx import App, Text


def main() -> int:
    app = App(Text("Hello from native Tkinter"), renderer="tkinter")
    if "--smoke" in sys.argv:
        try:
            widget = app.mount()
            assert widget is not None
            print("Tkinter native mount: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
