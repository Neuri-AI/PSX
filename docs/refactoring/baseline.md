# REF-M0 baseline

Captured on 2026-10-08 with Python 3.12.4 on Windows 11. The committed machine-readable benchmark artifact is `benchmarks/ref-m0-baseline.json`.

## Tests

Initial full collection: 91 items, stopped at collection because `pydux` and `PySide6` are absent. The affected modules are `test_pydux_integration.py`, `test_pyside6_renderer.py`, and `test_qyro_integration.py`.

Runnable baseline command:

```powershell
python -m pytest -ra --basetemp .pytest-ref-m0 --ignore=tests/test_pydux_integration.py --ignore=tests/test_pyside6_renderer.py --ignore=tests/test_qyro_integration.py --ignore=tests/test_kivy_renderer.py
```

Result: 85 passed, 2 skipped (PyQt5/PyQt6 absent), 3 failed.

1. Tkinter: `Button.font_size` is rejected by `TkinterRenderer._validate_props` despite being emitted by `Button()`.
2. Devtools watcher: atomic replacement debounce expectation fails.
3. Devtools supervisor: transformed child cannot import `psx` because the test supplies the obsolete `src` path.

Kivy is absent and its test is not currently guarded by an optional-dependency skip. Qyro+PSX and Pydux+PSX remain unverified in this environment; their existing tests must be included in every later milestone when their dependencies are installed.

REF-M1/REF-M2 compatibility follow-up: the Tkinter `Button.font_size` failure remains intentionally preserved as an observable baseline behavior. REF-M2's latest available command produced 96 passed, 2 skipped and 2 failures; the atomic-save watcher failure did not reproduce and remains tracked as intermittent.

## REF-M4 environment correction

The REF-M0 record above is preserved as the historical default-interpreter baseline. REF-M4 validated the required Conda `playground` environment instead: Python 3.13.16 at `C:\Users\luisp\.conda\envs\playground\python.exe`, with PySide6, PyQt5, Kivy, Qyro and Pydux installed. Its full suite command used a repository-local pytest base directory and produced 137 passed and 1 PyQt6 skip. The historical failures were not suppressed by test changes; the portable `Text` default and Tkinter `Button.font_size` compatibility behavior were corrected so the existing tests pass in the intended environment.

The REF-M0 characterization test covers standalone Python builders, runtime markup, declarative components, key/ref behavior, state scheduling, identity preservation and stable event slots using the headless renderer. Existing suites cover the static transform, native widgets, available Tkinter and optional Qt/Kivy paths.

## Benchmark

Command:

```powershell
$env:PYTHONPATH='.'; python benchmarks/psx_benchmark.py --size 100 --iterations 30 --repeats 3 --write-baseline benchmarks/ref-m0-baseline.json
```

Selected mean latency (milliseconds): mount/unmount 1.7817; full update 1.9110; single-property update 1.4231; keyed reorder 1.5248; markup render 0.8773; markup compile 2.8653; static transform 0.2055. Native GUI performance is intentionally not represented because it is host/window-server dependent.
