# PSX

**Declarative native UI for Python.**

PSX lets you describe UI with Python components or JSX-like markup while it
renders real widgets through PySide6, PyQt6, PyQt5, Tkinter, or Kivy. It has a
portable core (`Flex`, `Scroll`, `Text`, `Button`) and an explicit native
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
from psx import App, Button, Flex, Text, component, use_state\nfrom psx.renderers.qt.pyside import PySide6Renderer\nfrom psx.sfle.engine import PythonLayoutEngine\nfrom psx.sfle.model import AvailableSize, LayoutConstraints


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
    renderer = PySide6Renderer(\n        sfle_constraints=LayoutConstraints(\n            AvailableSize(400, True), AvailableSize(240, True)),\n        engine=PythonLayoutEngine(),\n    )\n    App(Counter(), renderer=renderer).run()
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
return Flex(*(Text(todo.title, key=todo.id) for todo in todos),\n            direction="column", width="400px", height="240px")
```

Duplicate sibling keys are an error.

## PSX markup

The Python builder and markup forms create the same VNode tree:

```python
from psx import psx

title = "Hello, PSX"
node = psx("""
    <Flex direction="column" gap={12} padding={24}>
        <Text>{title}</Text>
        <Button on_click={save}>Save</Button>
    </Flex>
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

## State management

PSX is UI infrastructure and does not own a state-management integration. For Pydux state in a PSX tree, install the optional `pydux[psx]` extra and import `StoreProvider`, `use_dispatch`, and `use_selector` from `pydux`. Applications using the Velto facade import those APIs from `velto.state`.

## Development and hot reload

`psx-dev` supervises a development process and restarts it safely when Python
source changes. Hot reload is disabled for frozen apps.

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


## Contributing and code naming

Use **behavior-descriptive** identifiers for packages, modules, functions, tests, scripts and workflows. Planning identifiers (F1/F2/F3, G1/G2/G3, C1–C6, etc.) belong only in documentation and historical certification reports. See [Source naming conventions](docs/development/naming-conventions.md) for requirements and examples.
