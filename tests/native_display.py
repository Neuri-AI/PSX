"""Provide a private test display when X11 Tk cannot render scalable fonts.

Conda Tk can use X11 core fonts instead of Xft. Fontconfig installation alone
does not make those faces available to Tk. Never change the user's X server.
"""
from __future__ import annotations

import os
import importlib.util
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile


_FONT_PROBE = """
import tkinter as tk
from tkinter import font
root = tk.Tk()
root.withdraw()
try:
    for family in font.families(root):
        small = font.Font(root=root, family=family, size=-12)
        large = font.Font(root=root, family=family, size=-30,
                          weight='bold', slant='italic')
        if (large.metrics('linespace') > small.metrics('linespace')
                and large.actual('weight') == 'bold'
                and large.actual('slant') == 'italic'):
            break
    else:
        raise SystemExit(1)
finally:
    root.destroy()
"""


def _has_scalable_fonts():
    if not os.environ.get("DISPLAY"):
        return False
    result = subprocess.run([sys.executable, "-c", _FONT_PROBE],
                            capture_output=True, timeout=15)
    return result.returncode == 0


def _font_directory(folder: Path):
    entries = set()
    for generic, alias in (("sans-serif", "helvetica"),
                           ("serif", "times"), ("monospace", "courier")):
        for style in ("", ":weight=bold", ":slant=italic", ":weight=bold:slant=italic"):
            match = subprocess.run(
                ["fc-match", "-f", "%{file}\n%{family}\n%{weight}\n%{slant}\n",
                 generic + style], capture_output=True, text=True, check=True,
                timeout=10,
            ).stdout.splitlines()
            if len(match) != 4 or not Path(match[0]).is_file():
                raise RuntimeError(f"No installed scalable font for {generic + style}")
            source, families, weight, slant = match
            # Use actual font properties, never label a regular face as bold
            # or italic merely because that style was requested.
            weight = "bold" if float(weight.split(",")[0]) >= 180 else "medium"
            slant_value = float(slant.split(",")[0])
            slant = "o" if slant_value >= 110 else "i" if slant_value >= 100 else "r"
            filename = f"face-{len(list(folder.iterdir()))}{Path(source).suffix}"
            (folder / filename).symlink_to(source)
            for family in (families.split(",")[0], alias):
                family = family.lower().replace("-", " ")
                spacing = "m" if generic == "monospace" else "p"
                entries.add(f"{filename} -misc-{family}-{weight}-{slant}-normal--"
                            f"0-0-0-0-{spacing}-0-iso10646-1")
    (folder / "fonts.dir").write_text(
        str(len(entries)) + "\n" + "\n".join(sorted(entries)) + "\n", encoding="utf-8")


class NativeTestDisplay:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="psx-test-fonts-")
        self.process = None
        self.previous_display = os.environ.get("DISPLAY")
        self.previous_authority = os.environ.get("XAUTHORITY")
        try:
            _font_directory(Path(self.directory.name))
            reader, writer = os.pipe()
            try:
                self.process = subprocess.Popen(
                    ["Xvfb", "-displayfd", str(writer), "-screen", "0", "1280x1024x24",
                     "-nolisten", "tcp", "-fp", self.directory.name],
                    pass_fds=(writer,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                os.close(writer)
                writer = None
                if not select.select([reader], [], [], 10)[0]:
                    raise RuntimeError("Private Xvfb did not become ready")
                number = os.read(reader, 64).decode().strip()
                if not number.isdigit():
                    raise RuntimeError("Private Xvfb failed to allocate a display")
            finally:
                os.close(reader)
                if writer is not None:
                    os.close(writer)
            os.environ["DISPLAY"] = ":" + number
            os.environ.pop("XAUTHORITY", None)
            if not _has_scalable_fonts():
                raise RuntimeError("Tk cannot render the system fonts on private Xvfb")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for name, previous in (("DISPLAY", self.previous_display),
                               ("XAUTHORITY", self.previous_authority)):
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous
        self.directory.cleanup()


def prepare_native_display(config):
    if (not sys.platform.startswith("linux")
            or importlib.util.find_spec("_tkinter") is None
            or importlib.util.find_spec("tkinter") is None
            or os.environ.get("PSX_TEST_NATIVE_DISPLAY") == "existing"
            or not shutil.which("Xvfb") or not shutil.which("fc-match")):
        return
    if _has_scalable_fonts():
        return
    display = NativeTestDisplay()
    config.add_cleanup(display.close)
    config._psx_private_native_display = True
