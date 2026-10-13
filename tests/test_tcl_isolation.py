
import tkinter as tk

import pytest


@pytest.mark.parametrize("iteration", range(200))
def test_tk_repeated_initialization(iteration):
    root = tk.Tk()
    try:
        root.update_idletasks()
        assert root.tk.call("package", "require", "Tk") == "8.6.15"
    finally:
        root.destroy()
