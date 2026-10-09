# REF-M2 component registry

`psx.core.registry` adds a renderer-independent registry without changing the current compiler or public application API.

## Model

`ComponentDefinition` contains a tag name, callable constructor and optional `ComponentContract`. `ComponentRegistry` owns its definitions; it has no mandatory global instance. Its operations are deterministic:

| Operation | Result |
| --- | --- |
| `register(name, constructor, contract=...)` | Adds one definition and returns it. |
| repeated name | Raises `DuplicateComponentError`. |
| `resolve(name)` for an absent name | Raises `UnknownComponentError`. |
| `snapshot()` | Returns an immutable copy suitable for a resolver. |
| `clone()` | Creates an independent registry. |

Every successful registration increments `version`. REF-M3 will use registry identity/version to ensure template caching cannot use an incompatible resolver configuration.

## Built-ins

`builtin_component_registry()` creates a fresh registry populated with `Column`, `Row`, `Text`, `Button`, `Input`, `Fragment`, and `Native`. `Text`, `Button`, and `Input` carry their REF-M1 contracts. The factory imports only PSX core modules; it does not import a Qt, Kivy or Tkinter package.

REF-M3 wires the registry into `psx.markup.compile` through an additive `registry=` argument. Existing explicit `primitives`, source transform, diagnostics and default-template behavior remain compatible; see `markup-resolver.md`.
