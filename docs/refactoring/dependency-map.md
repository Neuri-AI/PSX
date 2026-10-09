# REF-M0 dependency map

```mermaid
flowchart TB
  API[psx public exports] --> APP[app.py]
  API --> VNODE[core/vnode.py]
  API --> MARKUP[markup]
  MARKUP --> VNODE
  MARKUP --> COMPONENT[core/component.py]
  COMPONENT --> VNODE
  APP --> RECONCILE[core/reconcile.py]
  RECONCILE --> INSTANCE[core/instance.py]
  RECONCILE --> HOOKS[core/hooks.py]
  RECONCILE --> EVENTS[core/events.py]
  RECONCILE --> PROTOCOL[renderers/protocol.py]
  PROTOCOL --> RENDERERS[headless / Tkinter / Kivy / Qt]
  QYRO[integrations/qyro.py] --> APP
  QYRO --> HOOKS
  PYDUX[integrations/pydux.py] --> HOOKS
  DEVTOOLS[devtools] --> COMPONENT
  DEVTOOLS --> MARKUP
```

Core imports no GUI backend directly. Renderer loading is lazy in `App`, and the Qyro/Pydux integrations retain optional imports. The main dependency inversion issue is semantic rather than import-level: component knowledge is replicated in the compiler and concrete renderers.

Migration seam: add contracts and a resolver below the legacy builder/markup functions; add adapter lookup behind the existing renderer protocol. Keep `Reconciler`, VNode shape, compatibility matching, `EventSlot`, and hook scheduling stable while adapters are introduced.
