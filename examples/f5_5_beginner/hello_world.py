"""First portable Velto component; run with python hello_world.py."""
from psx import App, Flex, Text, component


@component
def Hello():
    return Flex(
        Text("Hello, Velto!"),
        direction="column",
        gap=12,
    )


def main() -> int:
    app = App(Hello(), renderer="headless")
    try:
        handle = app.mount()
        assert handle.type == "Flex"
        assert handle.children[0].props["value"] == "Hello, Velto!"
        print(handle.children[0].props["value"])
        return 0
    finally:
        app.unmount()


if __name__ == "__main__":
    raise SystemExit(main())
