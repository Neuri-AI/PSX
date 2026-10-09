# REF-M0 architecture audit

## Scope and compatibility boundary

This audit records the repository state before the clean-architecture migration. REF-M0 changes no runtime architecture. All subsequent work must retain every public export, builder signature and observable result documented by the existing tests and the characterization suite.

The public surface starts at `psx.__init__`, `psx.markup`, `psx.integrations`, `App`, the `@component` decorator, hooks, builders, `Native`, renderer selection strings, and the `psx-transform` and `psx-dev` commands. Markup remains source compatible: attributes, safe references, children, `key`, `ref`, events, fragments, explicit scope, lexical transformation, and component tags from scope must retain their current semantics.

## Current pipeline

```mermaid
flowchart LR
  P[Python builders] --> V[core/vnode.py]
  M[PSX markup] --> C[markup/compile.py]
  C --> V
  D[@component] --> V
  V --> R[core/reconcile.py]
  R --> I[MountedInstance + hooks + EventSlot]
  I --> A[Renderer protocol]
  A --> H[Headless]
  A --> Q[Qt adapters]
  A --> K[Kivy]
  A --> T[Tkinter]
```

`VNode` is immutable. `MountedInstance` stores native identity, hooks, refs and event subscriptions. Compatibility during reconciliation is `kind`, `type`, and `key`; compatible nodes retain their handle. `EventSlot` keeps one native binding while replacing the callback. This behavior is a non-negotiable migration invariant.

## Coupling findings

| Area | Current location | Why extension is expensive |
| --- | --- | --- |
| Built-in component definitions and validation | `core/vnode.py` | Builders, defaults, validation and names are concentrated in one module. |
| Markup component knowledge | `markup/compile.py` | `_PRIMITIVES` and special cases for `Text` and `Button` duplicate component semantics. |
| Native implementation | `renderers/{headless,tkinter,kivy,qt/*}.py` | Each renderer branches on host names and carries its own property/update/event rules. |
| Event lifecycle | `core/reconcile.py`, renderer binders | Generic event detection uses the `on_` prefix, while `Native` uses a different signal prefix. |
| Integrations | `integrations/{pydux,qyro}.py` | Integration modules correctly use optional/lazy imports, but couple lifecycle behavior directly to core hooks and renderer selection. |
| Hot reload | `core/component.py`, `devtools/*` | `_COMPONENT_REGISTRY` preserves component identity by module/qualified name and is an existing behavior that a new registry must not replace. |

Portable `Text`, `Button`, and `Input` currently require edits across a builder/validator, markup special cases where applicable, every renderer, tests, exports, and documentation. A new portable component therefore touches at least 7 responsibility areas (and 10+ files for four renderers).

## Observed risks to preserve

- Builder defaults and error classes/messages are observable. For example, `Text()` emits `font_size=16`, while `TEXT_DEFAULTS` is 14; this discrepancy is baseline behavior until deliberately resolved under a compatible policy.
- Markup has constructor-specific child-text rules for `Text` and `Button` and coercion for layout properties.
- `ComponentType` identity survives a compatible hot reload. Registry work must compose with `_COMPONENT_REGISTRY`.
- Existing local changes reveal a baseline Tkinter mismatch: `Button()` supplies `font_size`, while Tkinter validation currently rejects it. This is a pre-M1 regression to resolve without changing the public builder contract.

## Refactoring responsibilities

REF-M1 should introduce internal component contracts while delegating through the existing builders. REF-M2 should make built-ins available automatically through a default registry. REF-M3 should replace `_PRIMITIVES` and compiler special cases with a resolver that preserves markup diagnostics and cache isolation. REF-M4 should move renderer `if node.type` handling into renderer-local adapters while leaving reconciliation generic. No milestone may make registration or a changed import mandatory for existing applications.
