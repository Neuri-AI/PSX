"""Point-3 native projection: bounded signed raw geometry and 1px roundtrip.

The independent native oracles use the signed 1/64px contract, not a second
CSS solver. Oversized or off-grid data fails before any partial UI mutation.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.fixed_point import I32_MAX, I32_MIN, LayoutUnit, SCALE
from psx.sfle.model import BoxRect, LayoutResult, Rect
from psx.sfle.native_geometry import GeometryBackend, NativeGeometryCommitter


MAX=I32_MAX/SCALE
MIN=I32_MIN/SCALE


def _make_result(root:Rect, wrapper:Rect, child:Rect) -> LayoutResult:
    boxes=tuple((name,BoxRect(rect,rect,rect,rect)) for name,rect in (
        ("root",root),("wrapper",wrapper),("child",child),
    ))
    return LayoutResult(1,9,boxes)


class _Widget:
    def __init__(self):
        self.geometry=None
        self.pos=None
        self.size=None

    def setGeometry(self,*coords):
        self.geometry=coords

    def place(self,**coords):
        self.geometry=tuple(coords[key] for key in ("x","y","width","height"))


def _expected(child:Rect,parent:Rect,backend:GeometryBackend):
    x=(LayoutUnit.from_nearest(child.x)-LayoutUnit.from_nearest(parent.x)).to_px()
    y=(LayoutUnit.from_nearest(child.y)-LayoutUnit.from_nearest(parent.y)).to_px()
    if backend==GeometryBackend.KIVY:
        y=(LayoutUnit.from_nearest(parent.height)-LayoutUnit.from_nearest(y)
           -LayoutUnit.from_nearest(child.height)).to_px()
    return (x,y,child.width,child.height)


@pytest.mark.parametrize("backend",tuple(GeometryBackend))
@pytest.mark.parametrize("positions",(
    # Realistic deeply nested fractional CSS layout.
    (Rect(12.125,6.375,330.125,220.25),
     Rect(24.625,19.875,190.375,175.0),
     Rect(31.6875,35.375,48.28125,21.578125)),
    # Extremal signed root/descendant differences must saturate, not wrap.
    (Rect(MIN,MIN,MAX,MAX),
     Rect(MAX,MAX,80.015625,70.015625),
     Rect(MIN,MIN,20.125,18.125)),
    (Rect(MAX,MAX,MAX,MAX),
     Rect(MIN,MIN,80.015625,70.015625),
     Rect(MAX,MAX,20.125,18.125)),
))
def test_three_native_adapters_project_signed_nested_geometry_within_one_pixel(
    backend,positions,
):
    result=_make_result(*positions)
    nodes=(
        SimpleNamespace(node_id="root",parent_id=None),
        SimpleNamespace(node_id="wrapper",parent_id="root"),
        SimpleNamespace(node_id="child",parent_id="wrapper"),
    )
    widgets={"wrapper":_Widget(),"child":_Widget()}
    NativeGeometryCommitter(backend,nodes,widgets)(result)
    for node,parent in (("wrapper","root"),("child","wrapper")):
        actual=(widgets[node].geometry if backend!=GeometryBackend.KIVY
                else (*widgets[node].pos,*widgets[node].size))
        expected=_expected(dict(result.boxes)[node].border,
                           dict(result.boxes)[parent].border,backend)
        assert actual is not None
        for axis,e,a in zip(("x","y","width","height"),expected,actual):
            assert abs(e-a)<=1.0,(
                "Native projected readback exceeds the 1px budget",
                backend,node,axis,e,a,
            )
        if backend==GeometryBackend.KIVY:
            assert actual==expected


@pytest.mark.parametrize("backend",tuple(GeometryBackend))
@pytest.mark.parametrize("bad",(
    Rect(MAX+1/SCALE,0,10,10),  # outside signed raw bound
    Rect(0,0,MAX+1/SCALE,10),  # size must not escape signed raw bound
    Rect(0.0078125,0,10,10),  # violates quantized 1/64px grid
    Rect(0,0,10.1,10),        # unsnapped native width
))
def test_invalid_result_rejected_atomically_before_any_widget_mutation(
    backend,bad,
):
    result=_make_result(Rect(0,0,100,100),Rect(10,10,60,60),bad)
    nodes=(
        SimpleNamespace(node_id="root",parent_id=None),
        SimpleNamespace(node_id="wrapper",parent_id="root"),
        SimpleNamespace(node_id="child",parent_id="wrapper"),
    )
    widgets={"wrapper":_Widget(),"child":_Widget()}
    with pytest.raises(SFLEError) as exc:
        NativeGeometryCommitter(backend,nodes,widgets)(result)
    assert exc.value.code==DiagnosticCode.INVALID_SNAPSHOT
    assert exc.value.node_id=="child"
    for widget in widgets.values():
        assert widget.geometry is None
        assert widget.pos is None
        assert widget.size is None


@pytest.mark.parametrize("raw",(
    I32_MIN,I32_MIN+1,-2**20,-1,0,1,2**20,I32_MAX-1,I32_MAX,
))
@pytest.mark.parametrize("multiplier,divisor",(
    (I32_MAX,1),(I32_MAX,I32_MAX),(-1,1),(I32_MIN,-1),
))
def test_python_layout_unit_fused_mul_div_uses_widened_signed_raw(
    raw,multiplier,divisor,
):
    a=LayoutUnit.from_raw(raw)
    m=LayoutUnit.from_raw(multiplier)
    d=LayoutUnit.from_raw(divisor)
    numerator=raw*multiplier
    quotient=abs(numerator)//abs(divisor)
    if (numerator<0)!=(divisor<0):
        quotient=-quotient
    expected=max(I32_MIN,min(I32_MAX,quotient))
    assert a.mul_div(m,d).raw==expected
