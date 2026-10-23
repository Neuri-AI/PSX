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
