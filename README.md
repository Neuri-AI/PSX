# PSX

**Declarative native UI for Python.**

PSX lets you describe UI with Python components or JSX-like markup while it
renders real widgets through PySide6, PyQt6, PyQt5, Tkinter, or Kivy. It has a
small portable core (`Column`, `Row`, `Text`, `Button`) and an explicit native
escape hatch when a backend-specific control is the right tool.

> PSX is an alpha release. The supported API and backend boundaries are
> documented in [docs/public-api.md](docs/public-api.md) and
> [docs/compatibility.md](docs/compatibility.md).

`Text` uses the same closed portable contract in every renderer.
See [Text properties](docs/components/text.md).

## Why PSX?

- Write components with familiar state, effects, refs, and event callbacks.
- Keep native widget identity stable across updates through keyed
  reconciliation.
- Use safe PSX markup without `eval`, runtime frame inspection, or arbitrary
  Python execution inside templates.
- Reuse advanced controls from the selected UI toolkit through `Native(...)`.
- Integrate with Qyro for application lifecycle and Pydux for state stores.

## Installation

PSX requires Python 3.10 or later. Choose the renderer you intend to use:

```bash
# PySide6
python -m pip install "psx[qt]"

# Or another renderer
python -m pip install "psx[pyqt6]"
python -m pip install "psx[pyqt5]"
python -m pip install "psx[kivy]"
```

Tkinter is normally bundled with desktop CPython. Optional integrations are
available through `psx[pydux]` and `psx[qyro]`. For a local checkout:

```bash
python -m pip install -e ".[dev,qt]"
```

## Your first component

Create `counter.py`:

```python
from psx import App, Button, Column, Text, component, use_state


@component
def Counter():
    count, set_count = use_state(0)

    def increment() -> None:
        set_count(lambda value: value + 1)

    return Column(
        Text(f"Count: {count}"),
        Button("Increment", on_click=increment),
        spacing=12,
        padding=24,
    )


if __name__ == "__main__":
    App(Counter(), renderer="pyside6").run()
```

Run it:

```bash
python counter.py
```

`use_state` schedules a render on the renderer's UI loop. When the button is
clicked, PSX updates the existing native `Text` and `Button` rather than
rebuilding the complete window.

## Core concepts

### Components and state

Use `@component` for a function that returns PSX nodes. Hooks must be called
in the same order every render.

```python
from psx import Text, component, use_effect, use_state


@component
def Status():
    online, set_online = use_state(False)

    use_effect(lambda: print(f"Online: {online}"), [online])
    return Text("Online" if online else "Offline")
```

`use_effect` runs after a UI commit. If it returns a cleanup function, PSX runs
it before the next effect and during unmount. Use `use_ref()` when you need a
stable reference after mount.

### Keys

Provide a stable `key` for dynamic siblings. A key preserves component/native
identity while items move; changing it intentionally resets that subtree.

```python
return Column(*(Text(todo.title, key=todo.id) for todo in todos))
```

Duplicate sibling keys are an error.

## PSX markup

The Python builder and markup forms create the same VNode tree:

```python
from psx import psx

title = "Hello, PSX"
node = psx("""
    <Column spacing={12} padding={24}>
        <Text>{title}</Text>
        <Button on_click={save}>Save</Button>
    </Column>
""", scope={"title": title, "save": save})
```

For normal application code, use the M4B static transform to resolve local
variables, closures, and `self` automatically—without supplying `scope`:

```bash
psx-transform app.py --output app_psx.py
python app_psx.py
```

Markup references are identifiers or dotted attribute paths, such as
`{count}`, `{self.window_title}`, and `{self.platform.value}`. It deliberately
does **not** evaluate arbitrary expressions: calculate conditionals and
collections in Python first, then reference the resulting name in markup.

```python
button_label = "Pause" if playing else "Play"
return psx("<Button on_click={toggle}>{button_label}</Button>")
```

## Native widgets when you need them

Portable primitives intentionally cover only common UI semantics. Use
`Native(...)` to mount a real backend control without leaving the declarative
tree:

```python
from PySide6.QtWebEngineWidgets import QWebEngineView
from psx import Native, component, use_state


@component
def Browser():
    url, set_url = use_state("https://www.python.org")

    return Native(
        QWebEngineView,
        props={"url": url},
        signals={"loadFinished": lambda ok: print("loaded", ok)},
        key="browser",
    )
```

