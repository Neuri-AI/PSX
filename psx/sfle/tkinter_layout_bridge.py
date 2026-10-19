"""G2 production geometry bridge for real Tkinter widgets.

F2 SFLE is the sole layout engine. This bridge measures live ttk widgets on
their owning Tk thread, computes an immutable SFLE snapshot, and applies its
border rectangles through F2 NativeGeometryCommitter's place() projection.
No pack/grid/fake text measurements or second CSS layout algorithm.
"""
from __future__ import annotations

from dataclasses import replace
from threading import get_ident
from typing import TYPE_CHECKING

from psx.core.layout_tree import normalize_flex_tree
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
from psx.sfle.tk_measurement import TkMeasurementSource
from psx.sfle.model import LayoutConstraints, AvailableSize
from psx.sfle.width_dependent_intrinsic_measurement import (
    compute_width_dependent, auto_height_measurement_ids,
    seed_unconstrained_width_measurements,
)

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.tkinter.tkinter import TkinterRenderer


def _geometry(widget: object) -> dict[str, float]:
    """Read Tk's actual placed rectangle, including on an unmapped test root."""
    placement = widget.place_info()
    if not placement:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                        "Tk SFLE widget has no native place() geometry.")
    return {
        axis: float(placement[axis])
        for axis in ("x", "y", "width", "height")
    }


