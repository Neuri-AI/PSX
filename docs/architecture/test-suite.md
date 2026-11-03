# Running and maintaining the test suite

Install the package with its development dependencies and the native backends
under test. Build the Cinnamon extension from `rust/cinnamon-core` using the
existing Rust workflow. The extension's Python import remains `_sfle_native`.

```sh
python -m pip install -e '.[dev,pyside6,kivy]'
python -m pip install playwright==1.64.1
python -m playwright install chromium
xvfb-run -a env QT_QPA_PLATFORM=offscreen KIVY_NO_ARGS=1 KIVY_NO_FILELOG=1 \
  python -m pytest -q -ra
```

On Linux, Tk requires scalable fonts, including bold and italic faces. With
Conda Tk without Xft, fontconfig listing a font alone is insufficient. Before
collection, pytest probes Tk in a separate process. If the current display lacks
scalable faces and `Xvfb`/`fc-match` are installed, it creates a private display
using the real system fonts and releases it after the session. The user's X
server is unchanged. This also works with the ordinary local command:

```sh
PSX_QT_BINDING=pyside6 poetry run pytest
```

Install declared development dependencies with `poetry install -E dev`; the
resource-soak and supervised-restart tests require `psutil`. For display-specific
diagnostics, `PSX_TEST_NATIVE_DISPLAY=existing` retains the original display.
Native font size, weight and slant assertions remain mandatory in both modes.

`tests/conftest.py` selects an installed Qt binding and defaults the shared native
tests to Qt when no backend is specified. Explicit `PSX_QT_BINDING` and
`PSX_GRID_BACKEND` selections are preserved. Run the shared cases in separate
processes for each backend:

```sh
python -m pytest --native-backend qt tests/test_mounted_grid_native_renderers.py
python -m pytest --native-backend tk tests/test_mounted_grid_native_renderers.py
python -m pytest --native-backend kivy tests/test_mounted_grid_native_renderers.py
```

The Rust-only import audits execute in fresh interpreters. Differential tests
deliberately import the Python oracle, so full-suite collection must not be
mistaken for Rust importing a fallback solver.

Live browser measurements support reviewed Playwright/Chromium pairs in
`tests/browser/test_sfle_chromium_version.py`. Historical JSON measurements retain
their original browser metadata. Updating a live oracle requires running the
geometry suite; neither archived provenance nor geometry tolerances should be
changed to bypass a version mismatch.

The public export snapshot lives in `tests/fixtures/public-api-exports.json` and
its reference in [public-api.md](public-api.md). The Mintlify validator's tests
use self-contained sites because the former `docs/public` site is not shipped.
The legacy layout inventory audits Python examples in README and Markdown docs,
as well as an `examples/` directory when present.

Native lifecycle assertions follow the current ownership boundaries:

- Fragments flatten into host children and add no native wrapper.
- Coordinated host replacement preserves the component boundary and hook state.
- Kivy resize consumes the current drawable size in a queued Clock callback.
- Ordinary Kivy widgets share canvas coordinates; ScrollView owns its transform
  and native gesture lifecycle.
- Tk Input separates the application value (`widget.var`) from the displayed
  placeholder (`widget.get()`); placeholders must not emit application changes.
- `Webview` is an alias of the external `WebView` port, not a portable leaf.
