"""Commit measured Cinnamon Block rectangles to mounted headless handles.

A single block root with measured leaf children is the initial certified
normal-flow subset. Native renderers must supply their own measurement ports
and geometry projectors; they cannot reuse this fake native handle model.
"""
from __future__ import annotations

from threading import get_ident

from psx.core.vnode import NodeKind
from psx.markup.html_aliases import FORMATTING_TAGS
from .adapter_contract import SFLEAdapterPorts, validate_adapter_commit
from .errors import DiagnosticCode, SFLEError
from .fixed_point import LayoutUnit
from .measured_block_snapshot import compute_measured_block_snapshot
from .model import LayoutInput, LayoutNode, MeasuredBox, WritingDirection
from .native_layout_snapshot import path_identity


def is_mounted_block_root(instance: object) -> bool:
    while instance.node.kind is NodeKind.COMPONENT:
        if len(instance.children) != 1:
            return False
        instance = instance.children[0]
    return instance.node.kind is NodeKind.HOST and instance.node.type in FORMATTING_TAGS


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
        if len(roots) != 1 or roots[0].type not in FORMATTING_TAGS:
            raise SFLEError(DiagnosticCode.INVALID_TREE, "Expected one explicit Block/Inline formatting root.")
        block = roots[0]
        generation = renderer._sfle_generation + 1
        renderer._sfle_generation = generation
        epoch = renderer._sfle_measurement_invalidations.epoch
        nodes = []
        measured = []
        bindings = {}

        def visit(item, parent_id):
            identifier = path_identity(item.path)
            if id(item.source) not in handles:
                raise SFLEError(
                    DiagnosticCode.INVALID_TREE,
                    "Flow node does not have a mounted native handle.",
                )
            bindings[identifier] = handles[id(item.source)]
            is_formatting = item.type in FORMATTING_TAGS
            if not is_formatting and item.effective_children:
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Native flow leaf requires an explicit nested formatting adapter.",
                )
            if item.source.props.keys() & {"layout_width", "layout_height"}:
                raise SFLEError(
                    DiagnosticCode.UNSUPPORTED_FEATURE,
                    "Explicit flow dimensions require a supported measurement port.",
                )
            nodes.append(LayoutNode(
                identifier, parent_id, str(item.type),
                (("display", item.source.props["display"]),)
                if is_formatting else (),
            ))
            if is_formatting:
                for child in item.effective_children:
                    visit(child, identifier)
            else:
                intrinsic = renderer._sfle_measure(item.source)
                if intrinsic is None:
                    raise SFLEError(
                        DiagnosticCode.UNSUPPORTED_MEASUREMENT,
                        "Block native leaf did not provide intrinsic measurements.",
                    )
                measured.append(MeasuredBox(
                    identifier, intrinsic, renderer._sfle_constraints, generation,
                ))

        visit(block, None)
        snapshot = LayoutInput(
            1, generation, WritingDirection.LTR,
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
