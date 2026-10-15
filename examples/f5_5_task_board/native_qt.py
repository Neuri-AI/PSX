"""Run the complete stateful TaskBoard on an actual PySide6 renderer.

Install: python -m pip install -e ".[pyside6]"
Smoke: QT_QPA_PLATFORM=offscreen python native_qt.py --smoke
"""
import sys

from psx import App
from app import TaskBoard


def main() -> int:
    app = App(TaskBoard(), renderer="pyside6")
    if "--smoke" in sys.argv:
        try:
            root = app.mount()
            assert root is not None
            print("Native Qt task board mounted: PASS")
            return 0
        finally:
            app.unmount()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
