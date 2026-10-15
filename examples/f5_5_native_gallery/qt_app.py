"""PySide6 native-UI example, with a bounded smoke path.

Requires pip install -e '.[pyside6]'. Uses real Qt widgets.
"""
import sys
from psx import App, Text, Button, Fragment


def make_app() -> App:
    return App(
        Fragment(
            Text("Velto + PySide6"),
            Button("Hello Qt", on_click=lambda: print("Qt clicked")),
        ),
        renderer="pyside6",
    )


def main() -> int:
    app = make_app()
    if "--smoke" in sys.argv:
        try:
            handle = app.mount()
            assert handle is not None
            print("PySide6 native mount: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
