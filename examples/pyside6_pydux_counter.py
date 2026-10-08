"""M5 demo: a PSX subtree consumes an explicitly provided Pydux Store."""

from pydux import configure_store, create_slice

from psx import App, Button, Column, Text, component
from psx.integrations.pydux import StoreProvider, use_dispatch, use_selector


counter_slice = create_slice(
    name="counter",
    initial_state={"count": 0},
    reducers={
        "increment": lambda state, action: state.update({"count": state["count"] + 1}),
    },
)


def select_count(state: dict[str, dict[str, int]]) -> int:
    return state["counter"]["count"]


@component
def Counter():
    count = use_selector(select_count)
    dispatch = use_dispatch()
    return Column(
        Text(f"Pydux count: {count}", key="count"),
        Button("Increment", key="increment", on_click=lambda: dispatch(counter_slice.actions.increment())),
        spacing=12,
    )


def main() -> int:
    store = configure_store({"counter": counter_slice}, devtools=True)
    app = App(StoreProvider(store, Counter()), renderer="pyside6")
    root = app.mount()
    root.widget.show()
    return app.renderer.run()


if __name__ == "__main__":
    raise SystemExit(main())
