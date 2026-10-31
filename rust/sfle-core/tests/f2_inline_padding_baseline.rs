//! Inline span padding must not shift its text baseline in Rust Cinnamon.
use sfle_core::compute::{compute, LayoutInput};
use serde_json::{json, Value};

fn measured(id: &str, width: f64) -> Value {
    json!({
        "node_id":id,
        "intrinsic":{
            "min_content_width":width,"max_content_width":width,
            "preferred_width":width,"min_content_height":18,
            "max_content_height":18,"preferred_height":18,
            "baseline":14
        },
        "constraints":{
            "width":{"value":null,"definite":false},
            "height":{"value":null,"definite":false}
        },
        "revision":1
    })
}

fn snapshot(padding: u32) -> LayoutInput {
    let input = json!({
        "schema_version":1,"generation":1,"direction":"ltr",
        "constraints":{
            "width":{"value":600,"definite":true},
            "height":{"value":80,"definite":true}
        },
        "nodes":[
            {"node_id":"root","parent_id":null,"component":"Flex",
             "style":{"direction":"row","wrap":"nowrap","align_items":"baseline"}},
            {"node_id":"before","parent_id":"root","component":"Text","style":{}},
            {"node_id":"span","parent_id":"root","component":"Flex",
             "style":{"direction":"row",
                      "layout_padding_top":padding,
                      "layout_padding_bottom":padding}},
            {"node_id":"inside","parent_id":"span","component":"Text","style":{}},
            {"node_id":"after","parent_id":"root","component":"Text","style":{}}
        ],
        "measurements":[
            measured("before",90.0),measured("inside",40.0),
            measured("after",70.0),
            {"node_id":"span","intrinsic":{
                "min_content_width":0,"max_content_width":0,"preferred_width":0,
                "min_content_height":0,"max_content_height":0,"preferred_height":0,
                "baseline":14},
             "constraints":{
                "width":{"value":null,"definite":false},
                "height":{"value":null,"definite":false}},
             "revision":1}
        ]
    });
    serde_json::from_value(input).expect("valid Cinnamon wire format")
}

#[test]
fn padded_inline_span_shares_painted_baseline_with_adjacent_text() {
    for padding in [0,4,19] {
        let result=compute(&snapshot(padding)).expect("baseline layout");
        let before=result.boxes.iter().find(|b|b.node_id=="before").unwrap();
        let inside=result.boxes.iter().find(|b|b.node_id=="inside").unwrap();
        let after=result.boxes.iter().find(|b|b.node_id=="after").unwrap();
        let span=result.boxes.iter().find(|b|b.node_id=="span").unwrap();
        let actual=[before.content.y+14.0,inside.content.y+14.0,after.content.y+14.0];
        assert!(actual.iter().copied().fold(f64::NEG_INFINITY,f64::max)
                -actual.iter().copied().fold(f64::INFINITY,f64::min)<=1.0/64.0,
                "padding={padding}, baseline={actual:?}");
        assert!(span.border.height >= 18.0+2.0*padding as f64-1.0);
    }
}
