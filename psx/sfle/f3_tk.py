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
from psx.sfle.tk_measurement import TkMeasurementSource
from psx.sfle.model import LayoutConstraints, AvailableSize
from psx.sfle.f3_width_remeasurement import (
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
        prepared = prepare_f3_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        widgets = {node_id: handles[id(node)].widget for node_id, node in prepared.identities}
        external = {
            node_id: port
            for node_id, source in prepared.identities
            if (port := external_port_for(source, renderer)) is not None
        }
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
            elif widget.master is not widgets[node.parent_id]:
                raise SFLEError(DiagnosticCode.INVALID_TREE,
                                "Tk widget master must match SFLE node parent.", node.node_id)

        leaf_widgets = {
            node_id: widgets[node_id]
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST and source.type != "Flex"
            and node_id not in external
        }
        # Let Tcl calculate requested sizes without giving it layout authority.
        renderer.root.update_idletasks()
        textarea_ids = frozenset(
            node_id for node_id, vnode in prepared.identities
            if vnode.kind is NodeKind.HOST and vnode.type == "TextArea"
        )
        source = TkMeasurementSource(leaf_widgets, textarea_ids=textarea_ids)
        readings = []
        for node_id in leaf_widgets:
            readings.append(source.measure(MeasurementRequest(
                node_id, renderer._sfle_constraints, generation, generation,
            )))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Tk measurement.")
        for node_id, port in external.items():
            readings.append(measure_external(
                port, widgets[node_id], renderer._sfle_constraints,
                node_id, generation,
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale external tk measurement.")
        snapshot = replace(prepared.snapshot, measurements=tuple(readings))
        automatic = auto_height_measurement_ids(snapshot)
        dependent = {
            node_id: (lambda width, node_id=node_id: source.measure_width(node_id, width))
            for node_id, vnode in prepared.identities
            if node_id in automatic and vnode.kind is NodeKind.HOST
            and vnode.type in ("Text", "TextArea")
        }
        for node_id, port in external.items():
            if node_id in automatic:
                dependent[node_id] = (
                    lambda width, port=port, node_id=node_id:
                    measure_external(
                        port, widgets[node_id],
                        LayoutConstraints(AvailableSize(width, True), AvailableSize(None, False)),
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
        try:
            # F2 checks signed 1/64px precision before mutating a single child.
            committer(result)
            # Apply the SAME measured content width to actual native text
            # painting, otherwise Tk could show a single-line clipped label
            # even though SFLE correctly reserved multiline block height.
            for node_id in previous_wraps:
                widgets[node_id].configure(
                    wraplength=max(1, round(rectangles[node_id].content.width)),
                )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale Tk geometry commit.")
            renderer.root.update_idletasks()
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
        except BaseException:
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
    finally:
        renderer._sfle_in_commit = False
