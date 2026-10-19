"""Commit measured Cinnamon Block rectangles to mounted headless handles.

A single block root with measured leaf children is the initial certified
normal-flow subset. Native renderers must supply their own measurement ports
and geometry projectors; they cannot reuse this fake native handle model.
"""
from __future__ import annotations

from threading import get_ident

from psx.core.vnode import NodeKind
from .adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from .errors import DiagnosticCode, SFLEError
from .fixed_point import LayoutUnit
from .measured_block_snapshot import compute_measured_block_snapshot
from .model import LayoutInput, LayoutNode, MeasuredBox
from .native_layout_snapshot import path_identity


def is_mounted_block_root(instance: object) -> bool:
    while instance.node.kind is NodeKind.COMPONENT:
        if len(instance.children) != 1:
            return False
        instance = instance.children[0]
    return instance.node.kind is NodeKind.HOST and instance.node.type == "div"


def commit_headless_block(renderer: object, root: object) -> None:
    if get_ident() != renderer._sfle_owner_thread:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Block measurement and commit require the renderer UI thread.")
    if renderer._sfle_in_commit:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Reentrant block geometry commit.")
    if renderer._sfle_measure is None:
        raise SFLEError(DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Block layout requires a native intrinsic measurement port.")
    renderer._sfle_in_commit = True
    try:
        from psx.core.layout_tree import normalize_flex_tree
        components = {}
        handles = {}

        def gather(instance):
            if instance.disposed:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Disposed block layout node.")
            if instance.node.kind is NodeKind.COMPONENT:
                if len(instance.children) != 1:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Component requires one mounted root.")
                components[id(instance.node)] = instance.children[0].node
            else:
                if instance.handle is None:
                    raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing native block handle.")
                handles[id(instance.node)] = instance.handle
            for child in instance.children:
                gather(child)

        gather(root)
        normalized = normalize_flex_tree(root.node, component_roots=components)
        roots = normalized._participating_roots()
        if len(roots) != 1 or roots[0].type != "div":
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Expected one explicit div block root.")
        block = roots[0]
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        epoch = renderer._sfle_measurement_invalidations.epoch
        participants = (block,) + block.effective_children
        nodes = []
        measured = []
        bindings = {}
        for index, item in enumerate(participants):
            identifier = path_identity(item.path)
            bindings[identifier] = handles[id(item.source)]
            nodes.append(LayoutNode(
                identifier,
                path_identity(block.path) if index else None,
                str(item.type), (),
            ))
            if index:
                if item.effective_children:
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Nested block or inline content requires another formatting context.",
                    )
                if item.source.props.keys() & {"layout_width", "layout_height"}:
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_FEATURE,
                        "Explicit native leaf sizing needs a supported Block measurement port.",
                    )
                intrinsic = renderer._sfle_measure(item.source)
                if intrinsic is None:
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Block native leaf did not provide intrinsic measurements.",
                    )
                measured.append(MeasuredBox(
                    identifier, intrinsic, renderer._sfle_constraints, generation,
                ))
        snapshot = LayoutInput(
            1, generation, renderer._sfle_engine_direction()
            if callable(getattr(renderer, "_sfle_engine_direction", None))
            else __import__("psx.sfle.model", fromlist=["WritingDirection"]).WritingDirection.LTR,
            renderer._sfle_constraints, tuple(nodes), tuple(measured),
        )
        result = compute_measured_block_snapshot(snapshot)
        ports = SFLEAdapterPorts(
            current_generation=lambda: renderer._sfle_generation,
            nodes_alive=lambda ids: all(
                key in bindings and not bindings[key].destroyed for key in ids
            ),
            apply_rectangles=lambda _: None,
            read_rectangles=lambda: {
                key: {"x": value.geometry.x, "y": value.geometry.y,
                      "width": value.geometry.width, "height": value.geometry.height}
                for key, value in bindings.items() if value.geometry is not None
            },
        )
        validate_adapter_commit(snapshot, result, ports)
        if epoch != renderer._sfle_measurement_invalidations.epoch:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale block layout invalidation.")
        previous = {key: value.geometry for key, value in bindings.items()}
        try:
            for key, rect in ((name, box.border) for name, box in result.boxes):
                if any(LayoutUnit.from_nearest(getattr(rect, axis)).to_px()
                       != getattr(rect, axis)
                       for axis in ("x", "y", "width", "height")):
                    raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT,
                                    "Block geometry must use 1/64 px layout units.")
                if bindings[key].geometry != rect:
                    bindings[key].geometry = rect
            if epoch != renderer._sfle_measurement_invalidations.epoch:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale block invalidation at commit.")
            if generation != renderer._sfle_generation:
                raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Stale block generation.")
        except BaseException:
            for key, rect in previous.items():
                bindings[key].geometry = rect
            raise
        renderer.sfle_result = result
        renderer._sfle_committed_signatures = None
        renderer._sfle_prior_solver_input = None
        renderer._sfle_prior_solver_result = None
    finally:
        renderer._sfle_in_commit = False
