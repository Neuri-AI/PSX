"""First portable Velto component; run with python hello_world.py."""
from psx import App, Fragment, Text, component


@component
def Hello():
    return Fragment(
        Text("Hello, Velto!"),
    )


def main() -> int:
    app = App(Hello(), renderer="headless")
    try:
        handle = app.mount()
        assert handle.type == "Fragment"
        assert handle.children[0].props["value"] == "Hello, Velto!"
        print(handle.children[0].props["value"])
        return 0
    finally:
        app.unmount()


if __name__ == "__main__":
    raise SystemExit(main())
