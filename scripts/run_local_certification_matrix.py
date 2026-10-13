"""Run the public-behavior certification matrix on one native platform.

The runner deliberately keeps GUI bindings in isolated virtual environments.
Each successful test produces its original JUnit XML and the public-behavior
receipt manifest required by the immutable-SHA census; failures preserve their
command, log and return code in the final report.

Run ``python scripts/run_local_certification_matrix.py --help`` for usage.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "artifacts" / "local-certification"
QT_BINDINGS = {
    "pyside6": ".[qt]",
    "pyqt6": ".[pyqt6]",
    "pyqt5": ".[pyqt5]",
    "pyside2": "PySide2==5.15.2.1",
}
SELECTIONS = frozenset({"core", "headless", "pyside6", "pyqt6", "pyqt5", "pyside2",
                        "kivy", "tkinter", "browser", "rust"})


@dataclass
class Result:
    name: str
    status: str
    duration_seconds: float
    command: list[str]
    log: str
    detail: str = ""


def call(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None,
         log: Path | None = None) -> tuple[int, float]:
    started = time.monotonic()
    complete_env = os.environ | (env or {})
    output = log.open("w", encoding="utf-8") if log else None
    try:
        process = subprocess.run(command, cwd=cwd, env=complete_env, text=True,
                                 stdout=output or subprocess.DEVNULL,
                                 stderr=subprocess.STDOUT, check=False)
    finally:
        if output:
            output.close()
    return process.returncode, round(time.monotonic() - started, 2)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def interpreter(version: str) -> list[str]:
    """Resolve a versioned Python without ever falling back silently."""
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            return [launcher, f"-{version}"]
        candidate = shutil.which(f"python{version}")
    else:
        candidate = shutil.which(f"python{version}")
    if not candidate:
        raise RuntimeError(
            f"Python {version} is required. Install it, then retry; do not use a different "
            "version because the report would not describe this matrix cell."
        )
    return [candidate]


def venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


class MatrixRunner:
    def __init__(self, output: Path, sha: str, *, reuse_envs: bool,
                 active_python: Path | None = None) -> None:
        self.output = output
        self.sha = sha
        self.reuse_envs = reuse_envs
        self.active_python = active_python
        self.results: list[Result] = []
        self.receipts: list[Path] = []

    def environment(self, name: str, version: str, dependency: str) -> Path | None:
        directory = self.output / ".venvs" / name
        python = self.active_python or venv_python(directory)
        log = self.output / "logs" / f"{name}-install.log"
        try:
            if self.active_python is None and not (self.reuse_envs and python.is_file()):
                code, duration = call([*interpreter(version), "-m", "venv", str(directory)], log=log)
                if code:
                    self.results.append(Result(name, "failed", duration, [*interpreter(version), "-m", "venv", str(directory)], str(log.relative_to(self.output)), "virtual environment creation failed"))
                    return None
            install = [str(python), "-m", "pip", "install", "-e",
                       dependency if dependency.startswith(".[") else ".", "pytest"]
            if dependency.startswith(".["):
                pass
            elif dependency:
                install.append(dependency)
            code, duration = call(install, log=log)
            if code:
                self.results.append(Result(name, "failed", duration, install, str(log.relative_to(self.output)), "dependency installation failed"))
                return None
            return python
        except RuntimeError as error:
            self.results.append(Result(name, "blocked", 0, [], str(log.relative_to(self.output)), str(error)))
            return None

    def test(self, name: str, python: Path, arguments: list[str], *, env: dict[str, str] | None = None) -> bool:
        log = self.output / "logs" / f"{name}.log"
        command = [str(python), *arguments]
        code, duration = call(command, env=env, log=log)
        self.results.append(Result(name, "passed" if code == 0 else "failed", duration, command,
                                   str(log.relative_to(self.output)), "" if code == 0 else f"exit code {code}"))
        return code == 0

    def census(self, name: str, python: Path, junit: Path, environment: str) -> Path | None:
        inventory = self.output / f"{name}-inventory.json"
        if not self.test(f"{name}-receipt", python, ["-m", "tests.certification.public_behavior_census",
                                                       "--out", str(inventory), "--junit", str(junit),
                                                       "--sha", self.sha, "--environment", environment]):
            return None
        receipt = inventory.with_name(f"{inventory.stem}-receipts.json")
        self.receipts.append(receipt)
        return receipt

    def run_public_suite(self, name: str, python: Path, test_file: str, environment: str,
                         env: dict[str, str] | None = None) -> None:
        junit = self.output / f"public-{name}.xml"
        if self.test(f"public-{name}", python, ["-m", "pytest", "-q", test_file,
                                                   f"--junitxml={junit}"], env=env):
            self.census(f"public-{name}", python, junit, environment)

    def write_report(self) -> None:
        report = {
            "schema_version": 1,
            "commit_sha": self.sha,
            "platform": platform.platform(),
            "python_host": sys.version,
            "results": [asdict(result) for result in self.results],
            "receipt_files": [str(path.relative_to(self.output)) for path in self.receipts if path.is_file()],
            "passed": sum(result.status == "passed" for result in self.results),
            "failed": sum(result.status == "failed" for result in self.results),
            "blocked": sum(result.status == "blocked" for result in self.results),
        }
        (self.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        rows = "\n".join(
            "<tr><td>{}</td><td class=\"{}\">{}</td><td>{:.2f}s</td><td><a href=\"{}\">log</a></td><td>{}</td></tr>".format(
                html.escape(item.name), item.status, item.status, item.duration_seconds,
                html.escape(item.log), html.escape(item.detail))
            for item in self.results
        )
        page = """<!doctype html><meta charset=\"utf-8\"><title>PSX local certification</title>
