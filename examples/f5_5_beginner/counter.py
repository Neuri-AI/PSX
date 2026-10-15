"""Stateful component in a deterministic Headless renderer."""
from psx import App, Button, Fragment, Text, component, use_state


@component
def Counter():
    count, set_count = use_state(0)

    def increment() -> None:
        set_count(lambda current: current + 1)

    return Fragment(
        Text(f"Count: {count}"),
        Button("Increment", on_click=increment),
    )


def main() -> int:
    app = App(Counter(), renderer="headless")
    try:
        root = app.mount()
        print(root.children[0].props["value"])
        root.children[1].props["on_click"]()
        app.renderer.flush()
        print(root.children[0].props["value"])
        return 0
    finally:
        app.unmount()


if __name__ == "__main__":
    raise SystemExit(main())
