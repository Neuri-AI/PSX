"""F2 unknown-*class* matrix, not rebrands of N01-N08.

Reject unsupported CSS property families, values and expression syntax with
the exact SAME node identity + diagnostic in Rust and Python. Positive CSS
indefinite-percentage fixtures are checked separately to catch over-rejection.
"""
from dataclasses import replace
import random
import pytest

from test_sfle_f2_differential import (
    _python_compute, _rust_compute, case_snapshot, rust_binary,
)
from psx.sfle.model import LayoutNode

UNSUPPORTED_PROPERTY_FAMILIES = (
    ("grid", "grid_template_columns", "repeat(2,1fr)"),
    ("positioning", "position", "absolute"),
    ("writing-modes", "writing_mode", "vertical-rl"),
    ("sizing", "box_sizing", "border-box"),
    ("transforms", "transform", "translateX(5px)"),
    ("containment", "contain", "size"),
    ("floats", "float", "left"),
    ("shorthand", "flex_flow", "row wrap"),
    ("independent-gaps", "gap", "8px"),
    ("inset", "inset_inline_start", "2px"),
)

UNSUPPORTED_ENUMS = (
    ("direction", "vertical"),
    ("wrap", "wrap-balance"),
    ("justify_content", "safe center"),
    ("align_items", "last baseline"),
    ("align_content", "baseline"),
    ("overflow", "overlay"),
)

UNSUPPORTED_EXPRESSIONS = (
    ("width", "calc(20px + 5%)"),
    ("flex_basis", "fit-content(20px)"),
    ("layout_padding_left", "var(--gap)"),
    ("column_gap", "1vw"),
)
SEEDS = (0xC5509, 0xC551A, 0xC551B, 0xC551C)


def _graph(property_name, value, seed):
    original=case_snapshot("A02")
    rnd=random.Random(seed)
    id_map={node.node_id:f"f2_{seed:x}_{rnd.randrange(100000)}_{i}"
            for i,node in enumerate(original.nodes)}
    nodes=[]
    # Child-scope rejections exercise stable per-node diagnostics even when
    # the parent is auto-sized. Existing properties are replaced, not duplicated.
    for node in original.nodes:
        style=dict(node.style)
        if node.node_id == "child":
            style[property_name]=value
        nodes.append(replace(node,node_id=id_map[node.node_id],
                    parent_id=id_map[node.parent_id] if node.parent_id else None,
                    style=tuple(style.items())))
    # The source fixture's original measured node ID must not leak into
    # renamed graphs; property classification precedes any UI measurement.
    return replace(original, generation=seed,nodes=tuple(nodes),measurements=()), id_map["child"]


@pytest.mark.parametrize("case",UNSUPPORTED_PROPERTY_FAMILIES,ids=lambda row:row[0])
@pytest.mark.parametrize("seed",SEEDS)
def test_unimplemented_css_property_classes_fail_closed(case,seed,rust_binary):
    _family,name,value=case
    snapshot,expected=_graph(name,value,seed)
    for backend,response in (
        ("python",_python_compute(snapshot)),
        ("rust",_rust_compute(rust_binary,snapshot)),
    ):
        assert not response["ok"],f"{backend} silently accepted {case}"
        assert response["error"]["code"]=="SFLE_UNSUPPORTED_FEATURE"
        assert response["error"]["node_id"]==expected


@pytest.mark.parametrize("name,value",UNSUPPORTED_ENUMS+UNSUPPORTED_EXPRESSIONS)
@pytest.mark.parametrize("seed",SEEDS)
def test_unimplemented_css_values_and_expressions_fail_closed(name,value,seed,rust_binary):
    snapshot,expected=_graph(name,value,seed)
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    for backend,response in (("python",py),("rust",rs)):
        assert not response["ok"],f"{backend} silently accepted {name}={value}"
        assert response["error"]["code"]=="SFLE_UNSUPPORTED_FEATURE",response
        assert response["error"]["node_id"]==expected,response


@pytest.mark.parametrize("case_id",("A02","A03","C04","C05","C06","N05"))
def test_valid_indefinite_or_cyclic_css_is_not_blanket_rejected(case_id,rust_binary):
    snapshot=case_snapshot(case_id)
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    assert py["ok"],(case_id,py.get("error"))
    assert rs["ok"],(case_id,rs.get("error"))
    assert tuple(n.node_id for n in snapshot.nodes)==tuple(
        node_id for node_id,_ in py["result"].boxes
    )
    assert tuple(n.node_id for n in snapshot.nodes)==tuple(
        item["node_id"] for item in rs["result"]["boxes"]
    )
