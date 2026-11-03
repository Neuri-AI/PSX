//! CSS images transfer their native ratio when only one axis is authored.
use serde_json::{json, Value};
use sfle_core::compute::{compute, LayoutInput};

fn snapshot(width: f64, ratio: f64) -> LayoutInput {
    let input: Value = json!({
        "schema_version":1,"generation":1,"direction":"ltr",
        "constraints":{
            "width":{"value":800,"definite":true},
            "height":{"value":600,"definite":true}
        },
        "nodes":[
            {"node_id":"root","parent_id":null,"component":"Flex",
             "style":{"direction":"column","align_items":"center","row_gap":16}},
            {"node_id":"image","parent_id":"root","component":"Image",
             "style":{"layout_width":width,"aspect_ratio":ratio}},
            {"node_id":"heading","parent_id":"root","component":"Text","style":{}}
        ],
        "measurements":[
            {"node_id":"image","intrinsic":{
                "min_content_width":400,"max_content_width":400,
                "preferred_width":400,"min_content_height":300,
                "max_content_height":300,"preferred_height":300},
             "constraints":{"width":{"value":null,"definite":false},
                            "height":{"value":null,"definite":false}},
             "revision":1},
            {"node_id":"heading","intrinsic":{
                "min_content_width":180,"max_content_width":180,
                "preferred_width":180,"min_content_height":32,
                "max_content_height":32,"preferred_height":32},
             "constraints":{"width":{"value":null,"definite":false},
                            "height":{"value":null,"definite":false}},
             "revision":1}
        ]
    });
    serde_json::from_value(input).expect("valid Rust layout snapshot")
}

#[test]
fn image_css_width_uses_aspect_ratio_and_correct_following_gap() {
    for width in [100.0, 200.0, 300.0] {
        let result=compute(&snapshot(width,4.0/3.0)).expect("Cinnamon layout");
        let image=result.boxes.iter().find(|b|b.node_id=="image").unwrap();
        let heading=result.boxes.iter().find(|b|b.node_id=="heading").unwrap();
        assert!((image.content.width-width).abs()<=1.0/64.0);
        assert!((image.content.height-width*0.75).abs()<=1.0/64.0);
        assert!((heading.border.y-image.border.y-image.border.height-16.0).abs()<=1.0/64.0);
    }
}
