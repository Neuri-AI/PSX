# Reuse Tkinter rounded-card paint during resize

## Problem and correction

At baseline `ef2d9cc8acdd08a228155120c59730e66d1e4dec`, every rounded CSS
surface Configure deleted its Canvas items, supersampled four RGB corners
in Python, PNG-encoded them and created four Tk PhotoImages. This work ran
on the UI thread regardless of the Cinnamon engine. The previous unstyled
Flex/Text Grid benchmark did not cover it. A video demonstrates user-visible
lag and CPU increases on macOS, but cannot attribute their entire cause.

The renderer now keeps one set of images per Canvas and paint signature:
effective radius (including size clamping), parent/fill colors and side
strokes. Size-only changes move existing items and resize the straight fill
and border rectangles. Paint changes regenerate the images, obsolete items
are removed, and stacking remains fill → borders → corners. There is no
shared interpreter resource cache. Cinnamon's solvers, native measurement,
transaction/readback and widget identities are unchanged.

## Controlled comparison

Environment: Linux x86_64; Python 3.12.14; native Tcl/Tk 9.0.4; Xvfb 21.1.12
on a 1600×1000×24 display over loopback TCP; Cinnamon Rust release wheel,
compiled with rustc 1.99.1. Backend selection is checked by the benchmark;
a Python fallback cannot silently produce a Rust result.

Six styled cards, 5 warmups and 30 measured resizes per run; widths
680/760/800/900/1000/1200/980/750. Three runs for each painter, alternating
before→after, after→before, before→after in one process. Both variants used
the same current benchmark/layout/solver code; the baseline painter was
loaded from `git show ef2d9cc8:psx/renderers/tkinter/rounded_surface.py` and
swapped into the module before each run. No cProfile was enabled.

| Mean across the three runs | Baseline painter | Reused painter |
| --- | ---: | ---: |
| Native event → commit end | 54.39 ms | 27.24 ms |
| Resize request → event-loop settled | 57.65 ms | 31.10 ms |
| Per-run p95 request → settled (mean) | 77.07 ms | 50.21 ms |
| Process CPU time per resize, including event-loop drain | 48.94 ms | 26.26 ms |

Request-to-settled wall time decreased 46.1%; process CPU per resize decreased
46.3%. Per-run aggregates are in `tkinter-rounded-resize-samples.json`.
These numbers characterize this workload/environment. They are not desktop
CPU percentages, FPS, or macOS compositor presentation measurements. The
remaining latency is still above a 16.7 ms frame budget; this does not close
the overall user-perceived smoothness issue.

The isolated original Python corner raster/PNG workload for five radius-8
cards averaged 16.87 ms over 30 repetitions, excluding native image creation,
layout and presentation. This isolates one avoidable cost, not all resize work.

## Verification

- RED: the resource/item reuse regression fails against the original painter
  because each resize replaces all item IDs.
- GREEN: 205 tests plus 214 subtests passed, 4 unsupported cases skipped, in
  the native Tkinter renderer/layout/external ports, Grid measurement/commit
  and CI routing suites using extracted system Tcl/Tk 8.6.14.
- GREEN: 202 tests passed, 6 unsupported cases skipped, in mounted native Grid,
  Tk public behavior and native rounded raster suites on Tcl/Tk 8.6.14.
- GREEN: all 20 native rounded visual tests passed independently on Tcl/Tk 9.0.4,
  including fresh-versus-resized pixel equality and Qt/QSS raster comparison.
- The broader Tcl/Tk 9 run had 198 passes and seven existing ttk padding
  conversion failures at unchanged `tkinter.py:1877` (`Tcl_Obj` to int).
  These are outside this painter correction; the primary native suite is green
  on Tcl/Tk 8.6. No macOS execution is claimed by local Linux tests.

Native test commands (with DISPLAY provided):

```sh
python -m pytest -q tests/test_tkinter_renderer.py tests/test_tkinter_native_layout.py tests/test_tkinter_external_native_ports.py tests/sfle/test_grid_native_measurement.py tests/sfle/test_grid_native_commit.py tests/test_ci_impact.py
PSX_GRID_BACKEND=tk PSX_CORNER_VISUAL_OUTPUT=/tmp/rounded-visual python -m pytest -q tests/test_mounted_grid_native_renderers.py tests/test_tk_public_behavior.py tests/test_native_rounded_card_visual.py
```

The Aqua CI suite now also checks that real window Configure events preserve
corner image and Canvas item identities. This is an additional native
regression, not proof of compositor frame cadence. Same-SHA CI results must
be read from the commit's workflow runs; this report does not predeclare them.

No public props/events/methods or interactions were introduced; new public
census cells are N/A. Existing public behavior tests remain regression evidence.
The selector routes painter/visual/benchmark changes to Qt and Tkinter, and
the dedicated performance workflow executes styled Python and Rust resizes.

## Reproduce the styled workload

On a desktop, omit Xvfb to exercise the actual native window system:

```sh
python benchmarks/grid_resize_interactive.py --adapter tk --engine rust --cards 6 --cycles 100 --warmup 10 --styled
```

On Linux CI, prefix with `xvfb-run -a`. The JSON includes process CPU and full
request-to-event-loop-settled time alongside event-to-commit latency. It keeps
`presentation_feedback_supported=false` and `frame_rate_fps=null`.
