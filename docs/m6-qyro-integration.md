# M6 Qyro integration

PSX consumes Qyro; it does not recreate Qyro runtime services.

```python
from psx.integrations.qyro import QyroProvider, use_container, use_qyro_context

tree = QyroProvider(AppView(), context=existing_application_context)
```

`use_qyro_context()` returns that exact `ApplicationContext`. `use_container()`
returns its exact public `EngineContainer`. `use_settings()` uses the container's
existing settings use case and `use_resource()` uses its existing resource
resolver, retaining Qyro source/frozen behavior.

When `App(..., renderer=None)` is used, PSX imports Qyro optionally and calls
the public `load_build_settings()` helper. It reads `binding`, then `framework`,
normalizes the selected name and raises a `RendererConfigurationError` for a
missing, unsupported or unavailable renderer. An explicit renderer always wins.

For an existing Qyro window, use `mount_psx(host, child, context=context)`. The
host is borrowed: PSX mounts its native root as the central widget (or into a
host layout), and `PSXMount.unmount()` tears down only that subtree. It never
calls Qyro lifecycle hooks or destroys the host.

For a declarative Qyro window, inherit `PSXComponent` between the Qt host and
`ApplicationContext`. Its `render()` returns one VNode; the adapter preserves
Qyro's lifecycle/event loop, waits for Qt host construction before the initial
commit, and tears down the PSX subtree when the host is destroyed.

```python
class Window(QMainWindow, PSXComponent, ApplicationContext):
    def render(self):
        return Column(Text("Declarative Qyro window"))
```

For a single class that uses an existing Pydux store, PSX discovers the one
Pydux-compatible store declared at module level. The provider is placed outside
the stable PSX root, so selectors and dispatch hooks are valid directly inside
the class `render()`:

```python
class Window(QMainWindow, PSXComponent, ApplicationContext):
    def render(self):
        count = use_selector(lambda state: state["counter"]["count"])
        dispatch = use_dispatch()
        return Button("Increment", on_click=lambda: dispatch(actions.increment()))
```

If a module intentionally declares multiple stores, set `psx_store` on the
component to select the intended one explicitly.

M8 does not alter Qyro runtime ownership. `psx-dev` is standalone; a future
Qyro CLI integration may delegate `qyro start --hot-reload` to its supervisor,
but no such CLI flag is currently claimed or required.
