"""A native Tkinter control gallery; --smoke validates mount/teardown.

The gallery uses portable PSX controls on a real Tkinter backend.
"""
import sys
from psx import App, Fragment, Text, Button, Input


def make_app() -> App:
    return App(
        Fragment(
            Text("Velto native controls"),
            Input(value="Welcome", placeholder="Type here"),
            Button("Confirm", on_click=lambda: print("Confirmed")),
            Text("Built with portable PSX components"),
        ),
        renderer="tkinter",
    )


def main() -> int:
    app = make_app()
    if "--smoke" in sys.argv:
        try:
            root = app.mount()
            assert root is not None
            print("Native gallery mount: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
