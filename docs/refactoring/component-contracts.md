# REF-M1 component contracts

`psx.core.contracts` centralizes the portable semantics of the built-in `Text`, `Button`, and `Input` components. It has no GUI, Qyro or Pydux dependency.

Each `ComponentContract` defines:

- its stable name;
- supported properties and default values;
- supported events;
- child policy metadata;
- renderer validation; and
- an optional legacy builder validator.

The public builders in `psx.core.vnode` keep their existing signatures and delegate to the relevant contract. `vnode.py` also re-exports the existing `*_PROPS`, `*_DEFAULTS`, and `validate_*_props` names, so current internal consumers continue to function while the migration proceeds.

`Input` is deliberately given a separate builder validator because its public constructor has pre-existing `TypeError` and `ValueError` diagnostics while renderer validation raises `RendererCapabilityError`. The distinction is represented by the contract instead of being duplicated through the builder.

Renderer helpers now ask contracts to validate `Text` and `Button` properties and to apply defaults. No public registry exists yet: REF-M2 will add an internal default registry without requiring built-in registration by applications.
