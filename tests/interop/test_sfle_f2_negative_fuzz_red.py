"""A3 strict negative fuzz: known unsupported CSS dependency graphs.

Generated unlisted node identities, changed lengths and unrelated siblings
exercise both Python and Rust. This must not reject CSS-defined valid
indefinite percentage resolutions outside these known unsupported classes.
"""

from dataclasses import replace
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sfle"))
from test_f2_acceptance_contract_red import case_snapshot  # noqa: E402
from test_sfle_f2_differential import _python_compute, _rust_compute, rust_binary  # noqa: E402,F401
from psx.sfle.lengths import Length, LengthKind  # noqa: E402
from psx.sfle.model import LayoutNode  # noqa: E402

UNSUPPORTED = ("N01", "N02", "N03", "N04", "C99", "N06", "N07", "N08")
SEEDS = tuple(0xABF200 + index * 313 for index in range(20))


def mutated_snapshot(case_id: str, seed: int):
    """Preserve graph class while eliminating fixed corpus IDs and fractions."""
    rnd = random.Random(seed)
    base = case_snapshot(case_id)
    id_map = {node.node_id: f"node_{seed:x}_{index}_{rnd.randrange(100000)}"
              for index, node in enumerate(base.nodes)}
    nodes = []
    for node in base.nodes:
        varied = []
        for key, value in node.style:
            if isinstance(value, Length) and value.kind == LengthKind.PERCENT:
                value = Length.percent(rnd.randint(5, 95) / 100)
            elif isinstance(value, Length) and value.kind == LengthKind.PX and value.value:
                value = Length.px(value.value + rnd.randint(0, 5))
            varied.append((key, value))
        nodes.append(replace(node, node_id=id_map[node.node_id],
                             parent_id=id_map[node.parent_id] if node.parent_id else None,
                             style=tuple(varied)))
    if seed & 1:
        root_id = nodes[0].node_id
        nodes.insert(1, LayoutNode(f"unrelated_{seed:x}", root_id, "Box", (
            ("width", Length.px(13)), ("height", Length.px(9)),
        )))
    expected_node = {"C99": "a"}.get(case_id, "child")
    return replace(base, generation=seed, nodes=tuple(nodes), measurements=()), id_map[expected_node]


@pytest.mark.parametrize("case_id", UNSUPPORTED)
@pytest.mark.parametrize("seed", SEEDS)
def test_unlisted_negative_graphs_have_identical_fail_closed_diagnostics(case_id, seed, rust_binary):
    snapshot, expected_node = mutated_snapshot(case_id, seed)
    python = _python_compute(snapshot)
    rust = _rust_compute(rust_binary, snapshot)
    for backend, response in (("python", python), ("rust", rust)):
        assert response["ok"] is False, f"{backend} guessed geometry for {case_id}/{seed:x}"
        assert response["error"]["code"] == "SFLE_UNSUPPORTED_FEATURE", (backend, response)
        assert response["error"]["node_id"] == expected_node, (backend, response)
    assert python["error"]["code"] == rust["error"]["code"]
    assert python["error"]["node_id"] == rust["error"]["node_id"]
