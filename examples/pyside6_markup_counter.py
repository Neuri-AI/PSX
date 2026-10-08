"""M4A demo: explicit-scope PSX markup backed by the PySide6 renderer."""

from psx import App, component, psx, use_state


@component
def Counter():
    count, set_count = use_state(0)

    def increment() -> None:
        set_count(lambda value: value + 1)

    return psx(
        """
        <Column spacing={spacing}>
            <Text>PSX Markup Counter</Text>
            <Text>Count: {count}</Text>
            <Button on_click={increment}>+1</Button>
        </Column>
        """,
        scope={"spacing": 12, "count": count, "increment": increment},
    )


def main() -> int:
    app = App(Counter(), renderer="pyside6")
    root = app.mount()
    root.widget.show()
    return app.renderer.run()


if __name__ == "__main__":
    raise SystemExit(main())
