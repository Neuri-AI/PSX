"""Every C01-C06 canonical tree must execute real Python compute, not JSON schema checks."""
import pytest
from psx.sfle.engine import PythonLayoutEngine
from test_f2_acceptance_contract_red import case_snapshot, _ACCEPTANCE

@pytest.mark.parametrize("case_id", [f"C{i:02d}" for i in range(1,7)])
def test_cycle_allowlist_numeric_runtime(case_id):
    """Compare exact accepted CSS result; unsupported engine semantics stay RED."""
    result=PythonLayoutEngine().compute(case_snapshot(case_id))
    boxes=dict(result.boxes)
    expected=_ACCEPTANCE[case_id]
    for key,value in expected.items():
        if not isinstance(value,(int,float)) or isinstance(value,bool):
            continue
        if key in ("intrinsic_gap","used_gap"):
            continue  # Verified in phase-specific intrinsic/used gap tests.
        node_id,axis=key.split(".")
        if axis=="padding_top":
            actual=boxes[node_id].content.y-boxes[node_id].padding.y
        else:
            actual=getattr(boxes[node_id].content,axis)
        assert actual==pytest.approx(value,abs=0.01),f"{case_id} {key}: {actual} != {value}"
