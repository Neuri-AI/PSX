# Inline complex literal props (M4B)

Developer-authored PSX Markup may pass Python collection literals directly to component props. This is an optional shorthand; prefer Python variables for substantial or reused data.

```python
@component
def Welcome(user: dict):
    return psx('<Text>{user.name}</Text>')  # Access semantics depend on the component's data model.

@component
def Demo():
    user = {"name": "User", "age": 30}
    return psx('<Welcome user={user} />')
```

Inline alternative:

```jsx
<Welcome user={{"name": "User", "age": 30, "tags": ["a", "b"], "position": (10, 20)}} />
```

The inline grammar supports Python dict, list and tuple literals, nesting, and lexical values such as `{"name": name}`. Python-style quoted keys and `True`, `False`, `None` are used; JavaScript shorthand `{name: "User"}` is not recommended. The expression is compiled statically by M4B into Python AST, not evaluated as text. No `eval`, `exec`, or frame introspection is introduced.

This extension applies only to statically authored, transformed M4B templates. M4A runtime templates remain restricted. Bare braced scalar attributes such as `gap={12}` remain invalid; write `gap="12"`. Malformed structures should raise source-positioned `MarkupSyntaxError`.

## Certification criteria

Run the focused inline-props regression tests, existing M4A/M4B/expressive suites, and the repository's CI workflow. Do not declare certification until the executions pass on the target branch.
