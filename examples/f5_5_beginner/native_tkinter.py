"""Minimal native Tkinter smoke app.

Run with python native_tkinter.py on a machine with tkinter and a display.
"""
from psx import App, Text


def main() -> int:
    app = App(Text("Hello from native Tkinter"), renderer="tkinter")
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
