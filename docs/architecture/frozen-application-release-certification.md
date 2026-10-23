# Velto frozen application, protected resources and sustained resource lifecycle

**Date:** 2026-10-23  
**Tracking:** P4.3 (distribution and native resource stability)  
**Status:** P4.3 CLOSED for the tested Linux distribution and sustained-runtime scenarios; broader cross-platform release qualification remains separate.

## Scope and design authority

This certification uses real, installed Velto `0.1.0` distributions built from the integrated PSX `develop`, Qyro Engine `release`, Pydux `main`, Velto CLI `release` and facade feature source. No fake native renderer, resource resolver, PyInstaller bootloader, `.pak` provider or Python state store is substituted. Architecture documentation stays in PSX. Tests/CI are under the facade repository's `tests/certification/` and `.github/workflows/` paths, respecting repository boundaries.

Two separate capabilities have independently executed coverage:

1. **Frozen distribution:** A real `VeltoContext` application with PSX Markup and a Tkinter window is built using `velto build`. The CLI creates an encrypted and authenticated `.velto/resources.pak` and includes the compiled runtime secret. The application asserts `is_frozen`, checks Qyro metadata and reads `fixtures/token.txt` using its public `get_resource` API; the expected bytes are not supplied as a separate source resource. `velto bundle --format tar.gz --no-resources` creates a distributable archive. The certification extracts it, explicitly confirms the absence of a raw `resources/` directory, launches the actual executable from an isolated working directory via Xvfb, exercises the native event loop and requires the success marker. Python versions 3.11/3.12 and both onedir/onefile have independently executed passing release jobs.
2. **Sustained UI/resource ownership:** A real, mounted Tkinter application uses `VeltoContext`, JSON settings, PSX Markup, Pydux Store/StoreProvider/`use_selector`, and Cinnamon native geometry. Its 2,000 store dispatches are spread over **at least 120 seconds**, with Tcl events processed and 20 `psutil` RSS plus `tracemalloc` Python allocation samples taken every 100 updates. The final state must be observed after flushing queued native events. After the 300-update warmup, the remaining RSS growth must stay below **64 MiB** and Python allocation growth below **12 MiB**. The provider's inspector lease must be zero after teardown. Separate jobs assert actual **Python fallback** and built/installed **Rust PyO3** Cinnamon backends; the latter is never silently substituted with Python.

## Executed evidence (immutable SHAs)

- [Frozen native application, installed PyInstaller binary and Qyro .pak #39965401657](https://github.com/Neuri-AI/Velto/actions/runs/39965401657): **PASS** for Linux Python 3.11 and 3.12, onedir direct binary, before the subsequent release archive addition. This is genuine protected-resource resolution from frozen mode.
- [Unpacked release archive #39966850872](https://github.com/Neuri-AI/Velto/actions/runs/39966850872): **PASS 2/2** Linux Python 3.11 and 3.12 for protected onedir archive packaging and isolated execution; tested facade SHA `f1ebb3e2cf003b8ed43e8240642c2efea4c565c3`.
- [Sustained native lifecycle #39966232424](https://github.com/Neuri-AI/Velto/actions/runs/39966232424): **PASS 2/2** for Tkinter/CPU x86_64 with real Python and Rust Cinnamon engines, 2,000 native state updates over two minutes, retained memory limits and teardown. Tested facade SHA `ccda6bce156ebdb3e53bd91b244965dd8bdbfaaa`. Logs and raw measurements are archived as `sustained-native-python` and `sustained-native-rust`.
- [Cross-package integrated native application #39962860498](https://github.com/Neuri-AI/Velto/actions/runs/39962860498): **25/25 PASS**, earlier P4.2 receipt exercising native PySide6, Tkinter, Kivy and both Cinnamon engines with live Pydux state and Qyro settings. This is not a frozen packaging result.

## Result boundaries and risks

The frozen tests prove **Linux Tkinter** distribution, both onefile and onedir release archives, and .pak access. They do not prove signed/notarized macOS apps, Windows installer generation, frozen PySide6 or Kivy packages, or every CPU architecture. The resource soak is **two minutes per engine**, not multi-hour or overnight stability; no broader lifetime claim is supported. Python version 3.13 has package-resolver evidence from P4.1 but is not part of these frozen jobs. Encryption tamper, encrypted secrets and protected-resource extraction are already covered in Qyro's dedicated `tests/test_protected_bundle_runtime.py` but require their own executed versioned CI receipt before including them as end-to-end frozen release evidence.

The project fixture explicitly sets `settings/base.json` version to `0.1.0`. The CLI release bundler reads the setting rather than `build.json` when determining its tarball filename; silently assuming the build manifest version generated a failed CI run. The `velto bundle` guard also requires a valid project `pyproject.toml`. The fixture now meets those real prerequisites rather than bypassing the CLI.

**Census:** N/A: no new public props, methods, event contracts or runtime behavior. Only certification fixtures, shell workflows and PSX evidence documents have been added. These tests must remain regression checks before advertising frozen distribution support.

## Exit and handoff

P4.3 distribution and resource-stability scenarios are certified only for the explicitly passing matrix cells. A global Velto release certification remains **OPEN** until Windows/macOS frozen binary and installer/signing/notarization qualifications, relevant frozen Qt/Kivy paths, longer duration measurements and usable released example projects have evidence. The next P4 documentation/release gates must explicitly link those exceptions and not inflate this Linux proof into a universal platform claim.

## Same-revision final CI closure

**Exact tested facade revision:** `92928b2a59708a3a7716edac71bcb614a64d8d80`.

- [Four-way frozen distribution run #39967824985](https://github.com/Neuri-AI/Velto/actions/runs/39967824985) — **4/4 PASS**, Linux CPython 3.11 and 3.12 × PyInstaller `onedir` and `onefile`; each invoked `velto build` → real `.pak` → `velto bundle --no-resources --format tar.gz` → archive extraction → isolated native window/event loop and protected `get_resource` read.
- [Sustained native runtime run #39967825020](https://github.com/Neuri-AI/Velto/actions/runs/39967825020) — **2/2 PASS**, Linux CPython 3.12 × real Cinnamon Python/Rust, 2,000 real native Tkinter Pydux selector updates over >=120 seconds per engine; recorded memory samples and tested bounded RSS/allocated-Python growth plus final teardown. This is not an hours-long soak.

**P4.3 scoped acceptance decision: CLOSED** with 6/6 same-commit jobs. Repeated package builds and real native source-independent execution have verified the distribution and protected resource path for Linux Tkinter, while native state ownership is separately verified under both Cinnamon engines. No PSX, Qyro, Pydux or CLI production change and no public-behavior census required. Cross-platform signed frozen deliverables, PySide6/Kivy frozen applications and longer soaks are explicitly outstanding *release qualifications*, not silently certified by these six Linux jobs.

**Integration result:** certification fixtures and their two workflows merged into Velto `main` through [PR #4](https://github.com/Neuri-AI/Velto/pull/4) at commit `53b9fd9eda66189535e1c7284dd0e3df7519c207`. The exact passing source revision remains `92928b2a59708a3a7716edac71bcb614a64d8d80`, not the merge commit. Cross-repo architecture remains in PSX; no source release signing or Windows/macOS frozen claim was added.
