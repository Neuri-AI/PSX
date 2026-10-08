from __future__ import annotations

import sys
import threading
import unittest
from collections.abc import Callable
from typing import Any

sys.path.insert(0, "src")

from pydux import Action, Store, configure_store, create_async_thunk, create_slice

from psx import Button, Column, PSXError, Text, component
from psx.core.reconcile import Reconciler
from psx.integrations.pydux import StoreProvider, use_dispatch, use_selector
from psx.renderers.headless import HeadlessRenderer


def select_count(state: dict[str, int]) -> int:
    return state["count"]


def select_other(state: dict[str, int]) -> int:
    return state["other"]


def reducer(state: dict[str, int], action: Action) -> dict[str, int]:
    if action.type == "increment":
        return {**state, "count": state["count"] + 1}
    if action.type == "other":
        return {**state, "other": state["other"] + 1}
    return state


class RecordingStore:
    """Delegates to the real Store while recording public unsubscribe calls."""

    def __init__(self, store: Store[dict[str, int]]) -> None:
        self.store = store
        self.unsubscribe_calls = 0

    def get_state(self) -> dict[str, int]:
        return self.store.get_state()

    def dispatch(self, action: object) -> object:
        return self.store.dispatch(action)

    def select(self, *args: object, **kwargs: object) -> Callable[[], None]:
        unsubscribe = self.store.select(*args, **kwargs)  # type: ignore[arg-type]

        def tracked() -> None:
            self.unsubscribe_calls += 1
            unsubscribe()

        return tracked


class RecordingInspector:
    def __init__(self) -> None:
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1


class PyduxIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = HeadlessRenderer()
        self.reconciler = Reconciler(self.renderer)
        self.store = Store(reducer, {"count": 0, "other": 0})

    def tearDown(self) -> None:
        self.reconciler.unmount()

    def test_selector_dispatch_and_native_event_share_the_existing_scheduler(self) -> None:
        renders = {"counter": 0}
        counter_slice = create_slice(
            name="counter",
            initial_state={"count": 0},
            reducers={
                "increment": lambda state, action: state.update({"count": state["count"] + 1}),
            },
        )
        store = configure_store({"counter": counter_slice}, devtools=False)

        def select_toolkit_count(state: dict[str, dict[str, int]]) -> int:
            return state["counter"]["count"]

        @component
        def Counter():
            renders["counter"] += 1
            count = use_selector(select_toolkit_count)
            dispatch = use_dispatch()
            return Column(
                Text(f"Count: {count}", key="label"),
                Button("+1", key="button", on_click=lambda: dispatch(counter_slice.actions.increment())),
            )

        root = self.reconciler.render(StoreProvider(store, Counter()))
        column = root.children[0].children[0].handle
        label, button = column.children
        self.assertEqual(label.props["value"], "Count: 0")
        button.events["on_click"].invoke()
        self.assertEqual(label.props["value"], "Count: 0")
        self.renderer.flush()
        self.assertEqual(label.props["value"], "Count: 1")
        self.assertEqual(renders["counter"], 2)

    def test_only_the_component_with_a_changed_selector_rerenders(self) -> None:
        renders = {"count": 0, "other": 0}

        @component
        def CountView():
            renders["count"] += 1
            return Text(str(use_selector(select_count)))

        @component
        def OtherView():
            renders["other"] += 1
            return Text(str(use_selector(select_other)))

        self.reconciler.render(StoreProvider(self.store, Column(CountView(), OtherView())))
        self.assertEqual(renders, {"count": 1, "other": 1})
        self.store.dispatch(Action("increment"))
        self.renderer.flush()
        self.assertEqual(renders, {"count": 2, "other": 1})

    def test_unmount_calls_the_public_unsubscribe_once(self) -> None:
        recording = RecordingStore(self.store)

        @component
        def Counter():
            return Text(str(use_selector(select_count)))

        self.reconciler.render(StoreProvider(recording, Counter()))
        self.reconciler.unmount()
        self.reconciler.unmount()
        self.assertEqual(recording.unsubscribe_calls, 1)

    def test_final_store_provider_unmount_stops_the_pydux_inspector_once(self) -> None:
        inspector = RecordingInspector()
        self.store.inspector = inspector
        self.reconciler.render(StoreProvider(self.store, Text("ready")))
        self.reconciler.unmount()
        self.reconciler.unmount()
        self.assertEqual(inspector.stops, 1)

    def test_worker_dispatch_does_not_mutate_the_ui_before_the_scheduler_flush(self) -> None:
        @component
        def Counter():
            return Text(str(use_selector(select_count)))

        root = self.reconciler.render(StoreProvider(self.store, Counter()))
        label = root.children[0].children[0].handle
        worker = threading.Thread(target=lambda: self.store.dispatch(Action("increment")))
        worker.start()
        worker.join()
        self.assertEqual(label.props["value"], "0")
        self.renderer.flush()
        self.assertEqual(label.props["value"], "1")

    def test_async_thunk_uses_the_same_selector_path(self) -> None:
        def thunk_reducer(state: int | None, action: Action) -> int:
            current = 0 if state is None else state
            if action.type == "counter/add/fulfilled":
                return current + int(action.payload)
            return current

        store = configure_store(thunk_reducer, preloaded_state=0, devtools=False, inspector_auto_start=False)
        thunk = create_async_thunk("counter/add", lambda amount: amount)

        @component
        def Counter():
            return Text(str(use_selector(lambda state: state)))

        root = self.reconciler.render(StoreProvider(store, Counter()))
        label = root.children[0].children[0].handle
        store.dispatch(thunk(2))
        self.renderer.flush()
        self.assertEqual(label.props["value"], "2")

    def test_hooks_require_an_explicit_provider(self) -> None:
        @component
        def Invalid():
            return Text(str(use_selector(select_count)))

        with self.assertRaises(PSXError):
            self.reconciler.render(Invalid())


if __name__ == "__main__":
    unittest.main()
