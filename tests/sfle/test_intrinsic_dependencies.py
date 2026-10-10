import pytest
from psx.sfle.errors import SFLECapabilityError, SFLEError
from psx.sfle.intrinsic_dependencies import LeafAutoSizing, collect_leaf_intrinsic_suggestions
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection, IntrinsicSizes, MeasuredBox
from psx.sfle.sizing import ResolutionKind
from psx.sfle.used_size_tree import UsedSizeTree

def size(w, h):
    return LayoutConstraints(AvailableSize(w, w is not None), AvailableSize(h, h is not None))
METRICS = IntrinsicSizes(10,30,10,60,30,40)

def fixture(measure=True):
    c=size(None,None)
    return LayoutInput(1,8,WritingDirection.LTR,size(200,100),(
        LayoutNode("root",None,"Flex",()), LayoutNode("leaf","root","Text",())
    ),(MeasuredBox("leaf",METRICS,c,0),) if measure else ()), UsedSizeTree(8,(
        ("root",size(200,100)),("leaf",c)
    ),("leaf",))

def test_auto_leaf_from_intrinsic_snapshot():
    snapshot, used=fixture()
    result=collect_leaf_intrinsic_suggestions(snapshot,used,declarations=(
        LeafAutoSizing("leaf",ResolutionKind.AUTO,ResolutionKind.AUTO),
    ))
    assert len(result) == 1
    assert result[0].node_id == "leaf"
    assert (result[0].preferred_width, result[0].preferred_height) == (30,40)
    # The input used tree remains indefinite: suggestions are not final CSS sizes.
    assert used.deferred == ("leaf",)

def test_missing_measurement_is_not_zero():
    snapshot,used=fixture(False)
    with pytest.raises(SFLEError):
        collect_leaf_intrinsic_suggestions(snapshot,used,declarations=(
            LeafAutoSizing("leaf",ResolutionKind.AUTO,ResolutionKind.AUTO),
        ))

def test_percent_cycle_not_misclassified_auto():
    snapshot,used=fixture()
    with pytest.raises(SFLECapabilityError):
        collect_leaf_intrinsic_suggestions(snapshot,used,declarations=(
            LeafAutoSizing("leaf",ResolutionKind.UNRESOLVED_PERCENT,ResolutionKind.AUTO),
        ))

def test_auto_container_rejected():
    snapshot,used=fixture()
    # An already definite root does not need an intrinsic AUTO resolution.
    # To test unsupported container sizing, its width must actually be indefinite.
    root_auto = UsedSizeTree(used.generation, (
        ("root",size(None,100)),("leaf",size(None,None)),
    ),("root","leaf"))
    with pytest.raises(SFLECapabilityError):
        collect_leaf_intrinsic_suggestions(snapshot,root_auto,declarations=(
            LeafAutoSizing("root",ResolutionKind.AUTO,ResolutionKind.USED),
        ))

def test_stale_leaf_measurement_revision_rejected():
    snapshot, used = fixture()
    with pytest.raises(SFLEError):
        collect_leaf_intrinsic_suggestions(snapshot,used,declarations=(
            LeafAutoSizing("leaf",ResolutionKind.AUTO,ResolutionKind.AUTO),
        ),revisions=(("leaf",1),))

def test_stale_leaf_measurement_constraints_rejected():
    snapshot, used = fixture()
    m = MeasuredBox("leaf",METRICS,size(50,None),0)
    stale = LayoutInput(1,8,WritingDirection.LTR,size(200,100),snapshot.nodes,(m,))
    with pytest.raises(SFLEError):
        collect_leaf_intrinsic_suggestions(stale,used,declarations=(
            LeafAutoSizing("leaf",ResolutionKind.AUTO,ResolutionKind.AUTO),
        ))
