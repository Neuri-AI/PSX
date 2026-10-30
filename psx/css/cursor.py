"""Portable CSS cursor names and native toolkit mappings.

Mappings use documented, available platform cursor shapes. When the native
toolkit cannot represent a distinct CSS shape (e.g. context-menu on SDL2),
fall back explicitly to its normal arrow, never invent an unsupported name.
"""

CSS_CURSOR_VALUES = frozenset({
    "auto", "default", "none", "context-menu", "help",
    "pointer", "progress", "wait",
})

QT_CURSOR_SHAPES = {
    "default": "ArrowCursor",
    "none": "BlankCursor",
    "context-menu": "ArrowCursor",  # no Qt CursorShape for CSS context-menu
    "help": "WhatsThisCursor",
    "pointer": "PointingHandCursor",
    "progress": "BusyCursor",
    "wait": "WaitCursor",
}

TK_CURSOR_SHAPES = {
    "default": "arrow",
    "none": "none",      # may be absent on Aqua/Windows Tk distributions
    "context-menu": "arrow",
    "help": "question_arrow",
    "pointer": "hand2",
    "progress": "watch",
    "wait": "watch",
}

KIVY_CURSOR_SHAPES = {
    "default": "arrow",
    "none": "arrow",  # hidden with Window.show_cursor=False, not SDL 'no'
    "context-menu": "arrow",
    "help": "arrow",
    "pointer": "hand",
    "progress": "wait_arrow",
    "wait": "wait",
}
