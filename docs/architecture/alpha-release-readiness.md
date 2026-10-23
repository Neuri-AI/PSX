# Velto alpha release preparation and verified support boundaries

**Review:** 2026-10-23  
**Tracking:** P4.5, example reproduction and alpha-release preparation  
**Documentation owner:** PSX (architecture and public developer docs)  
**Status:** documented native beginner application reproduced successfully; source-alpha preparation checklist ready, but no published release, signed binary or all-platform frozen support is claimed.

## Version and API boundaries

The five repositories agree on the first-party `0.1.0` release series and `requires-python = ">=3.10,<3.13.20"`. The Python 3.10–3.13 installations were tested for the exact CI-selected interpreter patch versions, not every micro release. The ecosystem is sourced directly from GitHub until its distributions become available on PyPI; public installation pages must not falsely assert a PyPI release.

The existing Velto facade re-exports the PSX, Qyro Engine and Pydux identities, while the CLI creates projects and handles development/frozen packaging. Markup is **PSX Markup** (HTML/JSX-like), without browser DOM or a `<Window>` tag. Cinnamon lives **inside** PSX and owns geometry; the Rust implementation is primary with Python fallback.

## Executed acceptance evidence already available

| Area | Exact execution | Qualification |
| --- | --- | --- |
| Python packages and backend extras | [Velto 19/19](https://github.com/Neuri-AI/Velto/actions/runs/39957504956) | Python 3.10, 3.11, 3.12, 3.13 wheel resolver; PySide6, PyQt6, PyQt5, Kivy install checks on Linux/Windows/macOS ARM64; PySide2 on Python 3.10 Linux/Windows, unavailable on macOS ARM64 |
| Application lifecycle and Pydux subscriptions | [Velto 25/25](https://github.com/Neuri-AI/Velto/actions/runs/39962860498) | Real Linux PySide6, Tkinter, Kivy native mounts under Rust and Python Cinnamon; not cross-OS full integrated qualification |
| Kivy real event-loop replacement | [PSX Windows](https://github.com/Neuri-AI/PSX/actions/runs/39951131528) | Windows native Kivy using ANGLE + SDL2; physical Mac ARM64 Kivy separately owner-run 10/10 with Python 3.12.15 |
| Protected frozen application | [Velto Linux 4/4](https://github.com/Neuri-AI/Velto/actions/runs/39967824985) | Tkinter Python 3.11/3.12, PyInstaller `onedir`/`onefile`, `.pak`, extracted `tar.gz` |
| Sustained resource regression | [Velto Linux 2/2](https://github.com/Neuri-AI/Velto/actions/runs/39967825020) | 2,000 Tkinter state changes over >=120 seconds per Cinnamon engine |
| Historical PSX lesson examples | [PSX documentation validation](https://github.com/Neuri-AI/PSX/actions/runs/39972479724) | Existing pinned historical headless/native examples independently reproducible within their documented CI scope |
| Exact new public Hello app | `tests/certification/verify_documented_hello.py`, workflow `documented-example-reproduction.yml` | Must finish with actual green CI on the current SHA; never substitute the historical PSX headless hello example as proof of this specific new facade snippet |

## Alpha publication gates

| Requirement | Status and release consequence |
| --- | --- |
| Installation of five first-party 0.1.0 GitHub packages | **Verified** at selected Python versions/OS cells; clean install instructions must use GitHub |
| Native Qyro → PSX → Cinnamon → Pydux lifecycle | **Verified** on Linux for specified toolkits and engines |
| Beginner's published example executed byte-for-byte | **Verified** with GitHub Actions #39974488324, 2/2 on Linux Python 3.11/3.12, source SHA `34f411eeb16e8084e20b6e406e8b096f9f20156d` |
| Public support matrix and known incompatibilities | **Documented** in `docs/public/guide/compatibility.mdx`; retain PySide2/macOS ARM64 exclusion |
| Documentation site and source-generated public API signatures | **Verified** in P4.4 docs workflows, with new changes revalidated on their own SHA |
| Human-independent reproduction of *every* published tutorial on every platform | **Not established**; historical native examples and new exact-copy test do not cover all pages |
| Windows/macOS frozen binaries and app installer workflows | **Not certified**; do not advertise these as finished deliverables |
| macOS code signing/notarization and Windows binary signing | **Not certified**; do not claim distribution trust or store-readiness |
| Frozen PySide6/Kivy and other bindings | **Not certified**; Linux Tkinter frozen results cannot be generalized |
| System GUI focus, DPI, resize, nested scroll and asynchronous interactions on full OS/backend matrix | **Incomplete**; different historical test receipts are not an all-in-one release acceptance run |
| Multi-hour/overnight native memory and resource endurance | **Not certified**; current sustained test lasted at least two minutes |
| Release tagging, package publication and GitHub release artifacts | **Not performed**, require explicit publication decision |

**Publication verdict:** source-available alpha/developer-preview documentation can describe the **tested narrow subset** and explicitly label remaining limits. A claim of **fully certified cross-platform binary distribution** is **BLOCKED** by the missing frozen/signing/long-duration and complete GUI coverage above. This checklist must not be converted into a claim of a release that was never actually tagged or published.

## Reproduction process for beginner documentation

The [executed exact-copy receipt](https://github.com/Neuri-AI/PSX/actions/runs/39974488324) passed both tested Python versions. The version-controlled example at `examples/documented_hello/` is synchronized with the exact `settings/base.json` and `main.py` fenced blocks in `docs/public/getting-started/first-app.mdx`. The test copies the snippets from the *page*, not from the example directory, into an isolated project root, installs real ecosystem GitHub sources, and checks a real PySide6 widget and Cinnamon geometry. The test's subprocess owns its native QApplication and must unmount the Qyro context.

The test executes the original `main.py` through a bounded real Qt event loop as well as verifying the native widget and layout. A separate standalone manual reader session was not performed; this is automated reproduction, not human usability signoff.

## Next decisions before announcing an alpha

1. Choose the exact cross-repository tags/SHAs as one immutable release bill of materials; no inferred PyPI publication.
2. Decide whether the release artifact scope is **source/developer preview only** or includes native installers. If installers, complete relevant OS signing and executable verification first.
3. Complete any required human/independent page walkthrough using only the published instructions and record per-platform results.
4. Freeze public compatibility wording to the executable evidence, document known issues and release blockers, and verify CI on the final release commit.

No new runtime API or public props were added: **public behavior census N/A** for this documentation/test-only increment. Architecture and public release records remain solely in PSX.

## P4.5 scoped disposition

**DONE for the scoped example and release-preparation deliverables:** exact code fences for `main.py`, `settings/base.json`, and `pyproject.toml` match checked-in source; the full application can mount, unmount and run its real Qt entry point in an isolated project; Python 3.11 and 3.12 CI both passed on exact feature revision `34f411eeb16e8084e20b6e406e8b096f9f20156d`. Historical six examples retain separate matrix tests. The release-readiness checklist catalogs verified scope and blockers without asserting publication or complete binary portability.

**Global P4/public-release gate remains OPEN**, because the exact-copy native test is only Linux/Qt, not an independent human reader on every platform, and the unexecuted installer/signing/frozen other-backend/long-duration cases above cannot be marked passed. Explicit owner decision required before a GitHub/PyPI tag or any binary launch. P4.5 does not waive those qualifications.