<style>body{font:14px system-ui;margin:2rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:.45rem;text-align:left}.passed{color:#087f23}.failed,.blocked{color:#b42318;font-weight:700}</style>
<h1>PSX local certification</h1><p>Commit: <code>{}</code></p>
<table><thead><tr><th>Combination</th><th>Status</th><th>Duration</th><th>Output</th><th>Detail</th></tr></thead><tbody>{}</tbody></table>
""".format(html.escape(self.sha), rows)
        (self.output / "report.html").write_text(page, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Directory for immutable test artifacts.")
    parser.add_argument("--reuse-envs", action="store_true", help="Reuse existing per-binding virtual environments.")
    parser.add_argument("--active-conda", action="store_true", help="Use the active Conda environment instead of creating virtual environments.")
    parser.add_argument("--python-version", help="Required active Python version, for example 3.10.")
    parser.add_argument("--only", default=",".join(sorted(SELECTIONS)),
                        help="Comma-separated cells: " + ", ".join(sorted(SELECTIONS)))
    parser.add_argument("--allow-dirty", action="store_true", help="Allow uncommitted files (results are not certifiable).")
    parser.add_argument("--include-browser-and-rust", action="store_true", help="Also run Chromium and Rust/Python differential suites.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = frozenset(part.strip() for part in args.only.split(",") if part.strip())
    unknown = selected - SELECTIONS
    if unknown:
        raise SystemExit("Unknown matrix cells: " + ", ".join(sorted(unknown)))
    active_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if args.active_conda and args.python_version and active_version != args.python_version:
        raise SystemExit(f"Active Python is {active_version}, expected {args.python_version}.")
    sha = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    if dirty and not args.allow_dirty:
        raise SystemExit("Refusing a dirty checkout. Commit/stash first, or use --allow-dirty for diagnostic-only output.")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    output = args.output or ARTIFACT_ROOT / f"{platform.system().lower()}-{sha[:12]}-{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    (output / "logs").mkdir()
    runner = MatrixRunner(output, sha, reuse_envs=args.reuse_envs,
                          active_python=Path(sys.executable) if args.active_conda else None)
    python_version = args.python_version or active_version

    core = runner.environment("core", python_version if args.active_conda else "3.12", "")
    if core:
        if "core" in selected:
            junit = output / "public-core.xml"
            if runner.test("public-core", core, ["-m", "pytest", "-q", "tests/test_public_behavior_census.py",
                                                   "tests/test_public_contract_census.py", "tests/test_public_property_validation.py",
                                                   f"--junitxml={junit}"]):
                runner.census("public-core", core, junit, f"{platform.system().lower()}-core-python-{python_version}")
        if "headless" in selected:
            runner.test("headless-native", core, ["-m", "pytest", "-q", "tests/test_core.py", "tests/test_renderer_adapters.py",
                                                    "tests/test_headless_native_layout.py", "tests/test_scroll_offsets.py"])
            runner.run_public_suite("headless", core, "tests/test_headless_public_behavior.py",
                                    f"{platform.system().lower()}-headless-python-{python_version}")

    for binding, dependency in QT_BINDINGS.items():
        if binding not in selected:
            continue
        version = python_version if args.active_conda else ("3.10" if binding == "pyside2" else "3.12")
        if binding == "pyside2" and version != "3.10":
            runner.results.append(Result(f"qt-{binding}", "blocked", 0, [], "", "PySide2 is supported only on Python 3.10."))
            continue
        python = runner.environment(f"qt-{binding}", version, dependency)
        if not python:
            continue
        env = {"PSX_QT_BINDING": binding, "QT_QPA_PLATFORM": "offscreen"}
        runner.test(f"qt-{binding}-native", python, ["-m", "pytest", "-q", "-rs",
                                                        "tests/test_qt_native_component_lifecycle.py"], env=env)
        runner.run_public_suite(f"qt-{binding}", python, "tests/test_qt_public_behavior.py",
                                f"{platform.system().lower()}-qt-{binding}-python-{version}", env)

    kivy = runner.environment("kivy", python_version if args.active_conda else "3.12", ".[kivy]") if "kivy" in selected else None
    if kivy:
        runner.test("kivy-native", kivy, ["-m", "pytest", "-q", "tests/test_kivy_renderer.py", "tests/test_kivy_native_layout.py"])
        runner.run_public_suite("kivy", kivy, "tests/test_kivy_public_behavior.py",
                                f"{platform.system().lower()}-kivy-python-{python_version}")

    tkinter = runner.environment("tkinter", python_version if args.active_conda else "3.12", "Pillow") if "tkinter" in selected else None
    if tkinter:
        runner.test("tkinter-native", tkinter, ["-m", "pytest", "-q", "tests/test_tkinter_renderer.py",
                                                   "tests/test_tkinter_native_layout.py", "tests/test_tkinter_external_native_ports.py"])
        runner.run_public_suite("tkinter", tkinter, "tests/test_tk_public_behavior.py",
                                f"{platform.system().lower()}-tkinter-python-{python_version}")

    if args.include_browser_and_rust and core and "rust" in selected:
        runner.test("rust-python", core, ["-m", "pytest", "-q", "tests/interop/test_sfle_differential.py",
                                            "tests/interop/test_sfle_capability_parity.py", "tests/interop/test_sfle_deferral_boundaries.py"])
    if args.include_browser_and_rust and core and "browser" in selected:
        if runner.test("browser-install", core, ["-m", "pip", "install", "playwright"]):
            runner.test("browser-chromium-install", core, ["-m", "playwright", "install", "chromium"])
            runner.test("browser-geometry", core, ["-m", "pytest", "-q", "tests/browser/test_sfle_chromium.py",
                                                      "tests/browser/test_sfle_engine_chromium.py", "tests/browser/test_sfle_headless_oracle.py", "tests/browser/test_sfle_seeded_fuzz_regression.py"])

    if runner.receipts and core:
        aggregate = output / "public-behavior-aggregate.json"
        runner.test("public-behavior-aggregate", core, ["-m", "tests.certification.public_behavior_census", "--out", str(aggregate),
                                                          "--sha", sha, *sum((["--receipt-file", str(path)] for path in runner.receipts), [])])
    runner.write_report()
    print(f"Report: {output / 'report.html'}")
    print(f"Machine-readable: {output / 'report.json'}")
    return 1 if any(result.status in {"failed", "blocked"} for result in runner.results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
