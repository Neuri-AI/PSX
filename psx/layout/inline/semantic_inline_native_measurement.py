"""Lazy, renderer-owned native font metric ports.

Importing this module must NOT import unavailable Qt/Tk/Kivy toolkits.
"""
def qt_inline_measure(widgets):
    from psx.renderers.qt.inline_measurement import qt_inline_measure as impl
    return impl(widgets)


def tk_inline_measure(widgets):
    from psx.renderers.tkinter.inline_measurement import tk_inline_measure as impl
    return impl(widgets)


def kivy_inline_measure(widgets):
    from psx.renderers.kivy.inline_measurement import kivy_inline_measure as impl
    return impl(widgets)


__all__ = ["qt_inline_measure", "tk_inline_measure", "kivy_inline_measure"]
