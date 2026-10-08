
from pydux import configure_store, create_slice


counter_slice = create_slice(
    name="counter",
    initial_state={"count": 0},
    reducers={
        "increment": lambda state, action: state.update(
            count=state["count"] + 1
        ),
        "decrement": lambda state, action: state.update(
            count=state["count"] - 1
        ),
    },
)

payload_slice = create_slice(
    name="payload",
    initial_state={"value": 0},
    reducers={
        "set": lambda state, action: state.update(
            value=action.payload
        ),
    },
)

store = configure_store(
    {
        "counter": counter_slice,
        "payload": payload_slice,
    },
    devtools=True,
)