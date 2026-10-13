"""Classify Native layout changes into the smallest *safe* GitHub Actions test set.

Stdlib-only: called by the lightweight CI router before installing toolkits.
A missing, truncated or ambiguous change set fails open to full validation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import PurePosixPath

SUITES = (
    "router", "core", "sfle", "rust", "chromium", "qt", "kivy",
    "tkinter", "headless", "native", "legacy",
)


def _is_docs(path: str) -> bool:
    return path == "README.md" or path.startswith("docs/") or (
        path.endswith(".md") and not path.startswith(".github/")
    )


def _classify_path(path: str) -> set[str]:
    if path in ("scripts/ci/impact.py", "tests/test_ci_impact.py") or path.startswith("scripts/ci/"):
        return {"router"}
    if path.startswith(".github/workflows/"):
        # A routing change must test the selector. Targeted workflows also
        # certify their own affected suite, not all of F2 by default.
        result = {"router"}
        name = PurePosixPath(path).name
        if name == "native-layout-selective.yml":
            # Changes to the shared Native layout workflow must exercise the Qt parity
            # matrix; don't certify its new required job with router-only CI.
            result.add("qt")
        elif name == "sfle-chromium.yml":
            result.add("chromium")
        elif name == "sfle-ui-certification.yml":
            result.update({"qt", "kivy", "tkinter"})
        elif name == "sfle-native-matrix.yml":
            result.add("native")
        elif name == "sfle-core.yml":
            result.update({"sfle", "rust"})
        elif name == "ci.yml":
            result.add("core")
        return result
    if path == "pyproject.toml" or path in ("setup.cfg", "setup.py"):
        return {"core", "sfle", "rust", "qt", "kivy", "tkinter", "native"}
    if path.startswith("rust/sfle-core/"):
        return {"sfle", "rust", "chromium", "native"}
    if path.startswith("psx/sfle/"):
        name = PurePosixPath(path).name
        # Production Native layout bridges must route to the real toolkit consumer, not
        # only to the neutral SFLE engine and browser oracle.
        if name == "qt_layout_bridge.py":
            return {"qt"}
        if name == "kivy_layout_bridge.py":
            return {"kivy"}
        if name == "tkinter_layout_bridge.py":
            return {"tkinter"}
        if name == "headless_layout_bridge.py":
            return {"headless"}
        if name in ("qt_measurement.py", "qt_worker_dispatch.py"):
            return {"sfle", "qt"}
        if name == "kivy_measurement.py":
            return {"sfle", "kivy"}
        if name == "tk_measurement.py":
            return {"sfle", "tkinter"}
        if name == "headless_measurement.py":
            return {"sfle", "headless"}
        if name in ("native_layout_snapshot.py", "external_native_geometry_ports.py"):
            return {"core", "headless", "qt", "kivy", "tkinter"}
        if name in ("width_dependent_intrinsic_measurement.py", "native_component_capabilities.py",
                    "native_pixel_space.py"):
            return {"core", "qt", "kivy", "tkinter"}
        if name in ("adapter_contract.py", "worker_lifecycle.py", "native_geometry.py",
                    "native_measurement.py", "native_lifecycle.py"):
            return {"core", "sfle", "headless", "qt", "kivy", "tkinter"}
        if name in ("backend.py", "native_loader.py"):
            return {"sfle", "rust", "native"}
        return {"sfle", "rust", "chromium", "headless"}
    if path.startswith("psx/renderers/qt/"):
        return {"qt"}
    if path.startswith("psx/renderers/kivy/"):
        return {"kivy"}
    if path.startswith("psx/renderers/tkinter/"):
        return {"tkinter"}
    if path.startswith("psx/renderers/components/") or path.startswith("psx/renderers/base"):
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path == "psx/renderers/headless.py":
        return {"headless"}
    if path.startswith("psx/renderers/"):
        return {"core", "qt", "kivy", "tkinter", "headless"}
    if path in ("psx/__init__.py", "psx/core/native.py") or path.startswith("psx/core/"):
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path.startswith("psx/markup/"):
        return {"core", "headless"}
    if path.startswith("psx/"):
        return {"core", "headless", "qt", "kivy", "tkinter"}
    if path.startswith("tests/browser/"):
        return {"chromium"}
    if path.startswith("tests/ui/"):
        return {"qt", "kivy", "tkinter"}
    if path.startswith("tests/sfle/"):
        if "qt" in path:
            return {"sfle", "qt"}
        return {"sfle"}
    if path.startswith("tests/interop/"):
        if "native_wheel" in path or "frozen" in path:
            return {"native"}
        return {"rust", "sfle"}
    if path.startswith("tests/"):
        name = PurePosixPath(path).name
        if "kivy" in name:
            return {"kivy"}
        if "tkinter" in name or name.startswith("test_tk"):
            return {"tkinter"}
        if "pyqt" in name or "pyside" in name or "_qt_" in name:
            return {"qt"}
        return {"core"}
    if path.startswith("examples/") or path.startswith("scripts/"):
        return {"core"}
    # Unrecognized code/configuration: do not silently skip tests.
    return set(SUITES)


def classify(files: list[str] | None, *, force_full: bool = False) -> dict[str, object]:
    if force_full or not files or len(files) >= 300 or any(
        not isinstance(p, str) or not p or p.startswith("/") or ".." in PurePosixPath(p).parts
        for p in files
    ):
        selected = set(SUITES)
        why = "explicit full certification" if force_full else "missing, unsafe or truncated diff"
        return {
            "docs_only": False, "full": True,
            "selected": sorted(selected),
            "reason": why,
            "changed": files or [],
        }

    normalized = sorted(set(files))
    if all(_is_docs(p) for p in normalized):
        return {
            "docs_only": True, "full": False, "selected": [],
            "reason": "documentation-only; no product tests",
            "changed": normalized,
        }

    selection = set()
    causes = []
    for path in normalized:
        if _is_docs(path):
            continue
        groups = _classify_path(path)
        selection.update(groups)
        causes.append(f"{path}: {','.join(sorted(groups))}")
    return {
        "docs_only": False, "full": False,
        "selected": sorted(selection),
        "reason": "; ".join(causes),
        "changed": normalized,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-json", required=True)
    parser.add_argument("--github-output")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    with open(args.changed_json, encoding="utf-8") as stream:
        changed = json.load(stream)
    if not isinstance(changed, list):
        changed = None
    result = classify(changed, force_full=args.full)
    print(json.dumps(result, indent=2))
    output = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            for suite in SUITES:
                stream.write(f"{suite}={str(suite in result['selected']).lower()}\n")
            stream.write(f"docs_only={str(result['docs_only']).lower()}\n")
            stream.write(f"full={str(result['full']).lower()}\n")
            stream.write(f"selected={','.join(result['selected'])}\n")


if __name__ == "__main__":
    main()
