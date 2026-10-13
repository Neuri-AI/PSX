# Local native certification matrix

Use the local runner when a native operating-system result is required in
addition to selective CI. It creates one virtual environment per Qt binding,
preserves every command's log and exports JUnit-backed public-behavior receipts
for the exact committed revision it tested.

Run it from a clean checkout of the target branch:

```powershell
# Windows PowerShell (install Python 3.10 and 3.12 with the Python launcher)
py -3.12 scripts/run_local_certification_matrix.py --include-browser-and-rust
```

```bash
# Native Linux partition or macOS (install python3.10 and python3.12 first)
python3.12 scripts/run_local_certification_matrix.py --include-browser-and-rust
```

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