PSX preserves the `QWebEngineView` while its type and key remain compatible;
changing `url` calls the appropriate native property setter. The same model
works with Tkinter and Kivy widgets, but a native widget is specific to its
backend—it is not silently emulated elsewhere.

For reusable third-party adapters, ownership rules, custom properties, and
native signal cleanup, see the [native widget tutorial](docs/tutorial-adding-native-widgets.md).

## Renderer selection

Pass a renderer name to `App`:

```python
App(Main(), renderer="pyside6")
App(Main(), renderer="pyqt6")
App(Main(), renderer="pyqt5")
App(Main(), renderer="tkinter")
App(Main(), renderer="kivy")
App(Main(), renderer="headless")  # deterministic tests
```

If you use Qyro, PSX can obtain the configured binding through Qyro's public
settings API. See the runnable projects in [examples](examples/).

## Pydux and Qyro

PSX does not create a hidden global store. Use an explicit `StoreProvider` in a
standalone PSX tree, or let a Qyro `PSXComponent` discover the single Pydux
store declared in its module. Read the exact state your component needs with
`use_selector`; dispatch through `use_dispatch`. Qyro's `ApplicationContext`
stays the owner of application lifecycle and native hosts.

### Create a Qyro + PSX project

Generate the Qyro application with the binding you want, install the matching
PSX extra in that project, and start it with Qyro:

```bash
qyro init my_psx_app --binding PySide6
cd my_psx_app
python -m pip install "psx[qt]"
qyro start
```

When developing PSX from this checkout, replace the installation command with
an editable path, for example:

```bash
python -m pip install -e "/path/to/psx[qt]"
```

### Qyro + PySide6

Use one window class. `ApplicationContext` owns Qyro's lifecycle,
`PSXComponent` owns the declarative subtree, and `QMainWindow` remains the
native host:

```python
"""main.py — run with: qyro start"""

import sys

from PySide6.QtWidgets import QMainWindow
from qyro import ApplicationContext
from psx import psx, use_state
from psx.integrations.qyro import PSXComponent


class CounterWindow(QMainWindow, PSXComponent, ApplicationContext):
    def component_will_mount(self) -> None:
        self.setMinimumSize(640, 480)

    def render(self):
        count, set_count = use_state(0)

        def increment() -> None:
            set_count(lambda value: value + 1)

        return psx("""
            <Column padding={32} spacing={12}>
                <Text>Qyro + PSX</Text>
                <Text>App: {self.window_title}</Text>
                <Text>Count: {count}</Text>
                <Button on_click={increment}>Increment</Button>
            </Column>
        """)


if __name__ == "__main__":
    window = CounterWindow()
    window.show()
    sys.exit(window.run())
```

The Qyro integration prepares literal PSX templates for M4B, so local values,
closures, and paths such as `self.window_title` resolve without `scope={...}`.

### Reusable PSX components in a Qyro project

Keep a single Qyro window/application class as the native host. Put reusable
UI in ordinary PSX function components; they do not inherit from Qyro classes
and can be tested with the headless renderer.

```python
# components/counter_card.py
from collections.abc import Callable

from psx import component, psx


@component
def CounterCard(*, title: str, count: int, on_increment: Callable[[], None]):
    return psx("""
        <Column spacing={8} padding={12}>
            <Text>{title}</Text>
            <Row spacing={8}>
                <Text>Count: {count}</Text>
                <Button on_click={on_increment}>Increment</Button>
            </Row>
        </Column>
    """, scope={
        "title": title,
        "count": count,
        "on_increment": on_increment,
    })
```

Import it into the Qyro host and pass data/callbacks as normal Python props:

```python
# main.py
from components.counter_card import CounterCard


class CounterWindow(QMainWindow, PSXComponent, ApplicationContext):
    def render(self):
        count, set_count = use_state(0)

        def increment() -> None:
            set_count(lambda value: value + 1)

        return psx("""
            <Column spacing={12} padding={32}>
                <Text>Qyro dashboard</Text>
                <CounterCard
                    title="Orders"
                    count={count}
                    on_increment={increment}
                    key="orders-counter" />
            </Column>
        """)
```

This component is authored in PSX markup and its explicit `scope` makes it
usable whether it is imported normally or transformed. To omit `scope={...}`
in a reusable module, apply M4B to that module as part of the project build;
the Qyro entry module is prepared automatically. Components do not create a
second Qyro lifecycle, window, or store; they are simply subtrees of the
host's PSX render.

