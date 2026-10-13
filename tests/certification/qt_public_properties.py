"""Feature-specific native observables shared by the four Qt binding runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable


@dataclass(frozen=True)
class NativePropertyCase:
    component: str
    prop: str
    before: object
    after: object
    read: Callable
    expected_before: object = None
    expected_after: object = None
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return f"{self.component}-{self.prop}"


def enum_number(value):
    return value.value if hasattr(value, "value") else int(value)


def color(widget):
    widget.ensurePolished()
    return widget.palette().color(widget.foregroundRole()).name()


def cases():
    result = []
    def add(name, prop, before, after, read, *, expected=None, extra=None):
        old, new = expected if expected is not None else (before, after)
        result.append(NativePropertyCase(name, prop, before, after, read,
                                         old, new, extra or {}))
    for name in ("Text", "Button", "Input", "Checkbox", "TextArea", "Slider",
                 "ProgressBar", "Radio", "RadioGroup", "Select", "Switch",
                 "Link", "Badge", "SpinBox", "Image", "Scroll"):
        add(name, "enabled", True, False, lambda w: w.isEnabled())
    add("Text", "value", "Before", "After", lambda w: w.text())
    add("Text", "font_size", 12, 24, lambda w: w.font().pixelSize())
    add("Text", "bold", False, True, lambda w: w.font().bold())
    add("Text", "italic", False, True, lambda w: w.font().italic())
    add("Text", "color", "#1254ab", "#ba3214", color)
    add("Text", "align", "left", "right", lambda w: enum_number(w.alignment()) & 7,
        expected=(1, 2))
    add("Button", "font_size", 11, 22, lambda w: w.font().pixelSize())
    for name in ("Input", "TextArea"):
        add(name, "font_size", 11, 22, lambda w: w.font().pointSize())
    for name in ("Button", "Radio", "Link"):
        add(name, "label", "Before", "After", lambda w: w.text())
    add("Switch", "label", "Before", "After", lambda w: w.accessibleName())
    add("Badge", "label", "Before", "After", lambda w: w.accessibleName())
    for name in ("Checkbox", "Switch"):
        add(name, "checked", False, True, lambda w: w.isChecked())
    for name in ("Input", "TextArea"):
        add(name, "value", "Before", "After", lambda w: w.text() if hasattr(w, "text") else w.toPlainText())
        add(name, "placeholder", "First hint", "Second hint", lambda w: w.placeholderText())
        add(name, "read_only", False, True, lambda w: w.isReadOnly())
    add("Input", "password", False, True, lambda w: enum_number(w.echoMode()), expected=(0, 2))
    for name in ("Slider", "ProgressBar"):
        add(name, "orientation", "horizontal", "vertical", lambda w: enum_number(w.orientation()), expected=(1, 2))
        add(name, "min", -5, -10, lambda w: w.minimum(), expected=(-5000, -10000))
        add(name, "max", 100, 200, lambda w: w.maximum(), expected=(100000, 200000))
        add(name, "value", 25, 75, lambda w: w.value(), expected=(25000, 75000))
    add("Slider", "step", 1, 2, lambda w: w.singleStep(), expected=(1, 2))
    add("ProgressBar", "indeterminate", False, True, lambda w: (w.minimum(), w.maximum()), expected=((0, 100000), (0, 0)))
    add("Divider", "orientation", "horizontal", "vertical", lambda w: enum_number(w.frameShape()), expected=(4, 5))
    add("Divider", "thickness", 1, 5, lambda w: w.lineWidth())
    add("Divider", "color", "#1254ab", "#ba3214", color)
    add("Link", "underline", False, True, lambda w: w.font().underline())
    add("Link", "color", "#1254ab", "#ba3214", color)
    add("Badge", "size", "small", "large", lambda w: w.font().pointSize(), expected=(11, 14))
    add("Select", "placeholder", "Choose one", "Pick one", lambda w: w.itemText(0))
    add("Select", "options", ("Alpha", "Beta"), ("Gamma", "Delta", "Omega"),
        lambda w: tuple(w.itemText(i) for i in range(1, w.count())))
    add("Select", "value", "Alpha", "Beta", lambda w: w.currentData(), extra={"options": ("Alpha", "Beta")})
    add("SpinBox", "value", 2, 8, lambda w: w.findChildren(type(w._psx_parts[1]))[0].text(), expected=("2", "8"))
    add("SpinBox", "decimals", 0, 2, lambda w: w._psx_parts[1].text(), expected=("2", "2.25"), extra={"value": 2.25})
    add("Image", "alt", "First description", "Second description", lambda w: w.accessibleName())
    return tuple(result)


NATIVE_PROPERTY_CASES = cases()
