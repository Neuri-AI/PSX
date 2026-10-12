"""G2 Qt: commit SFLE-computed rectangles to actual mounted widgets.

This bridge does NOT implement CSS sizing. Native Qt sizeHint/heightForWidth
supplies intrinsic measurements; SFLE Rust/Python computes all layout boxes.
F2 NativeGeometryCommitter projects absolute top-left rectangles to the
real native parent before writing QWidget.setGeometry.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import NodeKind
from psx.sfle.adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.f3_snapshot import prepare_f3_snapshot
from psx.sfle.f3_external import external_port_for, measure_external, read_external
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.native_pixel_space import DevicePixelSpace
from psx.sfle.model import Rect
from psx.sfle.qt_measurement import QtMeasurementSource
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.f3_width_remeasurement import (
    compute_width_dependent, auto_height_measurement_ids,
    seed_unconstrained_width_measurements,
)

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.qt.pyqt import QtRenderer


def commit_qt_sfle(renderer: "QtRenderer", root: "MountedInstance") -> None:
    """Measure/compute/validate/apply/read back one current mounted Qt tree."""
    if renderer._sfle_constraints is None:
        return
    if renderer._qtcore.QThread.currentThread() != renderer.application.thread():
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Qt SFLE geometry commit requires the QApplication UI thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Re-entrant Qt SFLE transaction.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        components: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Qt node in SFLE tree.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Component must have one rendered root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Qt handle missing.")
                if id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Duplicate mounted VNode.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        prepared = prepare_f3_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        bindings = {node_id: handles[id(node)] for node_id, node in prepared.identities}
        external = {
            node_id: port
            for node_id, source in prepared.identities
            if (port := external_port_for(source, renderer)) is not None
        }
        # A Qt layout must never be allowed to override SFLE rectangles.
        for node_id, handle in bindings.items():
            # An SFLE leaf may use a toolkit layout for its own internal
            # chrome (SpinBox minus/editor/plus), never for declarative
            # PSX child placement. Container layouts still fail closed.
            internal_chrome = (
                (
                    handle.node_type == "SpinBox"
                    and getattr(handle.widget, "_psx_sfle_internal_layout", False)
                ) or (
                    handle.node_type == "Scroll"
                    and getattr(handle.widget, "_psx_sfle_scroll", False)
                )
            )
            if handle.layout is not None or (
                handle.widget.layout() is not None and not internal_chrome
            ):
                raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                "Qt SFLE participant is owned by a competing QLayout.", node_id)
        for node in prepared.snapshot.nodes:
            if node.parent_id is None:
                continue
            child, parent = bindings[node.node_id].widget, bindings[node.parent_id].widget
            owner = (
                parent._psx_content if getattr(parent, "_psx_sfle_scroll", False)
                else parent
            )
            if child.parentWidget() is not owner:
                raise SFLEError(DiagnosticCode.INVALID_TREE,
                                "Actual Qt parent does not match SFLE parent.", node.node_id)

        leaf_widgets = {
            node_id: bindings[node_id].widget
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST
            and source.type not in ("Flex", "Box", "RadioGroup", "Scroll")
            and not (source.type == "Divider" and source.children)
            and node_id not in external
        }
        textarea_ids = frozenset(
            node_id for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "TextArea"
        )
        image_ids = frozenset(
            node_id for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "Image"
        )
        spacer_ids = frozenset(
            node_id for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "Spacer"
        )
        divider_nodes = {
            node_id: dict(vnode.props)
            for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "Divider"
            and not vnode.children
        }
        source = QtMeasurementSource(
            leaf_widgets, qtcore=renderer._qtcore,
            textarea_ids=textarea_ids, image_ids=image_ids,
            spacer_ids=spacer_ids, divider_nodes=divider_nodes,
        )
        if not source.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt intrinsic measurement requires widget owner thread.")
        measurements = []
        native_round = renderer._sfle_native_intrinsic_cache.begin(
            invalidate_all=renderer._sfle_measurement_invalidations.needs_commit())
        declared_props = {node_id: dict(vnode.props)
                          for node_id, vnode in prepared.identities}
        for node_id in leaf_widgets:
            measurements.append(native_round.read(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda node_id=node_id: source.measure(MeasurementRequest(
                    node_id, renderer._sfle_constraints, generation, generation)),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt measurement generation.")
        for node_id, port in external.items():
            measurements.append(native_round.read(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda port=port, node_id=node_id: measure_external(
                    port, bindings[node_id].widget, renderer._sfle_constraints,
                    node_id, generation),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale external qt measurement.")
        snapshot = replace(prepared.snapshot, measurements=tuple(measurements))
        automatic = auto_height_measurement_ids(snapshot)
        dependent = {
            node_id: (lambda width, node_id=node_id: source.measure_width(node_id, width))
            for node_id, vnode in prepared.identities
            if node_id in automatic and vnode.kind is NodeKind.HOST
            and (
                (vnode.type == "Text" and bindings[node_id].widget.hasHeightForWidth())
                or vnode.type == "TextArea"
            )
        }
        for node_id, port in external.items():
            if node_id in automatic:
                dependent[node_id] = (
                    lambda width, port=port, node_id=node_id:
                    measure_external(
                        port, bindings[node_id].widget,
                        LayoutConstraints(
                            AvailableSize(width, True), AvailableSize(None, False),
                        ),
                        node_id, generation,
                    ).intrinsic
                )
        snapshot = seed_unconstrained_width_measurements(snapshot, frozenset(dependent))
        result = compute_width_dependent(
            renderer._sfle_engine, snapshot, dependent,
            current_generation=lambda: renderer._sfle_generation,
        )

        def read_widget(node_id, handle):
            port = external.get(node_id)
            if port is not None:
                widget = handle if "qt" == "tk" else handle.widget
                rect = read_external(port, widget, node_id)
                return dict(x=rect.x, y=rect.y, width=rect.width, height=rect.height)
            rect = handle.widget.geometry()
            return dict(x=float(rect.x()), y=float(rect.y()),
                        width=float(rect.width()), height=float(rect.height()))

        ports = SFLEAdapterPorts(
            current_generation=lambda: renderer._sfle_generation,
            nodes_alive=lambda ids: all(
                node_id in bindings and bindings[node_id].widget is not None
                for node_id in ids
            ),
            apply_rectangles=lambda _: None,
            read_rectangles=lambda: {
                node_id: read_widget(node_id, handle)
                for node_id, handle in bindings.items()
            },
        )
        validate_adapter_commit(snapshot, result, ports)
        if renderer._sfle_generation != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt geometry result.")

        pixel_space = DevicePixelSpace.from_widget(
            "qt", bindings[snapshot.nodes[0].node_id].widget,
        )
        # F2 projection explicitly skips the root/window (host owned).
        # Parent IDs/rectangles are supplied verbatim from the SFLE snapshot.
        nodes = tuple(
            MarginTreeNode(node.node_id, node.parent_id, 0, 0)
            for node in snapshot.nodes
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.QT, nodes,
            {node_id: handle.widget for node_id, handle in bindings.items()},
            external_ports=external,
        )
        before = {
            node_id: (
                widget.widget.geometry().x(), widget.widget.geometry().y(),
                widget.widget.geometry().width(), widget.widget.geometry().height(),
            )
            for node_id, widget in bindings.items()
            if node_id != snapshot.nodes[0].node_id
        }
        try:
            committer(result)
            for node in snapshot.nodes:
                if node.parent_id is not None:
                    parent = bindings[node.parent_id].widget
                    if getattr(parent, "_psx_sfle_scroll", False):
                        content = parent._psx_content
                        box = dict(result.boxes)[node.node_id].border
                        content.resize(
                            max(parent.viewport().width(), round(box.width)),
                            max(parent.viewport().height(), round(box.height)),
                        )
            # A labeled Divider paints two line segments around its child's
            # *committed* native rectangle, never a speculative sizeHint.
            for node_id, vnode in prepared.identities:
                if vnode.kind is NodeKind.HOST and vnode.type == "Divider" and vnode.children:
                    bindings[node_id].widget.update()
            # Repaint inside SFLE's committed rectangle, never QPixmap's
            # natural dimensions or a competing QLabel.setFixedSize().
            if image_ids:
                from psx.renderers.qt.image import QtImageAdapter
                for node_id in image_ids:
                    widget = bindings[node_id].widget
                    QtImageAdapter.paint_sfle(
                        widget, widget.width(), widget.height(),
                        renderer._binding_package,
                    )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt commit.")
            rects = dict(result.boxes)
            maximum = 0.0
            physical_maximum = 0.0
            observed = ports.read_rectangles()
            for node in snapshot.nodes:
                if node.parent_id is None:
                    continue
                rect, parent = rects[node.node_id].border, rects[node.parent_id].border
                expected = (rect.x - parent.x, rect.y - parent.y, rect.width, rect.height)
                actual = observed[node.node_id]
                logical_error, physical_error = pixel_space.error(
                    Rect(*expected),
                    Rect(*(actual[axis] for axis in ("x", "y", "width", "height"))),
                )
                maximum = max(maximum, logical_error)
                physical_maximum = max(physical_maximum, physical_error)
            if maximum > 1.0 or physical_maximum > pixel_space.allowed_physical_error:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Qt widget geometry readback exceeds 1px tolerance.")
        except BaseException:
            for node_id, values in before.items():
                if node_id in external:
                    external[node_id].apply(bindings[node_id].widget, Rect(*values))
                else:
                    bindings[node_id].widget.setGeometry(*values)
            raise
        renderer._sfle_physical_commit_error = physical_maximum
        renderer.sfle_result = replace(result, geometry_commit_error=maximum)
        native_round.publish()
    finally:
        renderer._sfle_in_commit = False
