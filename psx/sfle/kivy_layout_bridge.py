"""Native SFLE mounted Kivy geometry bridge over SFLE's immutable output.

Everything stays on the owning Kivy Clock/UI thread. Intrinsic metrics
are read from actual label textures. The pre-existing F2 committer
transforms each absolute top-left SFLE border rectangle into the *actual*
Kivy parent's bottom-left frame: parent_h - local_y - child_h.
No BoxLayout, size_hint, alternate CSS solver or rewritten SFLE boxes.
"""
from __future__ import annotations

from psx.markup.html_aliases import FORMATTING_TAGS

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
from psx.sfle.native_component_capabilities import native_leaf_needs_measurement
from psx.sfle.fixed_point import LayoutUnit
from psx.sfle.kivy_measurement import KivyMeasurementSource
from psx.sfle.model import LayoutConstraints, AvailableSize
from psx.sfle.width_dependent_intrinsic_measurement import (
    compute_width_dependent, auto_height_measurement_ids,
    seed_unconstrained_width_measurements,
)
from psx.sfle.margin_tree import MarginTreeNode
from psx.sfle.measurement_plan import MeasurementRequest
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter
from psx.sfle.native_pixel_space import DevicePixelSpace
from psx.sfle.model import Rect

if TYPE_CHECKING:
    from psx.core.instance import MountedInstance
    from psx.renderers.kivy.kivy import KivyRenderer