### Qyro + Pydux

Keep the Qyro host as one class. When exactly one compatible store is declared
in the module, `PSXComponent` discovers and provides it automatically—no
`psx_store = store` or visible `StoreProvider` is required:

```python
import sys

from PySide6.QtWidgets import QMainWindow
from pydux import configure_store, create_slice
from qyro import ApplicationContext
from psx import psx
from psx.integrations.pydux import use_dispatch, use_selector
from psx.integrations.qyro import PSXComponent


counter = create_slice(
    name="counter",
    initial_state={"count": 0},
    reducers={
        "increment": lambda state, action: state.update(count=state["count"] + 1),
    },
)
store = configure_store({"counter": counter.reducer})


class CounterWindow(QMainWindow, PSXComponent, ApplicationContext):
    def render(self):
        count = use_selector(lambda state: state["counter"]["count"])
        dispatch = use_dispatch()

        def increment() -> None:
            dispatch(counter.actions.increment())

        return psx("""
            <Column padding={32} spacing={12}>
                <Text>Counter: {count}</Text>
                <Button on_click={increment}>Increment</Button>
            </Column>
        """)


if __name__ == "__main__":
    window = CounterWindow()
    window.show()
    sys.exit(window.run())
```

### Qyro + Kivy

Generate this project with `qyro init my_kivy_app --binding Kivy`. Do not add a
manual `App.__init__`: `PSXComponent` handles the Kivy lifecycle bridge.

```python
import sys

from kivy.app import App
from qyro import ApplicationContext
from psx import psx, use_state
from psx.integrations.qyro import PSXComponent


class CounterApp(PSXComponent, App, ApplicationContext):
    def render(self):
        count, set_count = use_state(0)

        def increment() -> None:
            set_count(lambda value: value + 1)

        return psx("""
            <Column padding={32} spacing={12}>
                <Text>Qyro + PSX + Kivy</Text>
                <Text>Count: {count}</Text>
                <Button on_click={increment}>Increment</Button>
            </Column>
        """)


if __name__ == "__main__":
    sys.exit(CounterApp().run())
```

For the generated Qyro project, start the application with:

```bash
qyro start
```

Examples:

- [Qyro + PSX + Qt](examples/qyro_qt_psx_demo/)
- [Qyro + PSX + Pydux + Qt](examples/qyro_qt_pydux_demo/)
- [Qyro + PSX + Tkinter](examples/qyro_tkinter_psx_demo/)
- [Qyro + PSX + Kivy](examples/qyro_kivy_psx_demo/)

## Development and hot reload

`psx-dev` supervises a development process and restarts it safely when Python
source changes. Qyro projects can also use PSX's development integration; hot
reload is disabled for frozen apps and can be controlled from Qyro settings.

```bash
psx-dev python counter.py
```

Read [M8 hot reload](docs/m8-hot-reloading.md) before relying on it for complex
module-level singletons or native resources.

## Testing and benchmarks

The headless renderer makes component tests deterministic:

```bash
PYTHONPATH=psx python -m pytest -q tests
```

Measure the core without a GUI backend:

```bash
PYTHONPATH=psx python benchmarks/psx_benchmark.py --write-baseline .bench.json
PYTHONPATH=psx python benchmarks/psx_benchmark.py --baseline .bench.json
```

The benchmark separates VNode construction from reconciliation and reports
full, single-node, no-op, keyed reorder, scheduler, markup, M4B, and memory
measurements. Compare baselines only on the same machine and Python version.

## Playground and layout inspector

The browser playground is a separate React project at
[`../playground`](../playground). Start it independently from the Python
package:

```bash
cd ../playground
# If Node is not yet available in this terminal, load NVM first.
nvm -v
npm install
npm run dev
```

It provides Monaco editing, examples, parser diagnostics, generated wrapper
code, hierarchy/bounds/padding/spacing/alignment inspection, and preview-only
layout edits. It never executes template references or renders desktop widgets
in the browser; use it to understand PSX structure, not to validate native
pixel output.

## Learn more

- [Public API](docs/public-api.md)
- [Compatibility matrix](docs/compatibility.md)
- [Native interoperability](docs/m10-native-interoperability.md)
- [Tutorial: adding portable widgets](docs/tutorial-adding-portable-widgets.md)
- [Alpha release and CI](docs/m11-alpha-release.md)
- [Playground and inspector](docs/m12-playground-inspector.md)
- [Architecture](docs/architecture.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).
