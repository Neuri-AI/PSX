"""Native SFLE explicit external leaf port invariants, toolkit-independent."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from psx.core.errors import RendererCapabilityError
from psx.core.native import Native, NativeWidget
from psx.core.vnode import create_element, native_widget
from psx.renderers.adapters import DelegatingAdapter, RendererAdapterRegistry
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.external_native_geometry_ports import (
    SFLEExternalPort, external_port_for, measure_external, read_external,
)
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, MeasuredBox, Rect,
    LayoutResult, BoxRect,
)
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter


def constraints():
    return LayoutConstraints(AvailableSize(120, True), AvailableSize(80, True))


def metrics():
    return IntrinsicSizes(8, 16, 6, 10, 16, 10)


def port():
    return SFLEExternalPort(
        measure=lambda widget, c: metrics(),
        apply=lambda widget, rect: setattr(widget, "rect", rect),
        read=lambda widget: widget.rect,
    )


def fake_renderer(backend="qt"):
    registry = RendererAdapterRegistry()
    registry.register("Opaque", DelegatingAdapter())
    return SimpleNamespace(_sfle_backend=backend, adapters=registry)


def test_port_must_define_all_three_required_callbacks():
    for name in ("measure", "apply", "read"):
        args = dict(measure=lambda w, c: metrics(), apply=lambda w, r: None,
                    read=lambda w: Rect(0, 0, 0, 0))
        args[name] = None
        with pytest.raises(TypeError, match=name):
            SFLEExternalPort(**args)


def test_native_without_geometry_port_rejected_before_mount():
    decl = NativeWidget(renderer="pyside6", factory=lambda: object())
    with pytest.raises(RendererCapabilityError, match="Native requires"):
        external_port_for(native_widget(decl), fake_renderer())


@pytest.mark.parametrize("renderer", ["pyside6", "tkinter", "kivy"])
def test_native_supplies_a_standard_geometry_port_for_supported_toolkits(renderer):
    node = Native(lambda: object(), renderer=renderer)
    assert isinstance(node.type, NativeWidget)
    assert isinstance(node.type.sfle_port, SFLEExternalPort)


def test_native_port_is_attached_to_declaration_without_native_imports():
    bound = port()
    decl = NativeWidget(renderer="pyside6", factory=lambda: object(), sfle_port=bound)
    assert external_port_for(native_widget(decl), fake_renderer()) is bound
    with pytest.raises(TypeError, match="sfle_port"):
        NativeWidget(renderer="pyside6", factory=lambda: object(), sfle_port=object())


def test_custom_registered_adapter_must_declare_port():
    renderer = fake_renderer()
    node = create_element("Opaque", layout_width="20px")
    with pytest.raises(RendererCapabilityError, match="not certified"):
        external_port_for(node, renderer)

    class Adapter: pass
    adapter = Adapter()
    renderer.adapters.register("Opaque", adapter, replace=True)
    with pytest.raises(RendererCapabilityError, match="sfle_port"):
        external_port_for(node, renderer)
    adapter.sfle_port = port()
    assert external_port_for(node, renderer) is adapter.sfle_port


def test_external_custom_node_cannot_own_psx_children():
    renderer = fake_renderer()
    renderer.adapters.register(
        "Opaque", SimpleNamespace(sfle_port=port()), replace=True,
    )
    from psx import Text
    with pytest.raises(RendererCapabilityError, match="must be a leaf"):
        external_port_for(create_element("Opaque", Text("child")), renderer)


def test_native_external_measurements_are_real_and_revision_tagged():
    widget = object()
    measured = measure_external(port(), widget, constraints(), "n", 21)
    assert isinstance(measured, MeasuredBox)
    assert measured.node_id == "n"
    assert measured.revision == 21
    assert measured.intrinsic == metrics()


def test_invalid_native_measurement_and_readback_are_rejected():
    wrong_measure = SFLEExternalPort(
        measure=lambda w, c: (20, 30),
        apply=lambda w, r: None, read=lambda w: Rect(0, 0, 0, 0),
    )
    with pytest.raises(SFLEError) as error:
        measure_external(wrong_measure, object(), constraints(), "bad", 1)
    assert error.value.code is DiagnosticCode.UNSUPPORTED_MEASUREMENT
    wrong_read = SFLEExternalPort(
        measure=lambda w, c: metrics(),
        apply=lambda w, r: None, read=lambda w: (0, 0, 10, 10),
    )
    with pytest.raises(SFLEError) as error:
        read_external(wrong_read, object(), "bad")
    assert error.value.code is DiagnosticCode.INVALID_SNAPSHOT


def test_native_geometry_projection_calls_external_port_only_for_its_node():
    class Builtin:
        def __init__(self):
            self.geometry = None
        def setGeometry(self, x, y, width, height):
            self.geometry = Rect(x, y, width, height)

    native = SimpleNamespace(rect=None)
    builtin = Builtin()
    measurements = []
    ext = SFLEExternalPort(
        measure=lambda w, c: metrics(),
        apply=lambda w, rect: (measurements.append(rect), setattr(w, "rect", rect)),
        read=lambda w: w.rect,
    )
    nodes = (
        MarginTreeNode("root", None, 0, 0),
        MarginTreeNode("external", "root", 0, 0),
        MarginTreeNode("builtin", "root", 0, 0),
    )
    from psx.sfle.model import BoxRect
    def box(x, y, w, h):
        r = Rect(x, y, w, h)
        return BoxRect(r, r, r, r)
    result = LayoutResult(1, 4, (
        ("root", box(0, 0, 120, 80)),
        ("external", box(10, 15, 30, 20)),
        ("builtin", box(50, 30, 12, 16)),
    ))
    NativeGeometryCommitter(
        GeometryBackend.QT, nodes,
        {"root": object(), "external": native, "builtin": builtin},
        external_ports={"external": ext},
    )(result)
    assert measurements == [Rect(10, 15, 30, 20)]
    assert native.rect == Rect(10, 15, 30, 20)
    assert builtin.geometry == Rect(50, 30, 12, 16)


def test_native_declaration_rejects_invalid_ownership_and_ports_before_mount():
    from psx.core.native import NativeOwnership

    cases = (
        {"renderer": "kivy", "factory": lambda: object(),
         "ownership": NativeOwnership.BORROWED},
        {"renderer": "kivy", "widget": object(),
         "ownership": NativeOwnership.OWNED},
        {"renderer": "kivy", "factory": lambda: object(), "widget": object()},
        {"renderer": "kivy"},
        {"renderer": "kivy", "widget": object(), "takes_parent": True,
         "ownership": NativeOwnership.BORROWED},
    )
    for case in cases:
        with pytest.raises((ValueError, TypeError)):
            NativeWidget(**case)

    with pytest.raises(TypeError, match="sfle_port"):
        NativeWidget(renderer="kivy", widget=object(),
                     ownership="borrowed", sfle_port=object())
    for backend in ("pyside6", "pyqt6", "pyqt5", "pyside2", "kivy", "tkinter"):
        assert NativeWidget(renderer=backend, factory=lambda: object(),
                            sfle_port=port()).ownership is NativeOwnership.OWNED
        assert NativeWidget(renderer=backend, widget=object(),
                            ownership="borrowed", sfle_port=port()).ownership is NativeOwnership.BORROWED


def test_external_port_never_changes_widget_ownership_during_measure_and_read():
    from psx.core.native import NativeOwnership
    from psx.sfle.native_operation_oracles import Observation, ORACLES

    host = SimpleNamespace(rect=Rect(2, 3, 15, 10), destroyed=False)
    decl = NativeWidget(renderer="pyside6", widget=host,
                        ownership=NativeOwnership.BORROWED, sfle_port=port())
    before = Observation(id(host), True, (2, 3, 15, 10), owner="caller")
    measured = measure_external(port(), host, constraints(), "native", 1)
    assert measured is not None
    assert measured.node_id == "native"
    assert read_external(port(), host, "native") == Rect(2, 3, 15, 10)
    after = Observation(id(host), False, (2, 3, 15, 10),
                        owner="caller", disposed=host.destroyed)
    ORACLES["borrowed_ownership"](before, after)
    assert decl.widget is host
