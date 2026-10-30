"""Paired real native font metric receipt for Qt and Kivy.

The same installed font file is loaded in both toolkits. This evaluates
typographic proportionality for the supported px/font-family/weight subset.
Differences in rasterization and hinting remain reportable, not silently equal.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


FONT_ROOT = Path("/usr/share/fonts/truetype/dejavu")
FONT_REGULAR = FONT_ROOT / "DejaVuSans.ttf"
FONT_BOLD = FONT_ROOT / "DejaVuSans-Bold.ttf"


@pytest.mark.parametrize("size", (12, 15, 18, 24, 32))
@pytest.mark.parametrize("bold", (False, True), ids=("regular", "bold"))
def test_qt_and_kivy_shared_font_metrics_are_proportionate(
    size: int, bold: bool, tmp_path: Path,
):
    """Measure from actual native font providers, not synthetic CSS geometry."""
    from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF
    from PySide6.QtWidgets import QApplication
    from kivy.core.text import Label as CoreLabel

    file = FONT_BOLD if bold else FONT_REGULAR
    if not file.is_file():
        pytest.fail(f"CI must install the pinned common font: {file}")
    app = QApplication.instance() or QApplication(["qt-kivy-font-metrics"])
    font_id = QFontDatabase.addApplicationFont(str(file))
    assert font_id >= 0, file
    families = QFontDatabase.applicationFontFamilies(font_id)
    assert families
    font = QFont(families[0])
    font.setPixelSize(size)
    font.setBold(bold)
    qt_metrics = QFontMetricsF(font)
    label = CoreLabel(
        text="Velto Layout 1234", font_name=str(file),
        font_size=size, bold=False,
    )
    label.refresh()
    kivy_width, kivy_height = map(float, label.get_extents("Velto Layout 1234"))
    qt_width = float(qt_metrics.horizontalAdvance("Velto Layout 1234"))
    qt_height = float(qt_metrics.height())
    assert min(kivy_width, kivy_height, qt_width, qt_height) > 0
    widths = (kivy_width / qt_width)
    heights = (kivy_height / qt_height)
    receipt = {
        "font_file": str(file), "bold": bold, "font_size_px": size,
        "qt_advance_px": qt_width, "kivy_advance_px": kivy_width,
        "qt_height_px": qt_height, "kivy_height_px": kivy_height,
        "width_ratio": widths, "height_ratio": heights,
        "native_raster_equivalence_claim": False,
    }
    root = os.environ.get("PSX_QT_KIVY_FONT_METRICS_OUTPUT")
    if root:
        destination = Path(root)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"font-{size}-{'bold' if bold else 'regular'}.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8",
        )
    # Same TTF face and px size should not produce a dramatically different
    # native intrinsic width. Report values rather than hiding discrepancies.
    assert 0.8 <= widths <= 1.25, receipt
    assert 0.75 <= heights <= 1.35, receipt