def commit_kivy_sfle(renderer: "KivyRenderer", root: "MountedInstance") -> None:
    """Measure, compute, validate, project, apply and read back live widgets."""
    if renderer._sfle_constraints is None:
        return
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "Kivy SFLE geometry requires the renderer's Clock/UI thread.",
        )
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                        "Re-entrant Kivy SFLE commit.")
    renderer._sfle_in_commit = True
    try:
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        invalidation_epoch = renderer._sfle_measurement_invalidations.epoch
        component_roots: dict[int, object] = {}
        handles: dict[int, object] = {}

        def gather(instance: "MountedInstance") -> None:
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Disposed Kivy layout node.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE,
                                    "Function component needs one mounted root.")
                component_roots[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None or id(instance.node) in handles:
                    raise SFLEError(DiagnosticCode.INVALID_TREE,
                                    "Missing or duplicated Kivy layout handle.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(
            root.node, component_roots=component_roots)
        mixed_grid = MountedMixedGrid(
            renderer, normalized, handles, GridCommitBackend.KIVY, generation,
        )
        prepared = prepare_native_layout_snapshot(
            normalized, renderer._sfle_constraints, generation=generation,
        )
        bindings = {node_id: handles[id(source)]
                    for node_id, source in prepared.identities}
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

        for node in prepared.snapshot.nodes:
            if node.parent_id is None:
                if bindings[node.node_id].widget is not renderer._root:
                    raise SFLEError(DiagnosticCode.INVALID_TREE,
                                    "Kivy SFLE root does not match host.")
                continue
            child = bindings[node.node_id].widget
            parent = bindings[node.parent_id].widget
            owner = (
                parent._psx_content if getattr(parent, "_psx_sfle_scroll", False)
                else parent
            )
            if child.parent is not owner:
                raise SFLEError(
                    DiagnosticCode.INVALID_TREE, "Actual Kivy parent differs from SFLE tree.", node.node_id,
                )
            if tuple(child.size_hint) != (None, None) or child.pos_hint:
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Kivy size_hint/pos_hint may not override SFLE geometry.", node.node_id,
                )

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
            node_id: bindings[node_id].widget
            for node_id, source in prepared.identities
            if source.kind is NodeKind.HOST
            and source.type not in ("Flex", "Box", "RadioGroup", "Scroll", "Grid")
            and source.type not in FORMATTING_TAGS
            and not (source.type == "Divider" and source.children)
            and node_id not in external
            and native_leaf_needs_measurement(source, backend="kivy")
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
        source = KivyMeasurementSource(
            leaf_widgets, textarea_ids=textarea_ids, image_ids=image_ids,
            spacer_ids=spacer_ids, divider_nodes=divider_nodes,
        )
        readings = []
        native_round = renderer._sfle_native_intrinsic_cache.begin(
            invalidate_all=renderer._sfle_measurement_invalidations.invalidate_all,
            dirty_widgets=frozenset(renderer._sfle_measurement_invalidations.dirty_widgets))
        declared_props = {node_id: dict(vnode.props)
                          for node_id, vnode in prepared.identities}
        for node_id, widget in leaf_widgets.items():
            # Kivy computes texture_size lazily; force only intrinsic texture
            # update, never a parent/BoxLayout placement pass.
            refresh = getattr(widget, "texture_update", None)
            if (bindings[node_id].node_type == "Text"
                    and hasattr(widget, "text_size")):
                original_text_size = widget.text_size
                try:
                    widget.text_size = (None, None)
                    if callable(refresh):
                        refresh()
                    readings.append(native_round.read(
                        widget=widget, props=declared_props[node_id],
                        constraints=renderer._sfle_constraints,
                        node_id=node_id, generation=generation,
                        measure=lambda node_id=node_id: source.measure(MeasurementRequest(
                            node_id, renderer._sfle_constraints, generation, generation)),
                    ))
                finally:
                    widget.text_size = original_text_size
                    if callable(refresh):
                        refresh()
                if renderer._sfle_generation != generation:
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Kivy measurement became stale.")
                continue
            if callable(refresh):
                refresh()
            readings.append(native_round.read(
                widget=widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda node_id=node_id: source.measure(MeasurementRequest(
                    node_id, renderer._sfle_constraints, generation, generation)),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Kivy measurement became stale.")
        for node_id, port in external.items():
            readings.append(native_round.read(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints,
                node_id=node_id, generation=generation,
                measure=lambda port=port, node_id=node_id: measure_external(
                    port, bindings[node_id].widget,
                    renderer._sfle_constraints, node_id, generation),
            ))
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Stale external kivy measurement.")
        readings.extend(mixed_grid.seed_measurements())
        # Consume canonical item box lengths after Kivy's real intrinsic readings;
        # preserve existing widget ownership, width dependencies and Grid path.
        snapshot = replace(prepared.css_geometry_snapshot(
            pixel_scale=getattr(renderer, "_psx_css_pixel_scale", 1.0)
        ), measurements=tuple(readings))
        automatic = auto_height_measurement_ids(snapshot)
        dependent = {
            node_id: (lambda width, node_id=node_id: native_round.read_width(
                widget=bindings[node_id].widget, props=declared_props[node_id],
                constraints=renderer._sfle_constraints, width=width,
                measure=lambda: source.measure_width(node_id, width),
            ))
            for node_id, vnode in prepared.identities
            if node_id in automatic and vnode.kind is NodeKind.HOST
            and vnode.type in ("Text", "TextArea", "Input", "Checkbox", "ProgressBar")
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
                            LayoutConstraints(AvailableSize(
                                width, True), AvailableSize(None, False)),
                            node_id, generation,
                        ).intrinsic,
                    )
                )
        dependent.update(mixed_grid.width_dependencies())
        snapshot = seed_unconstrained_width_measurements(
            snapshot, frozenset(leaf_widgets) | frozenset(dependent))
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
                widget = handle if "kivy" == "tk" else handle.widget
                rect = read_external(port, widget, node_id)
                return dict(x=rect.x, y=rect.y, width=rect.width, height=rect.height)
            widget = handle.widget
            return dict(x=float(widget.x), y=float(widget.y),
                        width=float(widget.width), height=float(widget.height))

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
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Kivy SFLE computation became stale.")

        pixel_space = DevicePixelSpace.from_widget("kivy", renderer._root)
        boxes = dict(result.boxes)
        root_id = snapshot.nodes[0].node_id
        root_rect = boxes[root_id].border
        host = bindings[root_id].widget
        # The native viewport stays fixed; a semantic flow root may have
        # intrinsic content height independently of that viewport.
        semantic_root = dict(prepared.identities)[root_id].type in FORMATTING_TAGS
        if not semantic_root and any(abs(got - expected) > 1.0 for got, expected in (
            (host.width, root_rect.width), (host.height, root_rect.height),
        )):
            raise SFLEError(
                DiagnosticCode.LAYOUT_CONSTRAINT,
                f"Kivy root host dimensions must match SFLE root; "
                f"host=({host.width},{host.height}), "
                f"SFLE=({root_rect.width},{root_rect.height}).",
                root_id,
            )
        nodes = tuple(
            MarginTreeNode(node.node_id, node.parent_id, 0, 0)
            for node in snapshot.nodes
        )
        committer = NativeGeometryCommitter(
            GeometryBackend.KIVY, nodes,
            {node_id: handle.widget for node_id, handle in bindings.items()},
            external_ports=external,
            skip_unchanged=True,
        )
        before = {
            node_id: (tuple(handle.widget.pos), tuple(handle.widget.size))
            for node_id, handle in bindings.items() if node_id != root_id
        }
        previous_text_sizes = {
            node_id: bindings[node_id].widget.text_size
            for node_id in dependent if node_id not in external
            and hasattr(bindings[node_id].widget, "text_size")
        }
        from psx.sfle.native_scroll_transaction import capture_scroll_hosts, restore_scroll_hosts
        scroll_before = capture_scroll_hosts("kivy", bindings)
        mixed_before = mixed_grid.snapshot()
        paint_rect = getattr(host, "_psx_css_paint_rect", None) if semantic_root else None
        paint_before = ((tuple(paint_rect.pos), tuple(paint_rect.size))
                        if paint_rect is not None else None)
        native_stroke = getattr(host, "_psx_css_stroke", None) if semantic_root else None
        previous_stroke_rect = (native_stroke[3].rounded_rectangle
                                if native_stroke is not None else None)
        stroke_before = (tuple(previous_stroke_rect)
                         if previous_stroke_rect is not None else None)
        if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                            "Stale semantic invalidation before native geometry.")
        try:
            # F2 already validates the fixed-point grid and applies a pure
            # parent-relative bottom-left transform in precomputed order.
            committer(result)
            if semantic_root:
                # The root native Widget fills Kivy's Window, but its CSS
                # background/border must paint only the semantic border box.
                local_x = host.x + root_rect.x
                local_y = host.y + host.height - root_rect.y - root_rect.height
                if paint_rect is not None:
                    paint_rect.pos = (local_x, local_y)
                    paint_rect.size = (root_rect.width, root_rect.height)
                if native_stroke is not None:
                    from psx.css.native_paint import inset_rounded_border_box
                    native_stroke[3].rounded_rectangle = inset_rounded_border_box(
                        local_x, local_y, root_rect.width, root_rect.height,
                        getattr(host, "_psx_css_semantic_radius", 0),
                        native_stroke[3].width,
                    )
            mixed_receipts = mixed_grid.commit(mixed_plans)
            for node in snapshot.nodes:
                if node.parent_id is not None:
                    parent = bindings[node.parent_id].widget
                    if getattr(parent, "_psx_sfle_scroll", False):
                        from psx.sfle.native_scroll_hosts import (
                            apply_kivy_scroll, binding_from_host,
                        )
                        from psx.sfle.scroll_offsets import ScrollOffset
                        parent_box = boxes[node.parent_id].border
                        child_box = boxes[node.node_id].border
                        binding = binding_from_host(
                            parent._psx_props, parent_box, child_box,
                        )
                        # scroll_y=1 is the top edge in Kivy.
                        from psx.sfle.native_scroll_transaction import prior_scroll_offset
                        previous = prior_scroll_offset(scroll_before, parent)
                        apply_kivy_scroll(parent, binding, previous)
            for node_id, vnode in prepared.identities:
                if vnode.kind is NodeKind.HOST and vnode.type == "Divider" and vnode.children:
                    from psx.renderers.kivy.divider import KivyDividerAdapter
                    widget = bindings[node_id].widget
                    KivyDividerAdapter._redraw(widget, widget._psx_props)
            for node_id in previous_text_sizes:
                widget = bindings[node_id].widget
                widget.text_size = (boxes[node_id].content.width, None)
                widget.texture_update()
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Stale semantic invalidation after native geometry.")
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Stale Kivy geometry commit.")
            observed = ports.read_rectangles()
            maximum = 0.0
            physical_maximum = 0.0
            scroll_descendants = set()
            for node in snapshot.nodes:
                if node.parent_id is not None and (
                    node.parent_id in scroll_descendants or
                    getattr(bindings[node.parent_id].widget, "_psx_sfle_scroll", False)
                ):
                    scroll_descendants.add(node.node_id)
            for node in snapshot.nodes:
                if node.parent_id is None:
                    continue
                border = boxes[node.node_id].border
                if node.node_id in scroll_descendants:
                    parent = boxes[node.parent_id].border
                    projected_x = (LayoutUnit.from_nearest(border.x) -
                                   LayoutUnit.from_nearest(parent.x)).to_px()
                    local_y = (LayoutUnit.from_nearest(border.y) -
                               LayoutUnit.from_nearest(parent.y)).to_px()
                    parent_widget = bindings[node.parent_id].widget
                    if getattr(parent_widget, "_psx_sfle_scroll", False):
                        parent_height = border.height
                    else:
                        parent_height = parent.height
                    projected_y = (LayoutUnit.from_nearest(parent_height) -
                                   LayoutUnit.from_nearest(local_y) -
                                   LayoutUnit.from_nearest(border.height)).to_px()
                else:
                    root_border = boxes[root_id].border
                    projected_x = (LayoutUnit.from_nearest(border.x) -
                                   LayoutUnit.from_nearest(root_border.x)).to_px() + float(host.x)
                    projected_y = (LayoutUnit.from_nearest(float(host.height))
                                   - (LayoutUnit.from_nearest(border.y) -
                                      LayoutUnit.from_nearest(root_border.y))
                                   - LayoutUnit.from_nearest(border.height)).to_px() + float(host.y)
                actual = observed[node.node_id]
                expected_native = Rect(
                    projected_x, projected_y, border.width, border.height)
                actual_native = Rect(
                    *(actual[axis] for axis in ("x", "y", "width", "height")))
                logical_error, physical_error = pixel_space.error(
                    expected_native, actual_native)
                maximum = max(maximum, logical_error)
                physical_maximum = max(physical_maximum, physical_error)
            if maximum > 1.0 or physical_maximum > pixel_space.allowed_physical_error:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Kivy native readback differs from SFLE projection by more than 1px.",
                )
            if renderer._sfle_measurement_invalidations.epoch != invalidation_epoch:
                raise SFLEError(
                    DiagnosticCode.INVALID_SNAPSHOT,
                    "Stale semantic invalidation during native readback.",
                )
            if renderer._sfle_generation != generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                "Stale generation during native readback.")
        except BaseException:
            if paint_before is not None:
                paint_rect.pos, paint_rect.size = paint_before
            if stroke_before is not None:
                native_stroke[3].rounded_rectangle = stroke_before
            restore_scroll_hosts(scroll_before)
            mixed_grid.restore(mixed_before)
            for node_id, previous in previous_text_sizes.items():
                widget = bindings[node_id].widget
                widget.text_size = previous
                widget.texture_update()
            for node_id, (pos, size) in before.items():
                if node_id in external:
                    external[node_id].apply(bindings[node_id].widget, Rect(
                        pos[0], pos[1], size[0], size[1],
                    ))
                else:
                    bindings[node_id].widget.pos = pos
                    bindings[node_id].widget.size = size
            raise
        renderer._sfle_physical_commit_error = physical_maximum
        renderer.sfle_result = replace(result, geometry_commit_error=maximum)
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
