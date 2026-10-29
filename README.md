# PSX


Build native Python interfaces using **PSX Markup**, CSS-like styling, reusable components, and a unified cross-platform rendering system.

PSX is the UI foundation of **Velto**. It provides a unified interface authoring language with familiar HTML-like syntax, reactive components, and native widget integration, rendering actual native widgets through **Qt, Tkinter, and Kivy**.

**No browser. No embedded web engine. Native interfaces powered by Python.**

> **Project status:** PSX is currently in alpha development. Features and APIs may change as the project evolves.

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
![GitHub Release](https://img.shields.io/github/v/release/Neuri-AI/PSX?include_prereleases&display_name=release&color=stable)
![GitHub Issues](https://img.shields.io/github/issues/Neuri-AI/PSX)
![GitHub Issues Closed](https://img.shields.io/github/issues-closed/Neuri-AI/PSX?color=green)
![GitHub forks](https://img.shields.io/github/forks/Neuri-AI/PSX)
![GitHub stars](https://img.shields.io/github/stars/Neuri-AI/PSX)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/Sponsor-Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/neuri)

## Why PSX?

Python already has excellent native UI frameworks. PSX doesn't replace them—it provides a common interface-building layer on top of their rendering capabilities.

- **PSX Markup** — Define interfaces using elements, attributes, expressions, conditionals, loops, and reusable components.
- **Native rendering** — Render actual widgets using PySide6, PyQt6, PyQt5, PySide2, Tkinter, or Kivy where supported.
- **CSS-like styling** — Apply styles using selectors, classes, inheritance, and a supported subset of CSS properties.
- **Unified layout** — Use Cinnamon, PSX's integrated layout engine, for consistent geometry calculations.
- **Reactive components** — Manage local state, effects, and references through hooks.
- **Efficient updates** — Reconcile virtual nodes, preserve compatible widget identities, and update affected interface regions.
- **Native interoperability** — Integrate framework-specific widgets and third-party libraries.
- **Extensible architecture** — Register components, native adapters, and plugins.

## Getting Started

### Requirements

- Python 3.10–3.13
- A supported native UI toolkit
- Windows, macOS, or Linux, subject to backend compatibility

### Installation

Install PSX from a local checkout with your preferred backend:

```bash
git clone https://github.com/Neuri-AI/PSX.git
cd PSX

# PySide6
python -m pip install -e ".[pyside6]"
```

Other available backend extras include `pyqt6`, `pyqt5`, `pyside2`, and `kivy`.

PySide2 has additional Python version restrictions, and Tkinter is normally provided by the Python installation.

See the [compatibility documentation](docs/compatibility.md) for supported combinations.

### Hello World

PSX interfaces are defined using **PSX Markup**:

```python
from psx import psx

view = psx("""
    <div>
        <h1>Hello, World!</h1>
        <p>Welcome to PSX.</p>
        <button>Get started</button>
    </div>
""")
```

The markup is compiled into a tree of virtual nodes (VNodes), which PSX reconciles and sends to a native renderer.

This snippet illustrates markup construction. A complete application also requires an application lifecycle and a compatible renderer.

### Reactive Components

PSX components can use hooks to manage state and update their interfaces.

```python
from psx import component, psx, use_state


@component
def Counter():
    count, set_count = use_state(0)

    def increment():
        set_count(lambda current: current + 1)

    return psx("""
        <div>
            <h2>Counter</h2>
            <p>Count: {count}</p>
            <button on_click={increment}>
                Increment
            </button>
        </div>
    """)
```

When state changes, PSX reconciles the updated interface instead of recreating the entire native widget tree.

PSX resolves references to local variables and callbacks through its lexical source transformation system.

## PSX Markup

**PSX Markup is the interface authoring language of PSX.**

All interfaces are defined through PSX Markup, which provides a unified syntax for HTML-like elements, built-in components, native widgets, and custom components.

It supports expressions, conditional rendering, iterations, component composition, and reactive state integration.

### HTML-like Elements

HTML-like elements provide familiar syntax for building native interfaces.

```python
from psx import psx

view = psx("""
    <div class="profile">
        <h2>Profile</h2>
        <p>Manage your account.</p>
        <input placeholder="Your name" />
        <button>Save changes</button>
    </div>
""")
```

These elements participate in PSX's component, styling, layout, reconciliation, and native rendering systems.

### Built-in Components

PSX provides built-in components such as `Flex`, `Grid`, `GridItem`, `Scroll`, and `Native` for organizing layouts, managing scrollable content, and integrating native widgets.

These components are used directly within PSX Markup:

```python
from psx import psx

view = psx("""
    <Flex direction="column" gap="16">
        <h2>Dashboard</h2>

        <Grid columns="2" gap="12">
            <GridItem>
                <p>Overview</p>
            </GridItem>

            <GridItem>
                <p>Statistics</p>
            </GridItem>
        </Grid>
    </Flex>
""")
```

Built-in components and HTML-like elements are part of the same markup system, sharing PSX's reconciliation, styling, layout, and native rendering infrastructure.

### Third-party Native Widgets

The `Native` component enables the integration of toolkit-specific widgets and third-party libraries directly into PSX Markup.

For example, a PyQtGraph chart can be embedded in a Qt-based interface:

```python
import numpy as np
import pyqtgraph as pg

from psx import psx


class SineChart(pg.PlotWidget):
    def __init__(self):
        super().__init__()

        x = np.linspace(0, 10, 1000)

        self.setBackground("#151515")
        self.setTitle("Sine Wave")
        self.showGrid(x=True, y=True)
        self.plot(
            x,
            np.sin(x),
            pen=pg.mkPen("#8B5CF6", width=2),
        )


view = psx("""
    <Flex direction="column" gap="16">
        <h2>Signal Visualization</h2>
        <Native widget={SineChart} />
    </Flex>
""")
```

The example illustrates third-party widget integration using the Qt backend. The exact `Native` widget-binding attribute should be checked against the installed PSX version.

Native widgets retain their toolkit-specific functionality and compatibility requirements.

## CSS and Layout

PSX includes a CSS-like styling system connected to its universal box model and Cinnamon layout engine.

Its supported styling capabilities include:

- Stylesheets, selectors, classes, IDs, specificity, cascade, and inheritance.
- Dimensions, spacing, borders, and supported sizing constraints.
- Foreground colors, semantic backgrounds, and native typography.
- Supported Flex, Grid, Block, and Inline layout behavior.
- Incremental layout and measurement invalidation.

Native visual support varies by property, component, and renderer.

PSX does not claim complete browser CSS compatibility.

## Architecture Overview

```text
                 PSX Markup
                     |
                     v
              Markup Compiler
                     |
                     v
               Virtual Nodes
                     |
                     v
                 Reconciler
                     |
           +---------+---------+
           |                   |
           v                   v
      CSS & Styles        Hooks & State
           |                   |
           +---------+---------+
                     |
                     v
             Cinnamon Layout
                     |
                     v
              Native Renderers
                     |
         +-----------+-----------+
         |           |           |
         v           v           v
        Qt        Tkinter       Kivy
```

PSX manages the interface representation, reconciliation, supported style resolution, and layout coordination.

Native renderers translate the resulting operations into real toolkit widgets, while Cinnamon remains the shared layout authority for the geometry it manages.

The diagram is a conceptual overview; actual rendering and update operations interact through the reconciler and renderer lifecycle.


## 🤝 Contributing

Contributions to `PSX` are welcome.

1. Fork the repository on GitHub.
2. Create a feature branch:

   ```bash
   git checkout -b feature/amazing-feature
   ```

3. Run the test suite:

   ```bash
   poetry run pytest
   ```

4. Commit your changes:

   ```bash
   git commit -m "feat: add amazing feature"
   ```

5. Push your branch:

   ```bash
   git push origin feature/amazing-feature
   ```

6. Open a pull request.

## License

PSX is released under the MIT License.

See [LICENSE](LICENSE) for details.


For the new explicit `props` mapping, use `update_props(props, changed)` on your
widget or register `@native_adapter`. See [Native reactive props](docs/native-reactive-props.md).
