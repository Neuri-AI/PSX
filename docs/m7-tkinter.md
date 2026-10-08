# M7 Tkinter renderer

`TkinterRenderer` maps the initial portable PSX subset to ttk widgets:

| PSX | Tkinter |
| --- | --- |
| `Column` | `ttk.Frame` with vertically packed children |
| `Row` | `ttk.Frame` with horizontally packed children |
| `Text` | `ttk.Label` |
| `Button` | `ttk.Button` |

`padding` becomes frame padding. `spacing` is applied as `padx` for rows and
`pady` for columns, including the outer edge; this is intentionally an
approximation, not Flexbox gap semantics. PSX owns `pack` for descendants of a
PSX-created frame. Do not mix `grid` or `place` into that same subtree.

Updates from worker threads are placed in a thread-safe queue and drained by
Tk's `after()` loop on the UI thread. `flush()` exists only for deterministic
tests and must be called on the Tk UI thread.

Tkinter is supplied by the Python distribution rather than a PSX pip extra.
Create an app with `App(root, renderer="tkinter")`, or pass a `TkinterRenderer`
created with an existing `tk.Tk` root for host ownership control. Unsupported
props raise `RendererCapabilityError`; styling, inputs, grids, native widgets,
and full geometry semantics remain later milestones.

When mounted through Qyro, PSX borrows Qyro's existing `tk.Tk` root rather than
creating a second window. Qyro brings that root forward before entering its
main loop. Native smoke testing on macOS must still run in a regular GUI login
session; headless Cocoa environments can abort before Tk creates any window.
