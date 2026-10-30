"""Compare real Qt and Kivy font metrics in isolated native processes.

Qt and Kivy SDL text providers can conflict when loaded in one Python
interpreter. Each provider is initialized in a dedicated subprocess to avoid
sharing their native graphical and font library state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


FONT_ROOT = Path("/usr/share/fonts/truetype/dejavu")
FONT_REGULAR = FONT_ROOT / "DejaVuSans.ttf"
FONT_BOLD = FONT_ROOT / "DejaVuSans-Bold.ttf"


def _native_metrics(backend: str, path: Path, size: int) -> dict:
    if backend == "qt":
        source = """
            from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF
            from PySide6.QtWidgets import QApplication
            import json, sys
            app = QApplication(["qt-font-probe"])
            font_id = QFontDatabase.addApplicationFont(sys.argv[1])
            assert font_id >= 0, sys.argv[1]
            font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0])
            font.setPixelSize(int(sys.argv[2]))
            metrics = QFontMetricsF(font)
            print(json.dumps({
                "width": float(metrics.horizontalAdvance("Velto Layout 1234")),
                "height": float(metrics.height()),
            }))
        """
    else:
        source = """
            import json, sys
            from kivy.core.window import Window
            from kivy.core.text import Label as CoreLabel
            label = CoreLabel(
                text="Velto Layout 1234", font_name=sys.argv[1],
                font_size=float(sys.argv[2]),
            )
            width, height = label.get_extents("Velto Layout 1234")
            print(json.dumps({"width": float(width), "height": float(height)}))
        """
    environment = dict(os.environ)
    environment.update(KIVY_NO_ARGS="1", KIVY_NO_FILELOG="1",
                       QT_QPA_PLATFORM="offscreen")
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source),
         str(path), str(size)],
        env=environment, capture_output=True, text=True, timeout=45,
    )
    assert completed.returncode == 0, (
        backend, completed.stdout, completed.stderr
    )
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.mark.parametrize("size", (12, 15, 18, 24, 32))
@pytest.mark.parametrize("bold", (False, True), ids=("regular", "bold"))
def test_qt_and_kivy_shared_font_metrics_are_proportionate(size: int, bold: bool):
    file = FONT_BOLD if bold else FONT_REGULAR
    assert file.is_file(), f"CI must install pinned font: {file}"
    qt = _native_metrics("qt", file, size)
    kivy = _native_metrics("kivy", file, size)
    assert min(*qt.values(), *kivy.values()) > 0
    width_ratio = kivy["width"] / qt["width"]
    height_ratio = kivy["height"] / qt["height"]
    receipt = {
        "font_file": str(file), "bold": bold, "font_size_px": size,
        "qt": qt, "kivy": kivy,
        "width_ratio": width_ratio, "height_ratio": height_ratio,
        "native_raster_equivalence_claim": False,
    }
    directory = os.environ.get("PSX_QT_KIVY_FONT_METRICS_OUTPUT")
    if directory:
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"font-{size}-{'bold' if bold else 'regular'}.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8",
        )
    assert 0.8 <= width_ratio <= 1.25, receipt
    assert 0.75 <= height_ratio <= 1.35, receipt
