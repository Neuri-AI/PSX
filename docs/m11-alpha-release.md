# M11 — Alpha Release

**Status:** alpha release candidate. M11 defines a reproducible and bounded
release surface rather than claiming that every installed GUI backend has been
tested in every environment.

## Release assets

- `pyproject.toml` supplies PEP 621 metadata, a README, MIT license, Python
  requirement, optional renderer/integration extras, and the `psx-transform`
  and `psx-dev` entry points.
- `README.md` documents installation and alpha expectations.
- `CHANGELOG.md` records alpha capabilities and known limitations for release
  notes.
- [public-api.md](public-api.md) identifies supported imports; private handles
  are explicitly outside the compatibility contract.
- [compatibility.md](compatibility.md) documents the validated matrix and its
  graphical-session limitations.
- [benchmarks/psx_benchmark.py](../benchmarks/psx_benchmark.py) separates
  VNode construction from reconciliation. It measures full, single-node, and
  no-op keyed updates; mount/unmount; reorders; event replacement/cleanup;
  scheduler updates; markup render/compile; M4B transforms; mean, median and
  p95 latency; plus Python peak/retained allocation after collection. It emits
  JSON, accepts same-machine baselines, and keeps CI timing-neutral. Memory is
  measured in an equivalent second pass so `tracemalloc` instrumentation does
  not distort latency results.

## CI and release gate

`.github/workflows/ci.yml` runs deterministic core/M4B/devtools tests on Python
3.10 and 3.12, an offscreen PySide6 smoke suite, a reconciliation benchmark,
and an isolated wheel/sdist build. Tkinter and Kivy require a logged-in native
desktop session for their final smoke test and remain documented manual gates.

Before publishing an alpha tag:

1. Run `python -m pytest -q tests` in each supported local graphical setup.
2. Run `python -m build` and inspect both artifacts.
3. Run `PYTHONPATH=src python benchmarks/psx_benchmark.py --write-baseline
   .bench.json`, then compare a later run using `--baseline .bench.json` on
   the same machine.
4. Verify every example against the matching Qyro binding and ensure M4B's
   `psx-transform` remains executable.
5. Record known backend-specific limitations in the release notes.

Development hot-reload tooling is optional and does not become a production
runtime dependency.