def commit_tk_sfle(renderer: "TkinterRenderer", root: "MountedInstance") -> None:
    """Preflight, measure, compute, place, and verify one mounted SFLE tree."""
    if renderer._sfle_constraints is None:
        return
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Tk SFLE commit must run on the owning Tcl/Tk thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Re-entrant Tk SFLE commit.")

    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        components: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed Tk SFLE node.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE,
                                    "Function component needs one mounted root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None or id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing or duplicated Tk handle.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        mixed_grid = MountedMixedGrid(
            renderer, normalized, handles, GridCommitBackend.TK, generation,
        )
        prepared = prepare_native_layout_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        widgets = {node_id: handles[id(node)].widget for node_id, node in prepared.identities}
        external = {
            node_id: port
            for node_id, source in prepared.identities
            if (port := external_port_for(source, renderer)) is not None
        }
        from psx.sfle.layout_change_effects import partition_dependency_signature

        (layout_signature, paint_signature), signature_safe = (
            partition_dependency_signature(
                tuple(
                    (node_id, str(source.type), id(widgets[node_id]), source.props)
                    for node_id, source in prepared.identities
                ),
                renderer._sfle_constraints,
            )
        )
        prior_signature = getattr(renderer, "_sfle_committed_signatures", None)

        root_id = prepared.snapshot.nodes[0].node_id

        for node in prepared.snapshot.nodes:
            widget = widgets[node.node_id]
            if not widget.winfo_exists():
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Disposed Tk widget in mounted SFLE tree.", node.node_id)
            if widget.winfo_manager() not in ("", "place"):
                raise SFLEError(DiagnosticCode.UNSUPPORTED_FEATURE,
                                "A Tk pack/grid manager cannot override SFLE geometry.", node.node_id)
            if node.parent_id is None:
                if widget.master is not renderer.root:
                    raise SFLEError(DiagnosticCode.INVALID_TREE,
                                    "Tk root Flex must belong directly to its renderer host.", node.node_id)
            elif widget.master is not (
                widgets[node.parent_id]._psx_content
                if getattr(widgets[node.parent_id], "_psx_sfle_scroll", False)
                else widgets[node.parent_id]
            ):
                raise SFLEError(DiagnosticCode.INVALID_TREE,
                                "Tk widget master must match SFLE node parent.", node.node_id)

        # Native ownership and placement checks precede the fast path.
        # Unrecognized/unsafe properties, external leaves, Grid and semantic
        # invalidations always retain the full measurement/layout transaction.
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
            node_id: widgets[node_id]
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST
            and source.type not in ("Flex", "Box", "RadioGroup", "Scroll", "Grid")
            and not (source.type == "Divider" and source.children)
            and node_id not in external
        }
        # Let Tcl calculate requested sizes without giving it layout authority.
        renderer.root.update_idletasks()
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
        source = TkMeasurementSource(
            leaf_widgets, textarea_ids=textarea_ids, image_ids=image_ids,
            spacer_ids=spacer_ids, divider_nodes=divider_nodes,
        )
        readings = []
        native_round = renderer._sfle_native_intrinsic_cache.begin(
            invalidate_all=renderer._sfle_measurement_invalidations.invalidate_all,
            dirty_widgets=frozenset(renderer._sfle_measurement_invalidations.dirty_widgets))
        declared_props = {node_id: dict(vnode.props)
                          for node_id, vnode in prepared.identities}
        for node_id in leaf_widgets:
            readings.append(native_round.read(
                widget=widgets[node_id], props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda node_id=node_id: source.measure(MeasurementRequest(
                    node_id, renderer._sfle_constraints, generation, generation)),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Tk measurement.")
        for node_id, port in external.items():
            readings.append(native_round.read(
                widget=widgets[node_id], props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda port=port, node_id=node_id: measure_external(
                    port, widgets[node_id], renderer._sfle_constraints,
                    node_id, generation),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale external tk measurement.")
        readings.extend(mixed_grid.seed_measurements())
        # Normalize explicitly declared item box lengths after native Tk
        # measurements, retaining the existing container and Grid contracts.
        snapshot = replace(prepared.canonical_snapshot(), measurements=tuple(readings))
        automatic = auto_height_measurement_ids(snapshot)
        dependent = {
            node_id: (lambda width, node_id=node_id: native_round.read_width(
                widget=widgets[node_id], props=declared_props[node_id],
                constraints=renderer._sfle_constraints, width=width,
                measure=lambda: source.measure_width(node_id, width),
            ))
            for node_id, vnode in prepared.identities
            if node_id in automatic and vnode.kind is NodeKind.HOST
            and vnode.type in ("Text", "TextArea")
        }
        for node_id, port in external.items():
            if node_id in automatic:
                dependent[node_id] = (
                    lambda width, port=port, node_id=node_id:
                    native_round.read_width(
                        widget=widgets[node_id],
                        props=declared_props[node_id],
                        constraints=renderer._sfle_constraints,
                        width=width,
                        measure=lambda: measure_external(
                        port, widgets[node_id],
                        LayoutConstraints(AvailableSize(width, True), AvailableSize(None, False)),
                        node_id, generation,
                    ).intrinsic,
                    )
                )
        dependent.update(mixed_grid.width_dependencies())
        snapshot = seed_unconstrained_width_measurements(snapshot, frozenset(dependent))
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
                widget = handle if "tk" == "tk" else handle.widget
                rect = read_external(port, widget, node_id)
                return dict(x=rect.x, y=rect.y, width=rect.width, height=rect.height)
            return _geometry(handle)

        ports = SFLEAdapterPorts(
            current_generation=lambda: renderer._sfle_generation,
            nodes_alive=lambda ids: all(
                node_id in widgets and widgets[node_id].winfo_exists() for node_id in ids
            ),
            apply_rectangles=lambda _: None,
            read_rectangles=lambda: {
                node_id: read_widget(node_id, widget)
                for node_id, widget in widgets.items()
                if widget.winfo_manager() == "place"
            },
        )
        validate_adapter_commit(snapshot, result, ports)
        if renderer._sfle_generation != generation:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Tk geometry result.")

        pixel_space = DevicePixelSpace.from_widget("tk", renderer.root)
        rectangles = dict(result.boxes)
        border_root = rectangles[root_id].border
        host_box = _geometry(widgets[root_id])
        if abs(host_box["width"] - border_root.width) > 1.0 or abs(
            host_box["height"] - border_root.height
        ) > 1.0:
            raise SFLEError(
                DiagnosticCode.LAYOUT_CONSTRAINT,
                "Tk root border box differs from the native viewport; "
                "update constraints/content-box dimensions.", root_id,
            )

        nodes = tuple(
            MarginTreeNode(node.node_id, node.parent_id, 0, 0)
            for node in snapshot.nodes
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.TK, nodes, widgets, external_ports=external,
            skip_unchanged=True,
        )
        before = {
            node_id: dict(widget.place_info())
            for node_id, widget in widgets.items() if node_id != root_id
        }
        previous_wraps = {
            node_id: widget.cget("wraplength")
            for node_id, widget in leaf_widgets.items()
            if node_id in dependent and "wraplength" in widget.keys()
        }
        from psx.sfle.native_scroll_transaction import capture_scroll_hosts, restore_scroll_hosts
        scroll_before = capture_scroll_hosts("tk", widgets)
        mixed_before = mixed_grid.snapshot()
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation before native geometry.")
        try:
            # F2 checks signed 1/64px precision before mutating a single child.
            committer(result)
            mixed_receipts = mixed_grid.commit(mixed_plans)
            for node in snapshot.nodes:
                if node.parent_id is not None:
                    parent = widgets[node.parent_id]
                    if getattr(parent, "_psx_sfle_scroll", False):
                        from psx.sfle.native_scroll_hosts import (
                            apply_tk_scroll, binding_from_host,
                        )
                        from psx.sfle.scroll_offsets import ScrollOffset
                        binding = binding_from_host(
                            parent._psx_props,
                            rectangles[node.parent_id].border,
                            rectangles[node.node_id].border,
                        )
                        canvas = parent._psx_canvas
                        from psx.sfle.native_scroll_transaction import prior_scroll_offset
                        current = prior_scroll_offset(scroll_before, parent)
                        apply_tk_scroll(parent, binding, current)
            if image_ids:
                from psx.renderers.tkinter.image import TkImageAdapter
                for node_id in image_ids:
                    widget = widgets[node_id]
                    rect = rectangles[node_id].border
                    TkImageAdapter.paint_sfle(
                        widget, round(rect.width), round(rect.height),
                    )
            # Apply the SAME measured content width to actual native text
            # painting, otherwise Tk could show a single-line clipped label
            # even though SFLE correctly reserved multiline block height.
            for node_id in previous_wraps:
                widgets[node_id].configure(
                    wraplength=max(1, round(rectangles[node_id].content.width)),
                )
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale semantic invalidation after native geometry.")
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Tk geometry commit.")
            renderer.root.update_idletasks()
            for node_id, vnode in prepared.identities:
                if vnode.kind is NodeKind.HOST and vnode.type == "Divider" and vnode.children:
                    from psx.renderers.tkinter.divider import TkDividerAdapter
                    TkDividerAdapter()._redraw(widgets[node_id], widgets[node_id]._psx_props)
            observed = ports.read_rectangles()
            error = 0.0
            physical_error_maximum = 0.0
            for node in snapshot.nodes:
                if node.parent_id is None:
                    continue
                child = rectangles[node.node_id].border
                parent = rectangles[node.parent_id].border
                expected = (child.x - parent.x, child.y - parent.y,
                            child.width, child.height)
                readback = observed[node.node_id]
                logical_error, physical_error = pixel_space.error(
                    Rect(*expected),
                    Rect(*(readback[axis] for axis in ("x", "y", "width", "height"))),
                )
                error = max(error, logical_error)
                physical_error_maximum = max(physical_error_maximum, physical_error)
            if error > 1.0 or physical_error_maximum > pixel_space.allowed_physical_error:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Tk native placement exceeds SFLE's 1px tolerance.")
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Stale semantic invalidation during native readback.",
                )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale generation during native readback.")
        except BaseException:
            restore_scroll_hosts(scroll_before)
            mixed_grid.restore(mixed_before)
            for node_id, old_wrap in previous_wraps.items():
                if widgets[node_id].winfo_exists():
                    widgets[node_id].configure(wraplength=old_wrap)
            for node_id, old in before.items():
                widget = widgets[node_id]
                if not widget.winfo_exists():
                    continue
                if old:
                    if node_id in external:
                        rect = Rect(*(float(old[axis]) for axis in (
                            "x", "y", "width", "height",
                        )))
                        external[node_id].apply(widget, rect)
                    else:
                        widget.place(**old)
                else:
                    widget.place_forget()
            raise
        renderer._sfle_physical_commit_error = physical_error_maximum
        renderer.sfle_result = replace(result, geometry_commit_error=error)
        if mixed_receipts:
            renderer.grid_result = mixed_receipts[-1]
        native_round.publish()
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
