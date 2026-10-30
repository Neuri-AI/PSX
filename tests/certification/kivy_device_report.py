"""Capture an actual display/Retina receipt on a user's Kivy-enabled machine.

Use: python -m tests.certification.kivy_device_report --output receipts
This is a physical window observation, not a synthetic 2x simulation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="kivy-device-receipt")
    args = parser.parse_args()
    target = Path(args.output).resolve()
    target.mkdir(parents=True, exist_ok=True)

    from kivy import __version__ as kivy_version
    from kivy.core.window import Window
    from kivy.metrics import Metrics
    from kivy.clock import Clock
    from kivy.base import EventLoop
    from psx.sfle.kivy_display_scale import KivyDisplayScale
    from psx.renderers.kivy.kivy import KivyRenderer

    if Window is None:
        raise RuntimeError("Kivy SDL2 could not create a native graphics window")
    observed = KivyDisplayScale.from_window(Window)
    renderer = KivyRenderer()
    report = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version,
        "kivy": kivy_version,
        "window_size": list(Window.size),
        "window_system_size": list(Window.system_size),
        "metrics_density": float(Metrics.density),
        "metrics_fontscale": float(Metrics.fontscale),
        "metrics_dpi": float(Metrics.dpi),
        "observed_ratio": observed.snapshot(),
        "renderer_css_scale": renderer._psx_css_pixel_scale,
        "uniform_ratio_error": None,
        "screenshot": None,
    }
    try:
        report["uniform_ratio"] = observed.uniform
    except ValueError as exc:
        report["uniform_ratio_error"] = str(exc)
    try:
        for _ in range(5):
            Window.canvas.ask_update()
            Clock.tick()
            EventLoop.idle()
        name = Window.screenshot(name=str(target / "kivy-native.png"))
        if name and Path(name).is_file():
            report["screenshot"] = str(Path(name).name)
    finally:
        (target / "kivy-device.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
