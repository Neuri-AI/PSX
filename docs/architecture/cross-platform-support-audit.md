# Velto cross-platform support audit

**Audit date:** 2026-10-23  
**Tracking:** P4.1 — initial compatibility baseline  
**Status:** evidence collection in progress; **not** a published support promise.

## Purpose and boundary

Establish a source-derived Python/backend/operating-system compatibility baseline before publishing a Velto support matrix. The present increment is documentation and metadata inspection only. No runtime API, adapter, packaged dependency or CI routing has been changed. Public-behavior census: **N/A** (no added or modified public operations).

Source revisions inspected at the start of this audit:

| Repository | Base branch | Exact merge commit | Distribution | Declared Python |
| --- | --- | --- | --- | --- |
| PSX | `develop` | `274d8b9419073cb170ab08c32601a94027f64be3` | `velto-core==0.1.0` | `>=3.10,<3.14` |
| Qyro Engine | `release` | `3e52d4e35e976fd0dea42d41d6e1703eb314fac4` | `qyro-engine==0.1.0` | `>=3.10,<3.13.20` |
| Velto CLI | `release` | `b8e0bb6a5e079b76dd0fc315b84b39cf31fc2275` | `velto-cli==0.1.0` | `>=3.10,<3.13.20` |
| Pydux | `main` | `f32f8d0ead5e7f39b0e846ba0898dcd34c526404` | `pydux==0.1.0` | `>=3.10,<3.16` |

The intersection of the four declared Python requirements is **`>=3.10,<3.13.20`**. This is a metadata intersection, **not** proof that the complete stack passes every Python version in the interval, and not a recommendation to advertise Python 3.13 generally. The Qyro and CLI upper bound is unusual: under PEP 440 it permits some Python 3.13 micro versions, but the exact installation and runtime results must be checked separately.

### Backend constraints observed in package metadata

| Backend | PSX | Qyro Engine | Pydux optional extra | Initial verdict |
| --- | --- | --- | --- | --- |
| PySide6 | `>=6.11`, Python <3.14 | `>=6.8`, Python <3.14 | `>=6.5.0`, Python <3.15 | Declared by all; version and OS matrix **unverified as a whole** |
| PyQt6 | `>=6.8`, Python <3.14 | `>=6.8`, Python <3.14 | `>=6.5.0` | Declared; native integrated coverage still required |
| PyQt5 | `>=5.15`, Python <3.14 | `>=5.15`, Python <3.14 | `>=5.15`, Python >=3.11 and <3.14 | Python 3.10 extra mismatch; resolve without silently dropping advertised support |
| PySide2 | `>=5.15,<6`, Python <3.11 | `>=5.15,<6`, Python <3.11 | `>=5.15`, Python <3.11 | Restricted, older Python path; native verification required |
| Kivy | `>=2.3` | `>=2.3` | `>=2.2` | Tested on several specific native platform/version combinations |
| Tkinter | Built-in adapter, no installation extra | Runtime selector | No optional extra | Depends on platform Tcl/Tk availability; not interchangeable with Python importability |

**Additional packaging discrepancy:** Qyro metadata lists `velto>=0.1.0,<1.0.0`, while PSX's published distribution is `velto-core`. Pydux's `qyro` extra specifies `qyro-engine>=1.0.0a1,<2.0.0` while the inspected Qyro release branch declares version `0.1.0`. Both require dependency-resolution tests and an owner-approved packaging decision before release; do not invent aliases or silently edit version constraints.

Velto CLI's metadata includes classifiers reaching Python 3.15 despite its actual `requires-python` cap. Classifiers do **not** override the cap and must be reconciled before any published compatibility claim.

## Native execution evidence and limits

