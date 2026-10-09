# REF-M6 public extension and plugin API

`psx.plugins` is dependency-free and exported from `psx`. It exposes `ComponentRegistry`, `ComponentDefinition`, `ComponentAdapter`, `RendererAdapterRegistry`, `register_component`, `register_adapter`, `renderer_capabilities`, `PluginAPI` and `load_plugins`.

Plugins receive a registry and named renderer instances. `api.component("Badge", Badge)` adds a component only to that registry; an optional namespace produces markup-safe names such as `acme.Badge`. Duplicate names and adapter collisions retain the existing explicit errors. Separate registries and renderer instances remain isolated.

Discovery uses the opt-in `psx.plugins` Python entry-point group. Entry points are never inspected or imported during ordinary PSX imports, so GUI dependencies remain lazy. See `examples/badge_plugin` for a minimal external package and entry-point declaration.

`renderer_capabilities(renderer)` reports adapters installed on that renderer instance. It reports availability only; it does not promise portable behavior across backends.
