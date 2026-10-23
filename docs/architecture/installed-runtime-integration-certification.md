# Installed Velto runtime integration certification

**Evaluation date:** 2026-10-23  
**Milestone:** P4.2, cross-package functional integration  
**Status:** P4.2 CLOSED for the explicitly bounded functional integration scenarios; packaging and long-duration UI/system release work remain for P4.3.

## Scope and operating boundaries

Certify the **actual installed distributions** as a single application through the approved boundaries:
`VeltoContext` (Qyro Engine) → `PSX Markup` and mounted reconciler (PSX) → `Cinnamon` (inside PSX; both Rust and Python) → native renderer (PySide6, Tkinter or Kivy) → widget and subscription teardown; Pydux supplies the same live store before, during, and after a state update. Velto facade must re-export the original objects without proxy wrappers.

The test implementation lives at `Neuri-AI/Velto/tests/test_installed_runtime_integration.py`. Its executable jobs live under the existing `Neuri-AI/Velto/.github/workflows/backend-wheel-compatibility.yml`. Cross-repository architectural evidence is owned by PSX, not copied into runtime packages.

## Exercised application path

The integration constructs `settings/base.json` in a temporary project and instantiates the **real** `VeltoContext(custom_root=..., enable_sentry=False)`. Qyro's real `EngineContainer`, environment adapter, JSON settings adapter and metadata loader initialize from the project. The application uses a real Pydux `Store`, `StoreProvider`, `use_selector` and `dispatch(Action(...))`; the actual Qyro root compiler renders a `psx(...)` PSX Markup tree and PSX mounts it. A native Qyro toolkit renderer (or the real PSX headless renderer for the four-version distribution smoke test) commits Cinnamon geometry. The test asserts non-null committed layout, zero geometry commit error, idempotent mount, observable selector-driven rerender and release of the provider's inspector lease after unmount.

Native CI also invokes Qyro's **real window-presentation path**, checking the configured window title through the Qt, Tkinter and Kivy window APIs. CI executes the test under an Xvfb display. This is real native toolkit mounting, not a fake widget or synthetic renderer.

The code verifies the selected Cinnamon backend before the native application run. The **Python** cells intentionally leave `_sfle_native` uninstalled; the **Rust** cells build the actual PyO3 wheel with `maturin`, install it into the integration venv and assert `load_layout_engine().backend_name == "rust"`. The assertions distinguish an executed native Rust engine from an accidental fallback. Both modes share the same application scenario.

## Immutable CI evidence

- **Passing cross-package integration:** [Backend wheel compatibility and native application execution #39962860498](https://github.com/Neuri-AI/Velto/actions/runs/39962860498) (facade tested source revision `2a34b9ff070ed80d72001cad714872c7c46e10eb`). Native jobs are separated by toolkit and layout engine; the workflow also includes the previously approved Python wheel and backend-extras matrix. The final GitHub Actions result is **SUCCESS: 25 of 25 jobs passed**, including six native cross-package app jobs, four Python interpreter builds, fourteen supported backend wheel installations and one explicit expected-unavailability check for PySide2 on macOS ARM64.
- **Prior successful real-bootstrap and selector coverage:** [Python wheel and native execution #39962416364](https://github.com/Neuri-AI/Velto/actions/runs/39962416364), commit `5ef9149b9e612de1e9f9cd3841f74ae6ca4f982f`, 25 of 25 CI cells. The newer job extends the checks to real window title presentation.
- The per-job `source-shas.txt` artifacts identify the PSX, Qyro, Pydux, CLI and facade source revisions actually installed, rather than assuming a moving branch's later head.
- Native backend scope: **Linux x86_64 + Python 3.12**, with PySide6, Tkinter and Kivy in each of Cinnamon Python and Rust variants. The four-version clean headless installed-distribution test covers Python 3.10, 3.11, 3.12 and 3.13 within the approved declared range.
- Native Qt/Tkinter/Kivy process/event-loop and restart scenarios on multiple operating systems were already independently exercised under P3, including [Windows Kivy](https://github.com/Neuri-AI/PSX/actions/runs/39951131528) and the owner's physical macOS ARM64 Kivy results. Those are **different exact revisions and different scenarios** and are not presented as executing this new cross-package integration test on all operating systems.

## Acceptance and deferred coverage

**The bounded P4.2 integration criterion is satisfied** when the six native jobs and four installed-wheel Python-version jobs are green on the same facade revision: real Qyro configuration → PSX Markup root → actual Cinnamon geometry with both Rust and Python → native toolkit handles → Pydux selector state change → idempotent mounting and provider cleanup, with no new public API.

This test does **not** certify every Qt binding through the complete context-to-native pipeline. PyQt5/PyQt6/PySide2 wheel installability was independently characterized in P4.1; platform-specific native renderer behaviors retain their separate PSX verification. Kivy and Qt do not use an interchangeable GUI event loop. No fake backend substitutes for an unsupported native combination.

The following are expressly **out of scope** and remain open for P4.3/release-level validation: hours-long native resource soak, PyInstaller or frozen `.pak` resource resolution, release signing, actual installed package start from the CLI beyond the already verified `velto --help` and P3 restart supervision, documentation example reproduction across every backend/OS, and the complete public release matrix.

Public-behavior census: **N/A** (tests and CI only; no new public props, events or interfaces). No production runtime behavior was changed.

## Handoff

- **Task:** certify the installed end-to-end Velto UI and state pipeline.
- **Repos:** test/CI merged through [Velto PR #3](https://github.com/Neuri-AI/Velto/pull/3) into facade `main` at merge commit `a0ecce6944138918795ce394e421cc6315dc4572`; architectural documentation in PSX `feature/cross-platform-certification`; Qyro `release`, Pydux `main`, PSX `develop`, CLI `release` used as source-built dependencies.
- **Contract:** the P4 integration layers in `velto-master-execution-plan.md`, PSX `AGENTS.md`, and `capability-certification-policy.md`.
- **Changed public behavior:** none. Runtime wrappers or compatibility shims: none.
- **Tests:** wheel installation and native runs recorded in CI; source-SHA artifacts are the audit basis.
- **Compatibility risk:** SDL2/Cocoa and Windows Tcl/Tk runner restrictions do not imply successful GUI runs on unexecuted combinations.
- **Next safe work:** P4.3 executable frozen assets and packaging, full example application workflows and longer-term memory/resource stability, using the just-certified real application as a baseline.

## Closure decision

The functional integration acceptance criteria for P4.2 have executed evidence and are **CLOSED**. A complete, all-green run is recorded at [#39962860498](https://github.com/Neuri-AI/Velto/actions/runs/39962860498): 25/25 successful jobs (6 native Qyro/PSX/Cinnamon/Pydux mounted scenarios and 19 installation/matrix checks), source revision `2a34b9ff070ed80d72001cad714872c7c46e10eb`. Its changes have been integrated to Velto `main` by [PR #3](https://github.com/Neuri-AI/Velto/pull/3), merge `a0ecce6944138918795ce394e421cc6315dc4572`. This is a functional gate only, not an assertion of a fully certified all-platform release. P4.3 remains open.