- Linux native Qt/Tkinter/Kivy mounted refresh, supervised event-loop process replacement and bounded memory cycles: [coordinated refresh execution](https://github.com/Neuri-AI/PSX/actions/runs/39945400491) and [supervised native-process execution](https://github.com/Neuri-AI/PSX/actions/runs/39945030892).
- Windows Kivy with real ANGLE/SDL2 backend: [Windows Kivy job, 10 passed](https://github.com/Neuri-AI/PSX/actions/runs/39951131528), commit `27c8d9e8dc86e2c24b7af42c4263e897e67e92e5`.
- macOS ARM64 Kivy: owner-provided local reports `certification.log`, `environment.txt`, `junit.xml`, `kivy-memory(1).json`; 10/10 passing with macOS 27.0, Anaconda Python 3.12.15, Kivy 2.3.1, PSX `ad350e1545f07b8e715701812b5dcac1ce1427fe`, CLI `75590348b3edb25d0d004bb11e3e2d0d127e5577`. The native memory regression sampled 160 source updates with 32,768 bytes incremental RSS and 5,387 bytes Python allocations (under its defined thresholds).
- The hosted macOS Kivy OpenGL initialization failure is a GitHub runner limitation **distinct from** the successful physical macOS certification.
- Windows hosted Tcl/Tk has shown intermittent installation failures across executions. Keep the result qualified by exact job and SHA.
- These tests certify specific versions and scenarios. They **do not** establish all-Python-version compatibility, application packaging in frozen mode, full Qyro/CLI/Pydux matrix coverage or multi-hour soak.

## Verified / unknown / contradictory

**Verified:** metadata requirements quoted above; specific passing native regression runs; local macOS Kivy report; merged source branch SHAs.

**Not yet verified:** full intersection of backend bindings, Python micro versions and OS architectures; fresh installation from published wheels; frozen `.pak` resource integration; executable examples; documentation correctness page by page; long-term RSS/resource slope and release-gate criteria.

**Contradictory or unresolved:** Qyro's `velto` requirement versus `velto-core` packaging, Pydux `qyro` optional extra versus Qyro's current version, PyQt5 extra restriction across packages, and CLI Python classifiers versus its supported range.

## Next executable increment

Build a deterministic, offline-installable **metadata and dependency-resolution test** against built distributions or installed wheel metadata for the four repositories. Test the declared Python intersections and optional extra combinations before proposing compatible constraint changes. Connect those tests to selective CI routing, capture exact-SHA results, then proceed to native multi-OS installation and frozen-mode verification. The audit itself does not alter public behavior or claim product-test execution.

P4 exit gate remains **OPEN**: public support matrix must match tested evidence; examples must be executable; documentation reviewed page by page; exceptions and release blockers linked.


## Metadata correction approved by owner (2026-10-23)

The owner confirmed that every Velto-family distribution currently has version `0.1.0` and approved one common `requires-python` range: `>=3.10,<3.13.20`. Initial discrepancies were actual stale manifests, not a previously released 1.0 series:

- PSX: set `requires-python = ">=3.10,<3.13.20"`.
- Pydux: set `requires-python = ">=3.10,<3.13.20"`; replace both `qyro-engine>=1.0.0a1,<2.0.0` references (the `qyro` and `all` extras) with `qyro-engine>=0.1.0,<1.0.0`; remove Python 3.14/3.15 classifiers.
- Facade Velto: set `requires-python = ">=3.10,<3.13.20"` and replace the core and every optional-backend `qyro-engine>=1.0.0a1,<2.0.0` reference with `qyro-engine>=0.1.0,<1.0.0`.
- Velto CLI: its existing Python range and Qyro dependency were correct; remove Python 3.14/3.15 classifiers.
- Qyro Engine: its version and Python range were correct; remove `velto>=0.1.0,<1.0.0` as a reverse dependency. The public facade is the consumer of Qyro, not a required dependency of the Qyro runtime; keeping it creates a circular installation dependency.

Python extra dependency *environment markers* use a `python_version` major.minor value, not a full micro version. Therefore their `python_version < '3.14'` constraints are retained where appropriate rather than attempting `python_version < '3.13.20'`. The package-level `requires-python` is authoritative for the exact micro bound.

These changes align manifests; they are not by themselves fresh wheel-install or cross-platform execution evidence. Run the actual packaging and dependency-resolution checks before marking the install-compatibility gate complete. Historical uncorrected metadata above is preserved as the baseline audit trail.


## Completed installability matrix — P4.1 final qualification (2026-10-23)

All five package sources were built as wheels from the current integration branches. The facade's previously overlooked `qyro-engine>=1.0.0a1,<2.0.0` constraints in its optional backend and sentry extras were corrected to `>=0.1.0,<1.0.0` on `Neuri-AI/Velto:feature/backend-wheel-certification`. The first CI attempt also proved why testing only `pip check` is insufficient: pip could select an unrelated `pydux==0.2.2` from PyPI instead of the local source-built `0.1.0`. The final workflow **installs the source-built Pydux 0.1.0 wheel first** and asserts version `0.1.0` for all installed family distributions.

**Executed integrated five-wheel installations:** Python **3.10, 3.11, 3.12 and 3.13** passed building and installing the five `0.1.0` wheels in independent clean environments, `pip check`, `velto --help`, and facade identity checks on Ubuntu. [Wheel/backend CI execution #39957277605](https://github.com/Neuri-AI/Velto/actions/runs/39957277605) contains the executed cells. These outcomes are bounded by the selected interpreter patch versions and the declared common requirement `>=3.10,<3.13.20`; they are not proof of every micro version.

### OS/backend extras (clean wheel installation; NOT GUI rendering)

| Backend extra | Linux, Python 3.12 | Windows, Python 3.12 | macOS ARM64, Python 3.12 |
| --- | --- | --- | --- |
| `velto[pyside6]` | PASS | PASS | PASS |
| `velto[pyqt6]` | PASS | PASS | PASS |
| `velto[pyqt5]` | PASS | PASS | PASS |
| `velto[kivy]` | PASS | PASS | PASS |

| Restricted backend | Linux, Python 3.10 | Windows, Python 3.10 | macOS ARM64, Python 3.10 |
| --- | --- | --- | --- |
| `velto[pyside2]` | PASS | PASS | **UNSUPPORTED: PySide2 5.15 wheel unavailable** |

`tkinter` is supplied with the Python distribution and is not a facade optional extra. Its importability and native Tcl/Tk display operation must be distinguished; the separate PSX native event-loop matrix covers exercised Tkinter paths, including caveats for certain GitHub-hosted Windows runners.

The tested positive cells verify an installable wheel/extra and importable backend with `pip check`; they do **not** automatically imply native window creation, full renderer behavior, frozen packaging, native embedding, or sustained runtime stability. Specifically, a hosted macOS Kivy failure to create OpenGL context in a separate *UI* workflow does not invalidate its successful extra installation or the owner's physical macOS native 10/10 certification.

**Source/version policy:** all first-party distributions remain `0.1.0` with common Python requirement `>=3.10,<3.13.20`. Backend marker expressions (`python_version`) retain major.minor precision and package-level `requires-python` enforces the micro-version bound. Never promote unsupported combinations into the public support matrix.

**P4.1 scope and handoff:** The core support/installation matrix and backend extra resolution checks are complete to the precisely qualified extent recorded above. P4.2 will cover full `VeltoContext` → PSX/Cinnamon → native renderer → Pydux lifecycle integration and behavioral testing. P4.3 will handle frozen `.pak`, packaging and long-duration soaks. Documentation remains canonical in PSX, with CI executable checks in the facade repository.
