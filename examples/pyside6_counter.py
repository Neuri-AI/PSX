"""M2 demo: real Qt widgets, event dispatch, and incremental text updates.

Run from the project root after installing the optional Qt extra:
    python -m pip install '.[qt]'
    PYTHONPATH=src python examples/pyside6_counter.py
"""

from psx import App, Button, Column, Text, component, use_state


def main() -> int:
    @component
    def Counter():
        count, set_count = use_state(0)
        return Column(
            Text(f"Count: {count}", key="count"),
            Button("+1", key="increment", on_click=lambda: set_count(lambda value: value + 1)),
            spacing=12,
        )

    app = App(Counter(), renderer="pyside6")
    root = app.mount()
    root.widget.show()
    return app.renderer.run()


if __name__ == "__main__":
    raise SystemExit(main())
