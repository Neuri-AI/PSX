# Tkinter resize investigation — 2026-10-28

- Repository: Neuri-AI/PSX; branch: fixes/psx-issues.
- Starting revision: ef2d9cc8acdd08a228155120c59730e66d1e4dec.
- Goal: reduce native resize work while preserving Cinnamon's sole geometry
  authority, widget identity, CSS pixels and transactional layout validation.
- Immediate deliverable: reuse canvas corner images and drawing items when
  only surface dimensions change, with a styled native resize benchmark.
- Exit criteria: native regressions for reuse, paint invalidation, effective
  radius changes and teardown; real raster parity; repeated controlled
  before/after timings; exact-SHA CI reported separately from local tests.
- Out of scope: new layout algorithms/APIs, moving Tk calls off its owning
  thread, claiming compositor/frame presentation evidence from Xvfb.

## Verified starting state

Tkinter's Aqua Configure handler commits synchronously. The layout bridge
still measures native widgets, solves Cinnamon snapshots and drains Tk idle
work on the UI thread. Rust accelerates the solver only. The rounded CSS
painter (`psx/renderers/tkinter/rounded_surface.py`) deletes all canvas items,
rasterizes four supersampled corners and creates four PhotoImages at every
size change, including when radius/colors/strokes have not changed. The
existing Grid benchmarks use unstyled Flex/Text cards and miss this cost.

Public facade and keyed reconciliation remain in `psx/__init__.py` and
`psx/core/reconcile.py`; layout ownership remains in `psx/sfle/`. No parser,
reconciler, Pydux/Qyro packaging or component API changes are required.
Python supports >=3.10,<3.13.20; native backends are Qt, Tkinter and Kivy
with Headless coverage. This checkout runs Python 3.12.14 on Linux; live
macOS Aqua presentation is unavailable locally.

## Contracts and validation

Read master execution plan, responsive Grid contract, capability certification
policy, runtime/certification boundaries and commit conventions. This is a
private renderer performance fix with no new props/events/methods or public
interactions; new public census cells are N/A. Existing native tests and
public interaction regressions remain required. Router already selects
Qt reference plus Tkinter for changes to rounded_surface.py.

Commands/results and final performance evidence will be recorded in
`docs/performance/tkinter-rounded-resize.md` after implementation.
