"""PySide6 native-UI example, with a bounded smoke path.

Requires pip install -e '.[pyside6]'. Uses real Qt widgets.
"""
import sys
from PySide6.QtWidgets import QApplication, QLabel

from psx import App, Text, Button, Fragment, Native


def make_app() -> App:
    return App(
        Fragment(
            Text("Velto + PySide6"),
            Button("Hello Qt", on_click=lambda: print("Qt clicked")),
            Native(QLabel, props={"text": "Native QLabel via Velto"}),
        ),
        renderer="pyside6",
    )


def main() -> int:
    app = make_app()
    if "--smoke" in sys.argv:
        try:
            handle = app.mount()
            assert handle is not None
            qt_app = QApplication.instance()
            assert qt_app is not None
            assert any(
                isinstance(widget, QLabel) and widget.text() == "Native QLabel via Velto"
                for widget in qt_app.allWidgets()
            ), "Native QLabel did not receive its text property"
            print("PySide6 native mount: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
