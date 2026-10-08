# M5 Pydux integration

PSX does not create a global store. Provide an existing Pydux store explicitly:

```python
from psx.integrations.pydux import StoreProvider, use_dispatch, use_selector

app = App(StoreProvider(store, Counter()), renderer="pyside6")
```

Create that store with Pydux's Toolkit-style API. Action creators belong to a
slice; PSX dispatches those creators' results and does not define its own action
format:

```python
from pydux import configure_store, create_slice

counter_slice = create_slice(
    name="counter",
    initial_state={"count": 0},
    reducers={
        "increment": lambda state, action: state.update({"count": state["count"] + 1}),
    },
)
store = configure_store({"counter": counter_slice}, devtools=False)

def select_count(state):
    return state["counter"]["count"]

@component
def Counter():
    count = use_selector(select_count)
    dispatch = use_dispatch()
    return Button("+1", on_click=lambda: dispatch(counter_slice.actions.increment()))
```

`use_selector(selector, equality_fn=None)` delegates to the public
`Store.select` API. Its listener only writes local hook state and schedules a
PSX UI flush; it never reconciles synchronously while Pydux may hold its store
lock. Its unsubscribe function is used as an effect cleanup on unmount.

`use_dispatch()` returns the exact `store.dispatch` method from the nearest
provider. Pydux remains responsible for reducers, selectors, middleware and
thunks.

The checked-out Pydux project is used for compatibility validation. The package
is not currently resolvable from the configured package index, so PSX does not
publish a misleading `psx[pydux]` extra yet. Install or provide a compatible
Pydux distribution independently.
