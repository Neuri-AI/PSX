"""Native Kivy example with a deterministic mount/teardown smoke."""
import sys

from psx import App, Text, Button, Fragment


def make_app() -> App:
    return App(
        Fragment(
            Text("Velto + Kivy"),
            Button("Hello Kivy", on_click=lambda: print("Kivy clicked")),
        ),
        renderer="kivy",
    )


def main() -> int:
    app = make_app()
    if "--smoke" in sys.argv:
        try:
            mounted = app.mount()
            assert mounted is not None
            print("Kivy native mount: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
