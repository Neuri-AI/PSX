# Local native certification matrix

Use the local runner when a native operating-system result is required in
addition to selective CI. It creates one virtual environment per Qt binding,
preserves every command's log and exports JUnit-backed public-behavior receipts
for the exact committed revision it tested.

Run it from a clean checkout of the target branch:

When Conda manages the environments, activate one and use it directly. The
first run installs the selected binding packages into that environment:

```powershell
conda activate psx-310
python scripts/run_local_certification_matrix.py --active-conda --python-version 3.10 --include-browser-and-rust
```

Use Python 3.10 with all supported bindings, including PySide2. Then run
Python 3.11, 3.12 and 3.13 with every selected cell *except* PySide2:

```powershell
conda activate psx-313
python scripts/run_local_certification_matrix.py --active-conda --python-version 3.13 --only core,headless,pyside6,pyqt6,pyqt5,kivy,tkinter,browser,rust --include-browser-and-rust
```

The same commands work on native Linux and macOS after activating the matching
Conda environment. Without `--active-conda`, the runner retains its original
mode: it creates isolated virtual environments and uses Python 3.12 for the
main matrix plus Python 3.10 for PySide2.

The report directory is printed at the end and contains:

- `report.html`: every combination, status, duration and a link to its log.
- `report.json`: the same data for automation.
- `public-*.xml`: original JUnit outputs.
- `public-*-inventory-receipts.json`: feature receipts bound to the tested SHA.
- `public-behavior-aggregate.json`: the combined census for that machine.

The runner refuses a dirty checkout by default because an uncommitted tree
cannot supply immutable-SHA certification. `--allow-dirty` is available only
for diagnosis and does not make its output certifiable. Use `--reuse-envs` on
subsequent runs to retain virtual environments; reports remain separate.

Run the complete command on Windows, native Linux and macOS. WSL is useful for
Linux-oriented diagnostics, but native Linux should provide the Linux GUI
evidence. Do not combine reports from different commit SHAs. A green local
report confirms its executed cells only; final closure still requires the
complete cross-platform receipt aggregation with no applicable pending or
failed rows.
