# Qyro + PSX + Tkinter demo

This project was generated with `qyro init --binding Tkinter` and adapted to
use `PSXComponent`. Qyro owns the application context and Tk main loop; PSX
owns only the packed declarative subtree.

`main.py` uses M4B markup with `self` attributes, local state and a callback.
`qyro start` automatically prepares literal PSX markup, so no `scope` mapping
or manual transform step is required:

```bash
PYTHONPATH=../../src /Users/fredo/miniconda3/bin/conda run -n osx310 qyro start
```

`Column` and `Row` are ttk frames managed with `pack`; see
[M7 Tkinter notes](../../docs/m7-tkinter.md) for the documented approximations.

---

> **The official, zero-dependency Tkinter desktop starter template for the [Qyro](https://github.com/Neuri-AI/qyro) ecosystem.**

[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![Framework](https://img.shields.io/badge/GUI-Tkinter%20(Built--in)-green.svg)](https://docs.python.org/3/library/tkinter.html)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 🌟 Overview

`qyro-boilerplate-tkinter` is the lightweight, zero-dependency starter template used by `qyro-cli` to scaffold desktop applications in seconds. It uses Python's built-in `tkinter` library while giving you modern tooling: reactive state, smart asset resolution, and simplified packaging.

Perfect for lightweight utilities, internal tools, and projects where bundle size and instant startup matter.

---

## ✨ Features

* **🪶 Zero External GUI Dependencies:** Runs out of the box using Python's standard library.
* **⚡ Reactive State Management:** Centralized state store and event subscriptions directly in your Tkinter app.
* **📦 Smart Resource Resolver:** Automated detection of icons and images (`resources/base/`, `resources/windows/`, `resources/mac/`, `resources/linux/`).
* **❄️ Packaging Ready:** Pre-configured for building ultra-compact executables with PyInstaller.
* **🎨 Window Auto-Config:** Automatic window title, sizing, and icon binding from `settings/base.json`.

---

## 🚀 Usage

Scaffold a new project automatically using the **Qyro CLI**:

```bash
# Create a Tkinter project
qyro init -n my-app --binding Tkinter
