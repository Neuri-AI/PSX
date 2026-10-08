# M12 — PSX Playground & Visual Layout Inspector

**Status:** implemented development vertical slice. The playground is the
standalone React project in [`../../playground`](../../playground), not a
module or command in the `psx` Python package.

The application provides a Monaco editor, editable markup, built-in examples,
source diagnostics with line/column locations, generated safe
`psx(..., scope=...)` wrapper code, a semantic preview, and an inspector tree.
Selecting a node exposes its estimated bounds, padding, spacing, alignment,
hierarchy, and props. The inspector can temporarily edit only `padding` and
`spacing` on layout nodes; it never mutates source or executes user code.

The preview parses a safe PSX markup subset but does not evaluate references,
import modules, instantiate native controls, or claim pixel parity with Qt,
Tkinter, or Kivy. `Native` is intentionally represented as a semantic
placeholder. This keeps the browser tool safe and honest; native inspection
remains renderer-specific future work.

Run the web project independently:

```bash
cd playground
# Run this first if the terminal has not loaded NVM/Node yet.
nvm -v
npm install
npm run dev
```

Vite reports the local browser URL. `npm run build` verifies the production
bundle; `npm run preview` serves that bundle locally.
