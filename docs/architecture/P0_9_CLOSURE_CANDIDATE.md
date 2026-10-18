# P0.9 — Closure candidate and hard evidence gate

**Date:** 2026-10-18  
**Status:** **NOT CLOSED — new CI receipts required**  
**Scope:** C07 native memory ownership, C05 ecosystem wheel resolution, owner architecture sign-off.

## Changes implemented

### C07 — Kivy owned widget KV rule lifetime

- `psx/renderers/kivy/kivy.py` now explicitly calls Kivy's documented `Builder.unbind_widget(widget.uid)` **after** a successful owned native handle teardown via `KivyRenderer.destroy()`.
- Borrowed native widget handles are explicitly exempt: their KV bindings and owner lifecycle must remain intact.
- `tests/test_p0_kivy_native_lifecycle.py` now tests that owned Flex/Button uids receive cleanup and a borrowed native Label uid is excluded.
- `.github/workflows/p0-memory-soak.yml` now triggers for changes to Kivy renderer sources, runs the Kivy native lifecycle test and defaults to **10,000 cycles** per backend. Outputs raw memory JSON and trend summaries.

**Why this change:** existing 5,000-cycle snapshots localize almost all positive Python allocations to `kivy.lang.builder` creation of rule binding graphs; the supported public Kivy API explicitly unbinds KV property rules keyed by widget uid. It is a **targeted remediation hypothesis**, not yet a verified leak fix. Kivy widget finalizers normally also unbind, so native retained owner/proxy cycles may remain even after proactive cleanup.

**Required passing evidence:** Kivy native test green; 10,000-cycle output for Qt, Tk and Kivy, with verified disposed instance/event slot/widget counts and an acceptable, explicitly justified post-warmup RSS/tracemalloc trend. A direct Kivy baseline is necessary if upstream retention remains. Must not reinterpret the probe's `no_sustained_growth_detected_in_sample` string as a memory slope acceptance.

### C05 — Full distribution resolver graph

In `Neuri-AI/Velto` default branch:
- `pyproject.toml` now requires `velto-core>=0.1.0,<1.0.0` (imports `psx`) instead of the nonexistent local `psx>=1.0a1` distribution.
- `pydux[psx]>=0.1.0,<1.0.0` matches actual Pydux `0.1.0`.
- `qyro-engine>=1.0.0a1,<2.0.0` matches current Qyro Engine `1.0.0a1`, including backend extras.
- `.github/workflows/p0-ecosystem-resolver.yml` builds all five collaborating project wheels (PSX, Pydux, Qyro Engine, Qyro CLI, Velto) and runs a fresh venv install, `pip check`, facade object identity imports and a `qyro --help` CLI smoke on Python 3.10 and 3.13. Git SHAs are captured by job output.

**Required passing evidence:** both fresh-wheel jobs green, exact SHA capture, `pip check` success, actual facade runtime smoke verified for advertised backends. Published-index installation cannot be inferred solely from local built wheels.

## Existing verified historical receipts

- 1,000-cycle native matrix: three backends completed.
- 5,000-cycle native matrix: Qt/Tk near plateau; Kivy growth still sustained.
- Kivy native / PSX without Cinnamon / PSX+SFLE three-arm profiler run `39146917385`: direct and no-SFLE about +15 MiB RSS, full SFLE about +50.39 MiB RSS between cycles 500–5,000, with same one-per-cycle Kivy `WeakProxy` count.
- No **post-fix** 10,000-cycle or clean five-wheel resolver receipts are available to this record yet.

## Closure decision

**DO NOT LABEL THIS WORKSTREAM COMPLETE WITHOUT NEW REAL ARTIFACTS.**

P0→P1 Architecture Gate additionally requires the owner to approve or explicitly defer decisions AD-01 through AD-12 and produce the full source/test/CI evidence ledger specified in `ARCHITECTURE_APPROVAL.md`; this file is not an approval signature.


## New executed results — run 39148603648 and C05 CI #1

**C07, 5,000-cycle three-arm run after Builder.unbind_widget:**

| Arm | RSS delta 500→5,000 | Traced Python delta 500→5,000 | Extra dicts | Extra lists |
| --- | ---: | ---: | ---: | ---: |
| Direct Kivy | 15,634,432 B | 5,279,356 B | 4,834 | 4,622 |
| PSX no Cinnamon | 15,175,680 B | 5,237,803 B | 4,768 | 4,556 |
| PSX + Cinnamon | 52,252,672 B | 18,376,894 B | 27,276 | 27,059 |

All arms exhibit exactly +4,500 live Kivy weakproxy objects from cycle 500 to 5,000. The owned-widget KV `Builder.unbind_widget` cleanup **did not meaningfully change the SFLE-enabled growth** compared with run `39146917385`. It must **not** be described as a certified memory fix. Source files: owner-supplied artifact ZIPs `p0-kivy-heap-{native,psx_no_cinnamon,velto}-39148603648.zip`.

The owner also supplied a GitHub Actions screenshot showing the full `P0 memory soak` matrix green (PySide6, Tkinter, Kivy, Python 3.13) at source commit `9aa614c`. **Green process exits alone do not establish that the measured Kivy RSS or traced heap plateaued**, and its per-backend raw JSON was not supplied in this batch. Additionally, CI's 10,000-cycle default requires checking the raw report; a green workflow summary without raw metadata must not be presented as verified cycle count.

**C05 resolver:** Owner supplied CI screenshot: clean-wheel-resolver Python 3.10 fails at `from qyro import VeltoContext`; actual `qyro/__init__.py` exported `ApplicationContext` but not `VeltoContext`, and `qyro/client/velto_context.py` does not exist on the runtime main branch. Remediation: Qyro now exports `VeltoContext = ApplicationContext` as an identity-preserving alias, and Velto facade tests assert identity to `qyro.ApplicationContext` rather than a nonexistent implementation module. **New resolver CI receipt still pending.** This alias repairs import/identity, not the independently unimplemented claimed PSX render/mount lifecycle contract.

**Additional C07 diagnostic:** A fourth isolated CI arm `velto_no_commit` retains SFLE-configured Kivy widget/adapters but temporarily disables native geometry commit *only in the test harness*. Compare its memory trend with `velto` to isolate growth in the commit path. This produces intentionally invalid geometry, never production behavior.

**Current status: NOT CLOSED.**
