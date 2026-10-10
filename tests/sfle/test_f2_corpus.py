"""The canonical F2 fixture format is shared by Python, Rust and Chromium.

No implementation-specific expected values are duplicated in this test.
"""
import json
from pathlib import Path
import pytest

PATH = Path(__file__).parent / "fixtures" / "f2_alpha_acceptance.json"


def corpus():
    return json.loads(PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", corpus(), ids=lambda case: case["id"])
def test_f2_corpus_has_valid_unique_preorder_tree(case):
    ids = set()
    for node in case["nodes"]:
        assert node["node_id"] not in ids
        assert node["parent_id"] is None or node["parent_id"] in ids
        ids.add(node["node_id"])
    assert all(name in case for name in ("expected", "measurements", "viewport", "verification"))
    assert set(case["verification"]) == {"python", "rust", "chromium"}


def test_f2_corpus_complete_case_inventory():
    assert {case["id"] for case in corpus()} == {
        *(f"A{i:02d}" for i in range(1, 8)),
        *(f"C{i:02d}" for i in range(1, 7)),
        "C99", "A08", "A09-LTR", "A09-RTL", "A10",
    }
