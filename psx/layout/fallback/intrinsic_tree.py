"""Historical Python-only intrinsic tree API.

Pure leaf adaptation lives in layout.runtime. This compatibility module keeps
explicit imports from psx.layout.fallback pinned to Python's numerical engine.
"""
from __future__ import annotations

from psx.layout.contracts.recursive_tree import IntrinsicLeafStyle
from psx.layout.runtime.recursive_preparation import prepare_measured_leaf_nodes


def compute_measured_leaf_tree(
    nodes, *, measurements, leaves, generation, writing=None,
):
    from psx.layout.contracts.model import WritingDirection
    from psx.layout.fallback.engine import PythonLayoutEngine
    from psx.layout.runtime.recursive_preparation import compute_measured_leaf_tree as compute
    return compute(
        nodes, measurements=measurements, leaves=leaves,
        generation=generation, writing=WritingDirection.LTR if writing is None else writing,
        engine=PythonLayoutEngine(),
    )
