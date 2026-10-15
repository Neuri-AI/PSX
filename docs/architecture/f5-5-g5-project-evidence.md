# F5.5 G5 — Project evidence and compatibility matrix

**Canonical start point:** `develop` `e20c18a430366ec47bf362f6b0e1dc261acb3e54` (2026-10-15).
**G5 branch:** `docs/f5-5-real-world-applications`; [PR #39](https://github.com/Neuri-AI/PSX/pull/39). All implementation stays on this branch.

## Projects and declared scope

| Project | Entry point | Behavior exercised | CI job | Verified target |
| --- | --- | --- | --- | --- |
| Stateful Task Board | `examples/f5_5_task_board/app.py` | `use_state`, keyed row toggling, clear completed, Headless readback | `task-board` | Ubuntu, Python 3.10–3.13 |
| Same Task Board on Qt | `examples/f5_5_task_board/native_qt.py` | Actual PySide6 mount and unmount; same stateful component | `native-qt-task-board` | Ubuntu, Python 3.12, Qt offscreen |
| Tkinter gallery | `examples/f5_5_native_gallery/app.py` | Native `Text`, `Input`, `Button` mount/unmount | `native-gallery-tkinter` | Ubuntu, Python 3.10–3.13, Xvfb |
| Qt gallery + interoperability | `examples/f5_5_native_gallery/qt_app.py` | Native Qt `Text`, `Button` and `Native(QLabel)` property readback | `pyside6-native-smoke` | Ubuntu, Python 3.11–3.13, Qt offscreen |
| Kivy gallery | `examples/f5_5_native_gallery/kivy_app.py` | Native Kivy portable controls mount/unmount | `kivy-native-smoke` | Ubuntu, Python 3.11–3.12, Xvfb |

All source examples are independent of unfinished Pydux/Qyro/CLI integrations. No browser/DOM is used. Each documentation page states exact install/run commands, supported smoke environment, expected output, and known limitations.

## Commands

From the checkout root after `python -m pip install -e .`:

```bash
python examples/f5_5_task_board/app.py
cd examples/f5_5_task_board && python -m unittest -v test_app
```

For Tkinter, `xvfb-run -a python examples/f5_5_native_gallery/app.py --smoke`. For Qt, install `.[pyside6]`, then `QT_QPA_PLATFORM=offscreen python examples/f5_5_native_gallery/qt_app.py --smoke` or `python examples/f5_5_task_board/native_qt.py --smoke` from their specified working directory. For Kivy, install `.[kivy]` then `xvfb-run -a python examples/f5_5_native_gallery/kivy_app.py --smoke`.

## Receipts and honest boundaries

- [Task Board CI #38693187737](https://github.com/Neuri-AI/PSX/actions/runs/38693187737): 4/4 Headless Python versions **SUCCESS**.
- [Tkinter CI #38693453663](https://github.com/Neuri-AI/PSX/actions/runs/38693453663): 4/4 Python versions **SUCCESS**.
- [Qt CI #38693712445](https://github.com/Neuri-AI/PSX/actions/runs/38693712445): after installing missing OS `libEGL` libraries, 3/3 PySide6 Python versions **SUCCESS**.
- [Kivy CI #38693803481](https://github.com/Neuri-AI/PSX/actions/runs/38693803481): after isolating Kivy's argument parser with `KIVY_NO_ARGS`, 2/2 Python versions **SUCCESS**.
- A later Qt-native Task Board CI run exercises the same app on PySide6. The initial native Qt job on [#38694105075](https://github.com/Neuri-AI/PSX/actions/runs/38694105075) has been observed **SUCCESS**.

**These receipts are limited to the exact source SHA of each run.** The latest documentation and strengthened `Native(QLabel)` readback changes require their latest workflow checks; never present an earlier green run as proof of a newer change.

### Not covered by this G5 Linux CI

- Real, human-verified screenshots, exact window geometries, controls clicked interactively in all graphical backends, or accessibility assessment of native widgets.
- macOS/Windows manual/automated native runs, and unsupported/unselected Python/OS/backend combinations.
- A platform-wide Qt/Kivy/Tkinter feature parity assertion. Headless behavior tests are not native behavior tests.

These are explicit requirements to evaluate in the final G6 comprehensive review. Do not invent screenshots or state that macOS/Windows native support was exercised here.
