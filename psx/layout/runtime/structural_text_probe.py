"""Bounded native text metrics without materializing a logical text widget.

One renderer-owned scratch label serves structural intrinsic queries. It is
never inserted into the application's native hierarchy or exposed by refs.
All glyph metrics still come from the backend's existing measurement source.
"""
from __future__ import annotations
from dataclasses import replace

from psx.core.structural_binding import StructuralBinding


class StructuralTextProbe:
    def __init__(self, renderer):
        self.renderer = renderer
        self.handle = None
        self.node = None
        self.measurements = {}
        self.css_epoch = None

    def close(self):
        if self.handle is not None:
            self.renderer.destroy(self.handle)
            self.handle = None
        self.node = None
        self.measurements.clear()
        self.css_epoch = None

    def measure(self, node, width, backend, *, text_metrics=False):
        renderer = self.renderer
        source = node.source
        epoch = renderer._sfle_measurement_invalidations.epoch
        key = (id(source), width, epoch, text_metrics)
        cached = self.measurements.get(key)
        if cached is not None and cached[0] is source:
            return cached[1]
        if self.handle is None:
            parent = renderer._psx_reconciler.root.native_handle()
            self.handle = renderer.create(source, parent)
        widget = self.handle.widget
        activating = getattr(renderer, "_psx_native_activation_widget_ids", None)
        if activating is None:
            activating = set()
            renderer._psx_native_activation_widget_ids = activating
        activating.add(id(widget))
        try:
            reset_css = False
            if self.node is not None:
                from psx.core.reconcile import _prop_delta
                changed, removed = _prop_delta(self.node.props, source.props)
                if set(changed) == {"value"} and not removed:
                    # Portable Text.update() also resets its font and color
                    # defaults. The private scratch label needs only new
                    # glyph content, retaining the already projected CSS.
                    from psx.core.contracts import validate_text_props
                    validate_text_props(changed)
                    value = str(changed["value"])
                    if backend == "qt":
                        widget.setText(value)
                    elif backend == "tk":
                        widget.configure(text=value)
                    else:
                        widget.text = value
                    self.handle.props["value"] = changed["value"]
                elif changed or removed:
                    renderer.update(self.handle, changed, removed)
                    reset_css = True
            previous_css = getattr(self.node, "css_computed", None)
            current_css = source.css_computed
            same_css = (previous_css is current_css or (
                previous_css is not None and current_css is not None
                and type(previous_css) is type(current_css)
                and getattr(previous_css, "properties", None) == getattr(current_css, "properties", None)
                and getattr(previous_css, "specified", None) == getattr(current_css, "specified", None)))
            if self.node is None or reset_css or not same_css or self.css_epoch != epoch:
                renderer.apply_css(self.handle, current_css)
                self.css_epoch = epoch
            self.node = source
            if backend == "qt":
                from psx.renderers.qt.cinnamon_qt_measurement import QtMeasurementSource
                port = QtMeasurementSource(
                    {"probe": widget}, qtcore=renderer._qtcore,
                    text_ids=frozenset({"probe"}) if text_metrics else frozenset(),
                )
            elif backend == "tk":
                from psx.renderers.tkinter.cinnamon_tk_measurement import TkMeasurementSource
                port = TkMeasurementSource({"probe": widget})
            else:
                from psx.renderers.kivy.cinnamon_kivy_measurement import KivyMeasurementSource
                port = KivyMeasurementSource({"probe": widget})
            if width is None and backend != "kivy":
                from psx.layout.contracts.model import AvailableSize, LayoutConstraints
                from psx.layout.runtime.measurement_plan import MeasurementRequest
                if backend == "qt":
                    port._text_ids = frozenset({"probe"})
                else:
                    # The scratch label's text was just changed. Tk's
                    # requested size is asynchronous even with wraplength=0.
                    widget.update_idletasks()
                result = port.measure(MeasurementRequest("probe", LayoutConstraints(
                    AvailableSize(None, False), AvailableSize(None, False)), 0, 0)).intrinsic
                if backend == "qt":
                    # QFontMetrics rounds advances to integer logical pixels;
                    # QTextDocument can need the fractional remainder. Keep a
                    # conservative pixel in both the probe and its threshold.
                    natural_width = result.preferred_width + 1.0
                    result = port.measure_width("probe", natural_width)
                    result = replace(result, preferred_width=natural_width,
                                     max_content_width=max(result.max_content_width, natural_width))
            else:
                result = port.measure_width("probe", width)
        finally:
            activating.discard(id(widget))
        if len(self.measurements) >= 32768:
            self.measurements.clear()
        self.measurements[key] = (source, result)
        return result


def measure_without_native_handle(renderer, node, handles, width, backend):
    binding = handles[id(node.source)]
    if (not isinstance(binding, StructuralBinding) or node.type != "Text"
            or not binding.instance.native_suspended):
        return None
    probe = getattr(renderer, "_psx_structural_text_probe", None)
    if probe is None:
        probe = StructuralTextProbe(renderer)
        renderer._psx_structural_text_probe = probe
    return probe.measure(node, width, backend)


class StructuralMeasurementSource:
    """Route absent Text leaves through the shared native metric probe."""

    def __init__(self, renderer, source, widgets, identities, backend):
        from psx.core.structural_binding import DormantWidgetIdentity
        self.renderer, self.source, self.backend = renderer, source, backend
        self.identities = dict(identities)
        self.dormant = {key for key, widget in widgets.items()
                        if isinstance(widget, DormantWidgetIdentity)}
        source._widgets = {key: widget for key, widget in source._widgets.items()
                           if key not in self.dormant}

    def is_ui_thread(self):
        return self.source.is_ui_thread()

    def measure_width(self, node_id, width):
        if node_id not in self.dormant:
            return self.source.measure_width(node_id, width)
        from types import SimpleNamespace
        vnode = self.identities[node_id]
        if vnode.type != "Text":
            raise RuntimeError("An absent native control requires materialization")
        probe = getattr(self.renderer, "_psx_structural_text_probe", None)
        if probe is None:
            probe = StructuralTextProbe(self.renderer)
            self.renderer._psx_structural_text_probe = probe
        return probe.measure(SimpleNamespace(source=vnode, type="Text"),
                             width, self.backend, text_metrics=True)

    def measure(self, request):
        if request.node_id not in self.dormant:
            return self.source.measure(request)
        from psx.layout.contracts.model import MeasuredBox
        return MeasuredBox(
            request.node_id,
            self.measure_width(request.node_id, request.constraints.width.value),
            request.constraints, request.revision,
        )
