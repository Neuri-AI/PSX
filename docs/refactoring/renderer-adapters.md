# REF-M4 renderer adapter architecture

`psx.renderers.adapters` defines the typed `ComponentAdapter` lifecycle contract and an instance-scoped `RendererAdapterRegistry`.

```mermaid
flowchart LR
  R[Reconciler] --> P[Renderer protocol]
  P --> D[Renderer adapter dispatch]
  D --> A[ComponentAdapter]
  A --> N[Native handle / subscription]
```

Adapters own create, property update, event bind/unbind and destruction. Structural child placement remains on the renderer because it is layout-specific. The reconciler still owns VNode compatibility, keyed reconciliation, `EventSlot`, refs, hooks and cleanup ordering.

Each renderer owns `adapters`, exposes `register_adapter(component, adapter, replace=False)`, and registers adapters for layout nodes, `Text`, `Button`, `Input` and `Native`. The initial adapters delegate to the renderer's extracted legacy lifecycle methods. This preserves existing widget handles and event subscription behavior while making the dispatch seam extensible.

Headless tests replace the `Button` adapter and add a new `Badge` adapter. They prove that mounting, property updates, stable callback replacement, unbinding and destruction are dispatched through the adapter without modifying `Reconciler`.

## Validation

Validation ran in Conda `playground` with Python 3.13.16. PySide6, PyQt5, Kivy, Qyro and Pydux are installed; PyQt6 is absent and its optional test is skipped. The full command `python -m pytest tests/ -v --basetemp .pytest-playground-m4-full` completed with **137 passed, 1 skipped**.

The PySide6 portable-control tests exercise `Text`, `Button` and `Input` mounting, updates without handle recreation, callback replacement and teardown. The full suite additionally exercises Tkinter control lifecycle, Kivy and PyQt5 button identity, Qyro integration and Pydux scheduling. The adapter-registry tests exercise registration conflict diagnostics, custom adapters and deterministic bind/unbind/destroy dispatch.
