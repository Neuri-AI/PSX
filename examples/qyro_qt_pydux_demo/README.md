# Qyro + PSX declarative demo

This project was scaffolded with the Qyro CLI and then rewritten to use the
opt-in `PSXComponent` adapter. Qyro still creates the `QApplication`, loads
settings/resources and runs its event loop. PSX owns only the VNode subtree
installed as the window's central widget.

`main.py` uses M4B lexical markup: local values and `self` attributes need no
`scope` dictionary. `qyro start` detects inline PSX templates and applies the
static transform to a temporary entry point before launching the application;
the authored file is never rewritten. The demo contains no manual
`mount_psx()` call or duplicate cleanup hook. `PSXComponent` mounts once after
Qyro/Qt completes construction and unmounts the subtree when the host is
destroyed.

From this directory, run it normally with the `osx310` environment:

```bash
qyro start
```

The same automatic preparation is used only when the entry source contains a
literal `psx(...)` call without `scope=`. Other Qyro applications are launched
unchanged.

The demo also shows the single-class Pydux pattern: with one module-level
store, call `use_selector` and `use_dispatch` directly from `render()`.
PSX supplies the `StoreProvider` around that stable root and releases the
Pydux inspector when the host unmounts. Modules with multiple stores can use
`psx_store` to select one explicitly.
