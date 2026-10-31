"""G2 Qt: commit SFLE-computed rectangles to actual mounted widgets.

This bridge does NOT implement CSS sizing. Native Qt sizeHint/heightForWidth
supplies intrinsic measurements; SFLE Rust/Python computes all layout boxes.
F2 NativeGeometryCommitter projects absolute top-left rectangles to the
real native parent before writing QWidget.setGeometry.
"""
from __future__ import annotations

from psx.markup.html_aliases import FORMATTING_TAGS

from dataclasses import replace
from typing import TYPE_CHECKING

from psx.sfle.native_structural_snapshot_reuse import NativeStructuralSnapshotReuse, mounted_structural_token
from psx.sfle.mixed_grid_native import MountedMixedGrid
from psx.sfle.grid_native_commit import GridCommitBackend
from psx.core.vnode import NodeKind
from psx.sfle.adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
from psx.sfle.external_native_geometry_ports import external_port_for, measure_external, read_external
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.native_pixel_space import DevicePixelSpace
from psx.sfle.model import Rect
from psx.sfle.qt_measurement import QtMeasurementSource
from psx.sfle.model import AvailableSize, LayoutConstraints
from psx.sfle.width_dependent_intrinsic_measurement import (
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
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        components: dict[int, object] = {}
        handles: dict[int, object] = {}
        mounted_stamp = []

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
            mounted_stamp.append(mounted_structural_token(instance))
            for child in instance.children:
                gather(child)

        gather(root)
        reuse = getattr(renderer, "_sfle_structural_snapshot_reuse", None)
        if reuse is None:
            reuse = NativeStructuralSnapshotReuse()
            renderer._sfle_structural_snapshot_reuse = reuse
        normalized, prepared = reuse.prepare(
            root.node, components, mounted_stamp, renderer._sfle_constraints,
            generation, invalidation_epoch,
        )
        mixed_grid = MountedMixedGrid(
            renderer, normalized, handles, GridCommitBackend.QT, generation,
        )
        bindings = {node_id: handles[id(node)] for node_id, node in prepared.identities}
        external = {
            node_id: port
            for node_id, source in prepared.identities
            if (port := external_port_for(source, renderer)) is not None
        }
        from psx.sfle.layout_change_effects import partition_dependency_signature

        (layout_signature, paint_signature), signature_safe = (
            partition_dependency_signature(
                tuple(
                    (node_id, str(source.type), id(bindings[node_id].widget),
                     source.props)
                    for node_id, source in prepared.identities
                ),
                renderer._sfle_constraints,
            )
        )
        prior_signature = getattr(renderer, "_sfle_committed_signatures", None)
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
            # External native leaves have no PSX children, so an internal Qt
            # layout belongs to the widget's own chrome (for example
            # QWebEngineView), not to competing declarative placement.
            if handle.layout is not None or (
                handle.widget.layout() is not None
                and not internal_chrome
                and node_id not in external
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

        # Only the certified Text.color-only change is eligible. The preceding
        # native layout/ownership checks must run even when the solver is reused.
        # A semantic invalidation always overrides the paint fast path.
        if (
            signature_safe
            and not external
            and not any(node.component == "Grid" for node in prepared.snapshot.nodes)
            and renderer.sfle_result is not None
            and prior_signature is not None
            and prior_signature[0] == layout_signature
            and prior_signature[1] != paint_signature
            and not renderer._sfle_measurement_invalidations.needs_commit()
        ):
            renderer._sfle_committed_signatures = (layout_signature, paint_signature)
            return

        leaf_widgets = {
            node_id: bindings[node_id].widget
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST
            and source.type not in ("Flex", "Box", "RadioGroup", "Scroll", "Grid")
            and source.type not in FORMATTING_TAGS
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
        text_ids = frozenset(
            node_id for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "Text"
        )
        source = QtMeasurementSource(
            leaf_widgets, qtcore=renderer._qtcore,
            textarea_ids=textarea_ids, text_ids=text_ids, image_ids=image_ids,
            spacer_ids=spacer_ids, divider_nodes=divider_nodes,
        )
        if not source.is_ui_thread():
            raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Qt intrinsic measurement requires widget owner thread.")
        measurements = []
        native_round = renderer._sfle_native_intrinsic_cache.begin(
            invalidate_all=renderer._sfle_measurement_invalidations.invalidate_all,
            dirty_widgets=frozenset(renderer._sfle_measurement_invalidations.dirty_widgets))
        declared_props = {node_id: dict(vnode.props)
                          for node_id, vnode in prepared.identities}
        for node_id in leaf_widgets:
            measurements.append(native_round.read(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda node_id=node_id: source.measure(MeasurementRequest(
                    node_id, renderer._sfle_constraints, generation, generation)),
                viewport_independent=not bindings[node_id].widget.hasHeightForWidth(),
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
        measurements.extend(mixed_grid.seed_measurements())
        # Consume normalized item box lengths while keeping native intrinsic
        # readings, component-owned dimensions and container styles unchanged.
        snapshot = replace(reuse.project_css(prepared), measurements=tuple(measurements))
        automatic = auto_height_measurement_ids(snapshot)
        dependent = {
            node_id: (lambda width, node_id=node_id: native_round.read_width(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints, width=width,
                measure=lambda: source.measure_width(node_id, width),
            ))
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
                    native_round.read_width(
                        widget=bindings[node_id].widget,
                        props=declared_props[node_id],
                        constraints=renderer._sfle_constraints,
                        width=width,
                        measure=lambda: measure_external(
                        port, bindings[node_id].widget,
                        LayoutConstraints(
                            AvailableSize(width, True), AvailableSize(None, False),
                        ),
                        node_id, generation,
                    ).intrinsic,
                    )
                )
        # Initial native hints describe intrinsic content, not a measurement
        # at the inherited viewport width. Width-independent controls (in
        # particular Image) must not advertise that placeholder as a certified
        # post-flex width. Dependent controls acquire definite widths below.
        dependent.update(mixed_grid.width_dependencies())
        snapshot = seed_unconstrained_width_measurements(
            snapshot, frozenset(leaf_widgets) | frozenset(dependent),
        )
        if snapshot.nodes[0].component in FORMATTING_TAGS:
            # Both Rust primary and Python fallback own the same measured flow wire.
            from psx.sfle.model import MeasuredBox
            width = renderer._sfle_constraints.width.value
            if width is None or not renderer._sfle_constraints.width.definite:
                raise SFLEError(
                    DiagnosticCode.LAYOUT_CONSTRAINT,
                    "Native Block requires a definite viewport width.",
                )
            if dependent:
                refreshed = {item.node_id: item for item in snapshot.measurements}
                for node_id, measure_at_width in dependent.items():
                    previous = refreshed.get(node_id)
                    if previous is None:
                        raise SFLEError(
                            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                            "Block text requires an initial intrinsic measurement.",
                            node_id,
                        )
                    refreshed[node_id] = MeasuredBox(
                        node_id, measure_at_width(width), previous.constraints,
                        previous.revision,
                    )
                    if renderer._sfle_generation != generation:
                        raise SFLEError(
                            DiagnosticCode.INVALID_SNAPSHOT,
                            "Stale Block width-dependent measurement.",
                            node_id,
                        )
                snapshot = replace(
                    snapshot, measurements=tuple(refreshed[node.node_id]
                    for node in snapshot.nodes if node.node_id in refreshed),
                )
            result = renderer._sfle_engine.compute(snapshot)
        else:
            result = compute_width_dependent(
                renderer._sfle_engine, snapshot, dependent,
                current_generation=lambda: renderer._sfle_generation,
                previous_input=(
                    renderer._sfle_prior_solver_input
                    if renderer._sfle_prior_solver_engine is renderer._sfle_engine else None
                ),
                previous_result=(
                    renderer._sfle_prior_solver_result
                    if renderer._sfle_prior_solver_engine is renderer._sfle_engine else None
                ),
                native_measurement_invalidated=(
                    renderer._sfle_measurement_invalidations.needs_commit()
                ),
            )

        mixed_plans = mixed_grid.plan(dict(result.boxes))

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
        # One owner-thread QWidget.geometry() read per native node is enough
        # for both atomic rollback and unchanged-placement suppression.
        # The previous implementation issued four reads per node to build
        # this tuple, then a fifth inside the native geometry committer.
        before = {}
        for node_id, handle in bindings.items():
            if node_id == snapshot.nodes[0].node_id:
                continue
            rect = handle.widget.geometry()
            before[node_id] = (
                rect.x(), rect.y(), rect.width(), rect.height(),
            )
        committer = NativeGeometryCommitter(
            GeometryBackend.QT, nodes,
            {node_id: handle.widget for node_id, handle in bindings.items()},
            external_ports=external,
            skip_unchanged=True,
            prior_qt_rectangles=before,
        )
        root_id = snapshot.nodes[0].node_id
        root_widget = bindings[root_id].widget
        semantic_shell = getattr(root_widget, "_psx_sfle_viewport_shell", None)
        original_root_geometry = root_widget.geometry() if semantic_shell is not None else None
        from psx.sfle.native_scroll_transaction import capture_scroll_hosts, restore_scroll_hosts
        scroll_before = capture_scroll_hosts("qt", bindings)
        mixed_before = mixed_grid.snapshot()
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation before native geometry.")
        # Reuse one immutable solver result index throughout native commit.
        # Previously each scroll child rebuilt dict(result.boxes), producing
        # O(N * S) geometry work for S scroll descendants.
        committed_boxes = dict(result.boxes)
        try:
            if semantic_shell is not None:
                # The window owns the viewport; the semantic host receives
                # exactly its intrinsic Cinnamon border box.
                box = committed_boxes[root_id].border
                root_widget.setGeometry(round(box.x), round(box.y),
                                        round(box.width), round(box.height))
                root_widget.show()
            committer(result)
            mixed_receipts = mixed_grid.commit(mixed_plans)
            for node in snapshot.nodes:
                if node.parent_id is not None:
                    parent = bindings[node.parent_id].widget
                    if getattr(parent, "_psx_sfle_scroll", False):
                        from psx.sfle.native_scroll_hosts import (
                            apply_qt_scroll, binding_from_host,
                        )
                        from psx.sfle.scroll_offsets import ScrollOffset
                        parent_rect = committed_boxes[node.parent_id].border
                        child_rect = committed_boxes[node.node_id].border
                        binding = binding_from_host(parent._psx_props, parent_rect, child_rect)
                        from psx.sfle.native_scroll_transaction import prior_scroll_offset
                        current = prior_scroll_offset(scroll_before, parent)
                        apply_qt_scroll(parent, binding, current)
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
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation after native geometry.")
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Qt commit.")
            rects = committed_boxes
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
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Stale semantic invalidation during native readback.",
                )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale generation during native readback.")
        except BaseException:
            if original_root_geometry is not None:
                root_widget.setGeometry(original_root_geometry)
            restore_scroll_hosts(scroll_before)
            mixed_grid.restore(mixed_before)
            for node_id, values in before.items():
                if node_id in external:
                    external[node_id].apply(bindings[node_id].widget, Rect(*values))
                else:
                    bindings[node_id].widget.setGeometry(*values)
            raise
        renderer._sfle_physical_commit_error = physical_maximum
        renderer.sfle_result = replace(result, geometry_commit_error=maximum)
        if mixed_receipts:
            renderer.grid_result = mixed_receipts[-1]
        native_round.publish()
        mixed_grid.accept_intrinsic()
        # Preserve only the most recent successful immutable snapshot.
        # Width-dependent provisional computations have separate iterative
        # measurements and cannot reuse this initial snapshot as a receipt.
        renderer._sfle_prior_solver_input = snapshot if not dependent else None
        renderer._sfle_prior_solver_result = result if not dependent else None
        renderer._sfle_prior_solver_engine = (
            renderer._sfle_engine if not dependent else None
        )
        renderer._sfle_committed_signatures = (
            (layout_signature, paint_signature) if signature_safe else None
        )
    finally:
        renderer._sfle_in_commit = False
