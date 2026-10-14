
import tkinter as tk


def test_tk_batch_initialization():
    for iteration in range(200):
        root = tk.Tk()
        try:
            root.update_idletasks()
            assert root.tk.call("package", "require", "Tk") == "8.6.15"
        finally:
            root.destroy()
