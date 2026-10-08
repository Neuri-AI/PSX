# M4B static lexical transform

M4B enables ergonomic inline developer-authored markup without runtime frame
inspection. Transform a Python module before running, testing, or packaging it:

```bash
psx-transform app.py --output build/app.py --source-map build/app.psxmap.json
```

The transform finds a literal call such as:

```python
return psx("<Text>{count}</Text>")
```

and emits a module-level compiled template factory plus a call equivalent to:

```python
return _psx_template_0.render_lexical({"count": lambda: count})
```

`count` remains an ordinary Python lexical name, so local variables, closures,
shadowed bindings and callbacks follow Python's own scoping rules. The factory is
created once when the transformed module imports, not once per component render.

The same applies to instance methods and parser-validated dotted paths. No
intermediate `scope` dictionary is needed:

```python
def render(self):
    return psx("""
        <Column padding={50}>
            <Text>App Title: {self.window_title}</Text>
            <Text>Platform: {self.platform.value}</Text>
            <Button on_click={self.open_settings}>Settings</Button>
        </Column>
    """)
```

The generated thunk resolves `self` afresh for every render, and the restricted
markup compiler follows only the declared attribute segments. A callback such as
`self.open_settings` is passed as a value; it is never called while rendering.
Missing roots and attributes produce `MarkupSyntaxError` diagnostics at the
original markup location.

M4A is unchanged: calls with `scope=` remain explicit-scope templates and permit
dotted access only through mappings. M4B is the opt-in static transform for
Python lexical names and object attributes. Neither mode evaluates arbitrary
Python expressions, captures frames, or uses `eval`/`exec`.

Only direct `psx("literal")` calls without `scope=` are transformed. Dynamic
templates and explicit-scope calls remain M4A calls. The transform has no
security role for external templates; those must continue using M4A's restricted
explicit-scope language.

M8's `psx-dev` supervisor applies this same static transform to a temporary
child entry point on each restart. It does not rewrite the authored source;
syntax diagnostics retain the original filename passed to the transform.
