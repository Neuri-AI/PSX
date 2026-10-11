"""F2 closeout point 2: exact positive geometry and negative CSS classification.

Both engines consume identical versioned normalized snapshots. Supported
features require bit-identical 1/64 px rectangles in all four box classes.
Unsupported CSS and malformed style values must have identical accept/reject
verdicts, stable error codes and source node identity. No skip or xfail.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from test_sfle_f2_differential import (
    _python_compute, _rects, _rust_compute, rust_binary,
)


@pytest.mark.parametrize("root_width",(118,176,263,410))
@pytest.mark.parametrize("direction",("row","row-reverse","column","column-reverse"))
@pytest.mark.parametrize("wrap",("nowrap","wrap","wrap-reverse"))
@pytest.mark.parametrize("min_max",("free","minimum","maximum"))
def test_accepted_alpha_flex_style_matrix_is_bit_identical(
    root_width,direction,wrap,min_max,rust_binary,
):
    sizes=(29,38,47)
    children=[]
    for index,size in enumerate(sizes):
        child_style={
            "width":f"{size}px","height":f"{size+4}px",
            "flex_basis":f"{size}px",
            "flex_grow":index%2,"flex_shrink":1+index%2,
            "min_width":"0px","min_height":"0px",
            "layout_padding_left":f"{index+1}px",
        }
        if min_max=="minimum":
            child_style["min_width"]=f"{size+3}px"
        if min_max=="maximum":
            child_style["max_width"]=f"{size-8}px"
        children.append(LayoutNode(
            f"child_{index}","root","Box",tuple(child_style.items()),
        ))
    snapshot=LayoutInput(
        1,100_000+root_width,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(root_width,True),AvailableSize(142,True)),
        (
            LayoutNode("root",None,"Flex",(
                ("direction",direction),("width",f"{root_width}px"),
                ("height","142px"),("wrap",wrap),
                ("row_gap","3px"),("column_gap","5px"),
                ("align_items","flex-start"),
            )),
            *children,
        ),
        (),
    )
    py=_python_compute(snapshot)
    rs=_rust_compute(rust_binary,snapshot)
    assert py["ok"]==rs["ok"],(root_width,direction,wrap,min_max,py.get("error"),rs.get("error"))
    assert py["ok"],(root_width,direction,wrap,min_max,py.get("error"))
    pboxes=_rects(py["result"])
    rboxes=_rects(rs["result"])
    assert list(pboxes)==list(rboxes)==[node.node_id for node in snapshot.nodes]
    for name in pboxes:
        for box_kind in ("content","padding","border","margin"):
            for axis in ("x","y","width","height"):
                p=pboxes[name][box_kind][axis]
                r=rboxes[name][box_kind][axis]
                assert p==r,(
                    "point2 positive parity",root_width,direction,wrap,
                    min_max,name,box_kind,axis,p,r,
                )
                assert p*64==int(p*64),("Non-LayoutUnit geometry",name,box_kind,axis,p)


# These are style-schema boundary cases, not requests to broaden CSS support.
# In particular, null enum values must not silently select the default.
INVALID_STYLE_CASES=(
    ("order",2147483648,"SFLE_INVALID_LENGTH"),
    ("order",-2147483649,"SFLE_INVALID_LENGTH"),
    ("direction","diagonal","SFLE_UNSUPPORTED_FEATURE"),
    ("wrap","balanced","SFLE_UNSUPPORTED_FEATURE"),
    ("align_items","last baseline","SFLE_UNSUPPORTED_FEATURE"),
    ("align_self","middle","SFLE_UNSUPPORTED_FEATURE"),
    ("justify_content","safe center","SFLE_UNSUPPORTED_FEATURE"),
    ("align_content","baseline","SFLE_UNSUPPORTED_FEATURE"),
    ("overflow","overlay","SFLE_UNSUPPORTED_FEATURE"),
    ("width","inherit","SFLE_UNSUPPORTED_FEATURE"),
    ("layout_padding_left","var(--gap)","SFLE_UNSUPPORTED_FEATURE"),
    ("flex_grow",-1,"SFLE_INVALID_LENGTH"),
    ("flex_shrink",-0.5,"SFLE_INVALID_LENGTH"),
    ("scroll_container","false","SFLE_INVALID_LENGTH"),
    ("replaced","true","SFLE_INVALID_LENGTH"),
    ("aspect_ratio",0,"SFLE_INVALID_LENGTH"),
    ("aspect_ratio",-1,"SFLE_INVALID_LENGTH"),
    ("flex_basis","calc(100% - 5px)","SFLE_UNSUPPORTED_FEATURE"),
)


@pytest.mark.parametrize("property_name,bad_value,code",INVALID_STYLE_CASES)
@pytest.mark.parametrize("seed",(17,311))
def test_malformed_style_is_never_accepted_by_only_one_backend(
    property_name,bad_value,code,seed,rust_binary,
):
    original=LayoutInput(
        1,seed,WritingDirection.LTR,
        LayoutConstraints(AvailableSize(200,True),AvailableSize(90,True)),
        (
            LayoutNode(f"r_{seed}",None,"Flex",(
                ("direction","row"),("width","200px"),
                ("height","90px"),("align_items","flex-start"),
            )),
            LayoutNode(f"n_{seed}",f"r_{seed}","Box",(
                ("width","30px"),("height","20px"),
                ("flex_basis","30px"),("min_width","0px"),
            )),
        ),(),
    )
    node=original.nodes[1]
    style=dict(node.style)
    style[property_name]=bad_value
    snapshot=replace(original,nodes=(original.nodes[0],replace(node,style=tuple(style.items()))))
    python=_python_compute(snapshot)
    rust=_rust_compute(rust_binary,snapshot)
    for backend,result in (("python",python),("rust",rust)):
        assert result["ok"] is False,(
            "Unsupported/malformed style silently accepted",backend,property_name,
            bad_value,result,
        )
        assert result["error"]["code"]==code,(backend,property_name,bad_value,result)
        assert result["error"]["node_id"]==node.node_id,(
            backend,property_name,bad_value,result,
        )
    assert (python["error"]["code"],python["error"]["node_id"])==(
        rust["error"]["code"],rust["error"]["node_id"]
    )
