"""Logical layout index retained across native-only viewport transactions."""
from psx.core.structural_binding import layout_binding
from psx.core.vnode import NodeKind
from psx.layout.contracts.errors import DiagnosticCode, SFLEError
from psx.layout.projection.native_structural_snapshot_reuse import mounted_structural_token


def mounted_layout_index(renderer, root):
    owner = getattr(renderer, "_psx_reconciler", None)
    revision = getattr(owner, "_logical_revision", 0)
    epoch = renderer._sfle_measurement_invalidations.epoch
    cached = getattr(renderer, "_psx_mounted_layout_index", None)
    if root.disposed:
        raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed logical layout root")
    if (owner is not None and cached is not None and cached[0] is root
            and cached[1] == (revision, epoch)):
        return cached[2:]
    if owner is not None:
        from psx.core.structural_binding import promote_required_native_subtrees
        promote_required_native_subtrees(renderer, root)
    components, handles, stamp = {}, {}, []

    def visit(instance):
        if instance.disposed:
            raise SFLEError(DiagnosticCode.INVALID_SNAPSHOT, "Disposed logical layout node")
        if instance.node.kind is NodeKind.COMPONENT:
            if len(instance.children) != 1:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Component needs one layout root")
            components[id(instance.node)] = instance.children[0].node
        else:
            binding = layout_binding(instance)
            if binding is None or id(instance.node) in handles:
                raise SFLEError(DiagnosticCode.INVALID_TREE, "Missing or duplicated layout binding")
            handles[id(instance.node)] = binding
        stamp.append(mounted_structural_token(instance))
        for child in instance.children:
            visit(child)

    visit(root)
    result = (components, handles, tuple(stamp))
    renderer._psx_mounted_layout_index = (root, (revision, epoch), *result)
    return result
