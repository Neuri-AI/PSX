"""B7 RED: F2.4 inventory must include separately versioned external boilerplates.

Temporary Git repositories make this test independent of GitHub network access
and enforce exact token counts, source commits, and missing-repo fail-closed.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_sfle_migration.py"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _repo(path, source):
    path.mkdir()
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "sfle-ci@example.invalid", cwd=path)
    _git("config", "user.name", "SFLE fixture", cwd=path)
    (path / "ui.py").write_text(source, encoding="utf-8")
    _git("add", "ui.py", cwd=path)
    _git("commit", "-qm", "fixture", cwd=path)
    return _git("rev-parse", "HEAD", cwd=path).stdout.strip()


def test_B7_external_repo_scan_is_versioned_and_counts_only_source_tokens(tmp_path):
    qt = tmp_path / "qt"
    tk = tmp_path / "tk"
    qt_sha = _repo(qt, "Row Row Column Scroll\n")
    tk_sha = _repo(tk, "Column Row\n# Scrollbar is not a layout component\n")
    out = tmp_path / "inventory"
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--output-dir", str(out),
            "--external-root", f"qt={qt}",
            "--external-root", f"tkinter={tk}",
        ],
        cwd=SCRIPT.parents[1], text=True, capture_output=True, timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads((out / "inventory.json").read_text())
    externals = payload["external_repositories"]
    assert set(externals) == {"qt", "tkinter"}
    assert externals["qt"]["commit_sha"] == qt_sha
    assert externals["tkinter"]["commit_sha"] == tk_sha
    assert externals["qt"]["counts"]["Row"]["occurrences"] == 2
    assert externals["qt"]["counts"]["Column"]["occurrences"] == 1
    assert externals["qt"]["counts"]["Scroll"]["occurrences"] == 1
    assert externals["tkinter"]["counts"]["Row"]["occurrences"] == 1
    assert externals["tkinter"]["counts"]["Column"]["occurrences"] == 1
    assert externals["tkinter"]["counts"]["Scroll"]["occurrences"] == 0
    assert externals["qt"]["matching_files"]["Row"] == ["ui.py"]


def test_B7_missing_external_repo_cannot_silently_pass(tmp_path):
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--output-dir", str(tmp_path / "out"),
            "--external-root", f"kivy={tmp_path / 'does-not-exist'}",
        ],
        cwd=SCRIPT.parents[1], text=True, capture_output=True, timeout=20,
    )
    assert proc.returncode != 0
    assert "kivy" in proc.stderr or "does-not-exist" in proc.stderr
